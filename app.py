import streamlit as st
import datetime
import json
import time
from sentence_transformers import SentenceTransformer
import pinecone
import groq
from docx import Document
from io import BytesIO
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

# Set up Streamlit
st.set_page_config(page_title="AcuAssist", layout="wide", initial_sidebar_state="collapsed")

# Custom CSS to hide the sidebar
hide_sidebar_style = """
    <style>
        div[data-testid="stSidebar"] {display: none;}
    </style>
"""
st.markdown(hide_sidebar_style, unsafe_allow_html=True)

# Load API keys from Streamlit secrets
PINECONE_API_KEY = st.secrets["api_keys"]["PINECONE_API_KEY"]
GROQ_API_KEY = st.secrets["api_keys"]["GROQ_API_KEY"]
INDEX_NAME = "tcmapp"

# Set up Google Sheets credentials
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

try:
    service_account_info = st.secrets["gcp_service_account"]
    if isinstance(service_account_info, str):
        service_account_info = json.loads(service_account_info)
    
    creds = Credentials.from_service_account_info(service_account_info, scopes=scope)
    gc = gspread.authorize(creds)
    
    sheet_id = st.secrets["google_sheets"]["sheet_id"]
    sheet = gc.open_by_key(sheet_id).sheet1
    st.success("Successfully connected to Google Sheets")
except Exception as e:
    st.error(f"An error occurred while setting up Google Sheets: {str(e)}")
    sheet = None

# Initialize resources
@st.cache_resource
def init_resources():
    try:
        pinecone.init(api_key=PINECONE_API_KEY, environment='us-west1-gcp')
        index = pinecone.Index(INDEX_NAME)
        embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        groq_client = groq.Client(api_key=GROQ_API_KEY)
        return index, embedding_model, groq_client
    except Exception as e:
        st.error(f"Error initializing resources: {str(e)}")
        return None, None, None

index, embedding_model, groq_client = init_resources()

def clear_patient_data():
    st.session_state.patient_info = {}
    st.session_state.generated_report = None
    st.session_state.search_success = None
    st.session_state.found_patient_data = None
    st.success("Patient data has been cleared.")

def calculate_age(born):
    today = datetime.date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

@st.cache_data
def query_pinecone(query_text, top_k=5):
    if index is None:
        raise ValueError("Pinecone index is not initialized")
    query_vector = embedding_model.encode(query_text).tolist()
    results = index.query(vector=query_vector, top_k=top_k, include_metadata=True)
    return results

def generate_diagnostic_report_part(system_message, user_message):
    try:
        response = groq_client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
            max_tokens=4000,
            top_p=1,
            stop=None,
            stream=False
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        return None

def generate_diagnostic_report(context, user_input):
    patient_info = json.loads(user_input)
    patient_name = patient_info.get('name', 'Patient')
    patient_age = patient_info.get('age', 'Unknown age')
    
    system_message = f"""You are a world-renowned Traditional Chinese Medicine practitioner with decades of experience and deep knowledge of both traditional and modern TCM practices. Your diagnostic reports are known for their exceptional detail, insight, and thoroughness.

    You are generating a report for {patient_name}, a {patient_age}-year-old patient. Ensure that your report is personalized and refers to the patient by name where appropriate."""
    
    report_sections = [
        "1. Patient Overview",
        "2. TCM Diagnosis",
        "3. Pattern Differentiation",
        "4. Treatment Principle and Plan",
        "5. Acupuncture Point Prescription",
        "6. Herbal Formula Recommendation",
        "7. Lifestyle and Dietary Advice",
        "8. Prognosis and Follow-up Recommendations"
    ]
    
    document = Document()
    document.add_heading(f"TCM Diagnostic Report for {patient_name}", 0)
    
    progress_bar = st.progress(0)
    
    for i, section in enumerate(report_sections):
        user_message = f"""
        Based on the following patient information and context, generate a comprehensive and detailed TCM diagnostic report section for: {section}
        Ensure your response is extremely thorough and professional, demonstrating deep understanding of TCM principles and providing well-reasoned insights. Do not repeat the section title in your response.
        Context: {context}
        Patient Information: {user_input}
        Generate the content for {section} of the TCM Diagnostic Report:
        """
        
        with st.spinner(f"Generating {section}..."):
            section_content = generate_diagnostic_report_part(system_message, user_message)
            if section_content:
                document.add_heading(section, level=1)
                document.add_paragraph(section_content)
            else:
                st.warning(f"Failed to generate {section}. Moving to the next section.")
        
        progress_bar.progress((i + 1) / len(report_sections))
        time.sleep(1)  # Add a small delay to avoid rate limiting
    
    return document

def search_patient(name):
    if sheet is None:
        st.error("Google Sheets connection is not available. Patient search is disabled.")
        return None
    try:
        cell = sheet.find(name)
        if cell:
            row = sheet.row_values(cell.row)
            headers = sheet.row_values(1)
            patient_data = dict(zip(headers, row))
            return {k: (v if v != '' else None) for k, v in patient_data.items()}
        else:
            return None
    except Exception as e:
        st.error(f"An error occurred while searching for the patient: {str(e)}")
        return None

def save_patient(patient_info):
    if sheet is None:
        st.error("Google Sheets connection is not available. Cannot save patient information.")
        return
    try:
        # Logging patient information for debugging
        st.write("Saving patient information:")
        st.write(patient_info)

        # Ensure headers are correct and get them
        headers = sheet.row_values(1)
        st.write("Headers from sheet:", headers)
        
        # Prepare row data to match the headers
        row_data = []
        for header in headers:
            value = patient_info.get(header, "")
            row_data.append(value)
        st.write("Row data to be saved:", row_data)

        # Check if patient already exists
        existing_patient = search_patient(patient_info['name'])
        if existing_patient:
            st.write("Patient exists. Updating information.")
            cell = sheet.find(patient_info['name'])
            for col, value in enumerate(row_data, start=1):
                sheet.update_cell(cell.row, col, value)
            st.success(f"Updated information for patient: {patient_info['name']}")
        else:
            st.write("Patient does not exist. Adding new entry.")
            sheet.append_row(row_data)
            st.success(f"Added new patient: {patient_info['name']}")
    except Exception as e:
        st.error(f"An error occurred while saving patient information: {str(e)}")

def patient_info_page():
    st.title("Patient Information for TCM Diagnosis")
    
    # Initialize session state variables
    if 'patient_info' not in st.session_state:
        st.session_state.patient_info = {}
    if 'search_success' not in st.session_state:
        st.session_state.search_success = None
    if 'found_patient_data' not in st.session_state:
        st.session_state.found_patient_data = None
    
    # Search form
    search_name = st.text_input("Search Patient Name", key="search_input")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Search"):
            if search_name:
                patient_data = search_patient(search_name)
                if patient_data is not None:
                    st.session_state.found_patient_data = patient_data
                    st.session_state.search_success = True
                    st.success(f"Patient '{search_name}' found. Click 'Populate Form' to fill in the data.")
                else:
                    st.session_state.found_patient_data = None
                    st.session_state.search_success = False
                    st.warning(f"Patient '{search_name}' not found. Please enter new patient information.")
            else:
                st.warning("Please enter a patient name to search.")
    
    with col2:
        if st.button("Populate Form", disabled=not st.session_state.search_success):
            if st.session_state.found_patient_data:
                st.session_state.patient_info = st.session_state.found_patient_data.copy()
                st.success("Form populated with patient data.")
                st.experimental_rerun()
    
    # Form fields
    st.subheader("Basic Information")
    name = st.text_input("Patient Name", key="name", value=st.session_state.patient_info.get('name', ''))
    
    # Date of Birth
    dob = st.session_state.patient_info.get('dob', '')
    dob_day, dob_month, dob_year = 1, 1, 1990
    if dob:
        try:
            dob_day, dob_month, dob_year = map(int, dob.split('/'))
        except:
            st.error("Invalid date format in stored data. Using default values.")
    
    dob_col1, dob_col2, dob_col3 = st.columns(3)
    with dob_col1:
        dob_day = st.number_input("Day", key="dob_day", min_value=1, max_value=31, value=dob_day)
    with dob_col2:
        dob_month = st.number_input("Month", key="dob_month", min_value=1, max_value=12, value=dob_month)
    with dob_col3:
        dob_year = st.number_input("Year", key="dob_year", min_value=1900, max_value=datetime.date.today().year, value=dob_year)
    
    dob = datetime.date(dob_year, dob_month, dob_day)
    dob_str = dob.strftime("%d/%m/%Y")
    age = calculate_age(dob)
    st.write(f"Patient Age: {age} years")
    
    gender = st.selectbox("Gender", ["Male", "Female", "Other"], key="gender", index=["Male", "Female", "Other"].index(st.session_state.patient_info.get('gender', 'Male')))
    
    # Chief Complaint
    st.subheader("Chief Complaint")
    chief_complaint = st.text_area("Main Complaint", key="chief_complaint", value=st.session_state.patient_info.get('chief_complaint', ''))
    complaint_duration = st.text_input("Duration of Complaint", key="complaint_duration", value=st.session_state.patient_info.get('complaint_duration', ''))
    
    # TCM Four Diagnostic Methods
    st.subheader("TCM Four Diagnostic Methods")
    
    # 1. Inspection (望 wàng)
    st.write("1. Inspection (望 wàng)")
    complexion = st.text_input("Complexion", key="complexion", value=st.session_state.patient_info.get('complexion', ''))
    tongue_color = st.selectbox("Tongue Color", ["Pale", "Red", "Dark Red", "Purple", "Bluish Purple"], key="tongue_color", index=["Pale", "Red", "Dark Red", "Purple", "Bluish Purple"].index(st.session_state.patient_info.get('tongue_color', 'Pale')))
    tongue_coating = st.selectbox("Tongue Coating", ["Thin White", "Thick White", "Yellow", "Grey", "Black"], key="tongue_coating", index=["Thin White", "Thick White", "Yellow", "Grey", "Black"].index(st.session_state.patient_info.get('tongue_coating', 'Thin White')))
    tongue_shape = st.text_input("Tongue Shape and Features", key="tongue_shape", value=st.session_state.patient_info.get('tongue_shape', ''))
    
    # 2. Auscultation and Olfaction (聞 wén)
    st.write("2. Auscultation and Olfaction (聞 wén)")
    voice_sound = st.text_input("Voice Sound", key="voice_sound", value=st.session_state.patient_info.get('voice_sound', ''))
    breath_odor = st.text_input("Breath Odor", key="breath_odor", value=st.session_state.patient_info.get('breath_odor', ''))
    
    # 3. Inquiry (問 wèn)
    st.write("3. Inquiry (問 wèn)")
    cold_heat_sensation = st.selectbox("Cold/Heat Sensation", ["Aversion to Cold", "Aversion to Heat", "Alternating Cold and Heat", "Normal"], key="cold_heat_sensation", index=["Aversion to Cold", "Aversion to Heat", "Alternating Cold and Heat", "Normal"].index(st.session_state.patient_info.get('cold_heat_sensation', 'Normal')))
    sweating = st.text_input("Sweating", key="sweating", value=st.session_state.patient_info.get('sweating', ''))
    appetite = st.text_input("Appetite and Thirst", key="appetite", value=st.session_state.patient_info.get('appetite', ''))
    sleep = st.text_input("Sleep Pattern", key="sleep", value=st.session_state.patient_info.get('sleep', ''))
    bowel_movements = st.text_input("Bowel Movements", key="bowel_movements", value=st.session_state.patient_info.get('bowel_movements', ''))
    urination = st.text_input("Urination", key="urination", value=st.session_state.patient_info.get('urination', ''))
    pain = st.text_area("Pain (location, nature, factors that alleviate or aggravate)", key="pain", value=st.session_state.patient_info.get('pain', ''))
    
    # 4. Palpation (切 qiè)
    st.write("4. Palpation (切 qiè)")
    pulse_rate = st.number_input("Pulse Rate (BPM)", key="pulse_rate", min_value=40, max_value=200, value=int(st.session_state.patient_info.get('pulse_rate', 70)))
    pulse_quality = st.multiselect("Pulse Quality", ["Floating", "Sinking", "Slow", "Rapid", "Strong", "Weak", "Wiry", "Slippery", "Rough"], key="pulse_quality", default=st.session_state.patient_info.get('pulse_quality', []))
    
    # Additional TCM Diagnostic Information
    st.subheader("Additional TCM Diagnostic Information")
    emotions = st.text_area("Emotional State", key="emotions", value=st.session_state.patient_info.get('emotions', ''))
    lifestyle = st.text_area("Lifestyle Factors (diet, exercise, stress, etc.)", key="lifestyle", value=st.session_state.patient_info.get('lifestyle', ''))
    medical_history = st.text_area("Relevant Medical History", key="medical_history", value=st.session_state.patient_info.get('medical_history', ''))

    # Update session state
    st.session_state.patient_info.update({
        'name': name,
        'dob': dob_str,
        'gender': gender,
        'chief_complaint': chief_complaint,
        'complaint_duration': complaint_duration,
        'complexion': complexion,
        'tongue_color': tongue_color,
        'tongue_coating': tongue_coating,
        'tongue_shape': tongue_shape,
        'voice_sound': voice_sound,
        'breath_odor': breath_odor,
        'cold_heat_sensation': cold_heat_sensation,
        'sweating': sweating,
        'appetite': appetite,
        'sleep': sleep,
        'bowel_movements': bowel_movements,
        'urination': urination,
        'pain': pain,
        'pulse_rate': pulse_rate,
        'pulse_quality': pulse_quality,
        'emotions': emotions,
        'lifestyle': lifestyle,
        'medical_history': medical_history
    })

    # Save patient information
    if st.button("Save Patient Information"):
        if name:
            save_patient(st.session_state.patient_info)
            st.success("Patient information saved successfully")
        else:
            st.error("Please enter patient name before saving")

    # Generate Report button
    if st.button("Generate TCM Diagnostic Report"):
        if len(st.session_state.patient_info) > 10:  # Simple check for sufficient information
            try:
                # Create a copy of the patient info
                serializable_patient_info = st.session_state.patient_info.copy()
                serializable_patient_info['age'] = age  # Add calculated age to the report data
                
                user_input = json.dumps(serializable_patient_info, indent=2)
                
                # Query Pinecone for relevant context (if available)
                context = ""
                if index is not None and embedding_model is not None:
                    try:
                        query_results = query_pinecone(user_input)
                        context = "\n".join([match['metadata']['text'] for match in query_results['matches'] if 'text' in match['metadata']])
                    except Exception as e:
                        st.error(f"Error querying Pinecone: {str(e)}")
                        st.warning("Proceeding with report generation without Pinecone context.")
                else:
                    st.warning("Pinecone or embedding model not initialized. Proceeding without context.")
                
                start_time = time.time()
                report = generate_diagnostic_report(context, user_input)
                end_time = time.time()
                
                if report:
                    st.success(f"Report generated in {end_time - start_time:.2f} seconds")
                    
                    # Save the report to session state
                    st.session_state.generated_report = report
                    
                    st.write("TCM Diagnostic Report generated successfully. Please go to the 'View Report' page to see and download the report.")
                else:
                    st.error("Failed to generate the report. Please try again.")
            except Exception as e:
                st.error(f"An error occurred during report generation: {str(e)}")
        else:
            st.warning("Please fill in more patient information before generating a report.")

    # Clear form button
    if st.button("Clear Form"):
        st.session_state.patient_info = {}
        st.session_state.search_success = None
        st.session_state.found_patient_data = None
        st.experimental_rerun()

def view_report_page():
    st.title("View TCM Diagnostic Report")
    if st.session_state.generated_report:
        # Display the report content
        doc = st.session_state.generated_report
        for paragraph in doc.paragraphs:
            st.write(paragraph.text)
        
        # Add a download button for the report
        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        
        st.download_button(
            label="Download Report as Word Document",
            data=buffer,
            file_name="tcm_diagnostic_report.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    else:
        st.warning("No report has been generated yet. Please go to the 'Patient Information' page to enter patient data and generate a report.")

def main():
    st.title("Welcome to AcuAssist")
    st.write("This application helps generate comprehensive Traditional Chinese Medicine (TCM) diagnostic reports based on patient information and symptoms.")

    # Navigation
    st.write("## Navigation")
    page = st.radio("Go to", ["Patient Information", "View Report"])

    # Clear Patient Data button
    if st.button("Clear Patient Data"):
        clear_patient_data()

    # Display the selected page
    if page == "Patient Information":
        patient_info_page()
    elif page == "View Report":
        view_report_page()

if __name__ == "__main__":
    main()
