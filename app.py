import streamlit as st
import datetime
import json
import time
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone
import groq
from docx import Document
from io import BytesIO
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

# Load API keys from Streamlit secrets
PINECONE_API_KEY = st.secrets["api_keys"]["PINECONE_API_KEY"]
GROQ_API_KEY = st.secrets["api_keys"]["GROQ_API_KEY"]
INDEX_NAME = "tcmapp"

# Set up Google Sheets credentials
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

try:
    # Attempt to load and parse the service account info
    service_account_info = st.secrets["gcp_service_account"]
    if isinstance(service_account_info, str):
        # If it's a string, try to parse it as JSON
        service_account_info = json.loads(service_account_info)

    creds = Credentials.from_service_account_info(service_account_info, scopes=scope)

    # Try to authorize and open the sheet
    try:
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(st.secrets["google_sheets"]["sheet_id"]).sheet1  # Get the sheet ID directly from secrets
        st.success("Successfully connected to Google Sheets")
    except gspread.exceptions.GSpreadException as e:
        st.error(f"Google Sheets authorization error: {e}")
        sheet = None
except json.JSONDecodeError:
    st.error("Error: The service account info is not valid JSON. Please check your secrets configuration.")
except KeyError as e:
    st.error(f"Error: Missing key in secrets - {str(e)}. Please check your secrets configuration.")
except Exception as e:  # Catch any other unexpected exceptions
    st.error(f"An error occurred while setting up Google Sheets: {str(e)}")
    st.error("Please check your service account credentials and make sure they are correctly formatted.")
    sheet = None

# Initialize resources
@st.cache_resource
def init_resources():
    try:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index = pc.Index(INDEX_NAME)
        embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        groq_client = groq.Client(api_key=GROQ_API_KEY)
        return index, embedding_model, groq_client
    except Exception as e:
        st.error(f"Error initializing resources: {str(e)}")
        return None, None, None

index, embedding_model, groq_client = init_resources()

# Initialize session state
if 'patient_info' not in st.session_state:
    st.session_state.patient_info = {}
if 'generated_report' not in st.session_state:
    st.session_state.generated_report = None

def clear_patient_data():
    st.session_state.patient_info = {}
    st.session_state.generated_report = None
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
        row = sheet.row_values(cell.row)
        return pd.Series(row, index=sheet.row_values(1))
    except:
        return None

def save_patient(patient_info):
    if sheet is None:
        st.error("Google Sheets connection is not available. Patient saving is disabled.")
        return
    
    # Convert dictionary values to a list and append
    row_values = list(patient_info.values())
    try:
        sheet.append_row(row_values)  # Append directly to the existing sheet
        st.success("New patient information saved")
    except gspread.exceptions.APIError as e:
        st.error(f"Error saving patient information: {e}")

def update_patient(patient_info, row):
    for col, value in enumerate(patient_info.values(), start=1):
        sheet.update_cell(row, col, value)

def patient_info_page():
    st.title("Patient Information for TCM Diagnosis")
    
    # Search for existing patient
    search_name = st.text_input("Search Patient Name")
    if search_name:
        patient_data = search_patient(search_name)
        if patient_data is not None:
            st.write("Patient found:")
            st.write(patient_data)
            if st.button("Load Patient Data"):
                st.session_state.patient_info = patient_data.to_dict()
        else:
            st.write("Patient not found")
    
    # Basic Information
    st.subheader("Basic Information")
    st.session_state.patient_info['name'] = st.text_input("Patient Name", st.session_state.patient_info.get('name', ''))
    
    # Date of Birth with age calculation
    st.write("Date of Birth (DD/MM/YYYY)")
    dob_col1, dob_col2, dob_col3 = st.columns(3)
    with dob_col1:
        dob_day = st.number_input("Day", min_value=1, max_value=31, value=st.session_state.patient_info.get('dob_day', 1))
    with dob_col2:
        dob_month = st.number_input("Month", min_value=1, max_value=12, value=st.session_state.patient_info.get('dob_month', 1))
    with dob_col3:
        dob_year = st.number_input("Year", min_value=1900, max_value=datetime.date.today().year, value=st.session_state.patient_info.get('dob_year', 1990))
    
    dob = datetime.date(dob_year, dob_month, dob_day)
    st.session_state.patient_info['dob'] = dob.strftime("%d/%m/%Y")
    age = calculate_age(dob)
    st.write(f"Patient Age: {age} years")
    
    st.session_state.patient_info['gender'] = st.selectbox("Gender", ["Male", "Female", "Other"], index=["Male", "Female", "Other"].index(st.session_state.patient_info.get('gender', 'Male')))
    
    # Chief Complaint
    st.subheader("Chief Complaint")
    st.session_state.patient_info['chief_complaint'] = st.text_area("Main Complaint", st.session_state.patient_info.get('chief_complaint', ''))
    st.session_state.patient_info['complaint_duration'] = st.text_input("Duration of Complaint", st.session_state.patient_info.get('complaint_duration', ''))
    
    # TCM Four Diagnostic Methods
    st.subheader("TCM Four Diagnostic Methods")
    
    # 1. Inspection (望 wàng)
    st.write("1. Inspection (望 wàng)")
    st.session_state.patient_info['complexion'] = st.text_input("Complexion", st.session_state.patient_info.get('complexion', ''))
    st.session_state.patient_info['tongue_color'] = st.selectbox("Tongue Color", ["Pale", "Red", "Dark Red", "Purple", "Bluish Purple"], index=["Pale", "Red", "Dark Red", "Purple", "Bluish Purple"].index(st.session_state.patient_info.get('tongue_color', 'Pale')))
    st.session_state.patient_info['tongue_coating'] = st.selectbox("Tongue Coating", ["Thin White", "Thick White", "Yellow", "Grey", "Black"], index=["Thin White", "Thick White", "Yellow", "Grey", "Black"].index(st.session_state.patient_info.get('tongue_coating', 'Thin White')))
    st.session_state.patient_info['tongue_shape'] = st.text_input("Tongue Shape and Features", st.session_state.patient_info.get('tongue_shape', ''))
    
    # 2. Auscultation and Olfaction (聞 wén)
    st.write("2. Auscultation and Olfaction (聞 wén)")
    st.session_state.patient_info['voice_sound'] = st.text_input("Voice Sound", st.session_state.patient_info.get('voice_sound', ''))
    st.session_state.patient_info['breath_odor'] = st.text_input("Breath Odor", st.session_state.patient_info.get('breath_odor', ''))
    
    # 3. Inquiry (問 wèn)
    st.write("3. Inquiry (問 wèn)")
    st.session_state.patient_info['cold_heat_sensation'] = st.selectbox("Cold/Heat Sensation", ["Aversion to Cold", "Aversion to Heat", "Alternating Cold and Heat", "Normal"], index=["Aversion to Cold", "Aversion to Heat", "Alternating Cold and Heat", "Normal"].index(st.session_state.patient_info.get('cold_heat_sensation', 'Normal')))
    st.session_state.patient_info['sweating'] = st.text_input("Sweating", st.session_state.patient_info.get('sweating', ''))
    st.session_state.patient_info['appetite'] = st.text_input("Appetite and Thirst", st.session_state.patient_info.get('appetite', ''))
    st.session_state.patient_info['sleep'] = st.text_input("Sleep Pattern", st.session_state.patient_info.get('sleep', ''))
    st.session_state.patient_info['bowel_movements'] = st.text_input("Bowel Movements", st.session_state.patient_info.get('bowel_movements', ''))
    st.session_state.patient_info['urination'] = st.text_input("Urination", st.session_state.patient_info.get('urination', ''))
    st.session_state.patient_info['pain'] = st.text_area("Pain (location, nature, factors that alleviate or aggravate)", st.session_state.patient_info.get('pain', ''))
    
    # 4. Palpation (切 qiè)
    st.write("4. Palpation (切 qiè)")
    st.session_state.patient_info['pulse_rate'] = st.number_input("Pulse Rate (BPM)", min_value=40, max_value=200, value=st.session_state.patient_info.get('pulse_rate', 70))
    st.session_state.patient_info['pulse_quality'] = st.multiselect("Pulse Quality", ["Floating", "Sinking", "Slow", "Rapid", "Strong", "Weak", "Wiry", "Slippery", "Rough"], default=st.session_state.patient_info.get('pulse_quality', []))
    
    # Additional TCM Diagnostic Information
    st.subheader("Additional TCM Diagnostic Information")
    st.session_state.patient_info['emotions'] = st.text_area("Emotional State", st.session_state.patient_info.get('emotions', ''))
    st.session_state.patient_info['lifestyle'] = st.text_area("Lifestyle Factors (diet, exercise, stress, etc.)", st.session_state.patient_info.get('lifestyle', ''))
    st.session_state.patient_info['medical_history'] = st.text_area("Relevant Medical History", st.session_state.patient_info.get('medical_history', ''))
    
    # Save patient information
    if st.button("Save Patient Information"):
        if 'name' in st.session_state.patient_info:
            existing_patient = search_patient(st.session_state.patient_info['name'])
            if existing_patient is not None:
                update_patient(st.session_state.patient_info, existing_patient.name)
                st.success("Patient information updated")
            else:
                save_patient(st.session_state.patient_info)
                st.success("New patient information saved")
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
