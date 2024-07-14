import streamlit as st
import datetime
import json
import time
from io import BytesIO
from sentence_transformers import SentenceTransformer
import weaviate
from weaviate.auth import AuthApiKey
import groq
from docx import Document
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# --- CONFIGURATION ---

# Load sensitive data from secrets
WEAVIATE_URL = st.secrets["api_keys"]["WEAVIATE_URL"]
WEAVIATE_API_KEY = st.secrets["api_keys"]["WEAVIATE_API_KEY"]
GROQ_API_KEY = st.secrets["api_keys"]["GROQ_API_KEY"]
INDEX_NAME = "tcmapp"  # Adjust as needed if your Weaviate index name is different

GOOGLE_SHEETS_CREDENTIALS = st.secrets["gcp_service_account"]
SHEET_ID = st.secrets["google_sheets"]["sheet_id"]

# Initialize Weaviate client
auth = AuthApiKey(api_key=WEAVIATE_API_KEY)
weaviate_client = weaviate.Client(WEAVIATE_URL, auth_client_secret=auth)


# --- UTILITY FUNCTIONS ---

def calculate_age(born):
    today = datetime.date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

def clear_patient_data():
    st.session_state.patient_info = {}
    st.session_state.generated_report = None
    st.success("Patient data has been cleared.")

# Google Sheets API Initialization
def initialize_sheets_service():
    creds = Credentials.from_service_account_info(
        GOOGLE_SHEETS_CREDENTIALS, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    service = build("sheets", "v4", credentials=creds)
    return service

# Patient Search Function
def search_patient(sheets_service, name):
    try:
        result = (
            sheets_service.spreadsheets()
            .values()
            .get(spreadsheetId=SHEET_ID, range="A:Z")
            .execute()
        )
        values = result.get("values", [])
        headers = values[0]
        for row in values[1:]:
            if row[0].lower() == name.lower():
                return dict(zip(headers, row))
        return None
    except Exception as e:
        st.error(f"Error searching for patient: {e}")
        return None

# Patient Save/Update Function
def save_or_update_patient(sheets_service, patient_data):
    try:
        result = sheets_service.spreadsheets().values().get(spreadsheetId=SHEET_ID, range="A:A").execute()
        names = result.get('values', [])
        row_index = next((i for i, name in enumerate(names) if name and name[0] == patient_data["Patient Name"]), None)

        values = [list(patient_data.values())]
        if row_index is not None:
            range_name = f'Sheet1!A{row_index + 1}'
            sheets_service.spreadsheets().values().update(
                spreadsheetId=SHEET_ID,
                range=range_name,
                valueInputOption="USER_ENTERED",
                body={"values": values}
            ).execute()
        else:
            sheets_service.spreadsheets().values().append(
                spreadsheetId=SHEET_ID,
                range="Sheet1!A1",
                valueInputOption="USER_ENTERED",
                body={"values": values}
            ).execute()
        st.success("Patient data saved/updated successfully")
    except Exception as e:
        st.error(f"Error saving/updating patient data: {e}")


# --- STYLING ---

st.markdown(
    """
    <style>
    .stApp {
        max-width: 1200px; /* Adjust width as needed */
        margin: 0 auto;  /* Center the content */
        background-color: #f4f4f4; /* Light background for the app */
        padding: 20px;
        border-radius: 10px; /* Optional rounded corners */
    }

    .stTextInput, .stTextArea, .stSelectbox {
        width: 100%;  /* Make input fields full width */
        border: 1px solid #ccc; /* Add a subtle border */
        padding: 10px; /* Add some padding */
    }

    .stButton {
        background-color: #007bff; /* Primary blue color */
        color: white;
        padding: 10px 15px;
        border: none;
        border-radius: 5px; /* Slightly rounded corners */
    }

    .stSubheader {
        color: #333; /* Darker color for subheaders */
        margin-top: 30px;
        border-bottom: 1px solid #ddd;
    }
    </style>
    """,
    unsafe_allow_html=True,
)



# --- QUERY & REPORT GENERATION FUNCTIONS ---

def query_weaviate(query_text, top_k=5):
    if weaviate_client is None:
        raise ValueError("Weaviate client is not initialized")
    query_vector = embedding_model.encode(query_text).tolist()
    near_vector = {"vector": query_vector}
    results = weaviate_client.query.get(INDEX_NAME, ["text"]).with_near_vector(near_vector).with_limit(top_k).do()

    if 'data' in results and 'Get' in results['data'] and INDEX_NAME in results['data']['Get']:
        return results['data']['Get'][INDEX_NAME]
    else:
        st.error(f"Unexpected response format: {results}")
        return []


def generate_diagnostic_report_part(system_message, user_message, context):
    try:
        response = groq_client.chat.completions.create(
            model="mixtral-8x7b-32768", 
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": f"Context: {context}\n\nUser Query: {user_message}"}
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
    patient_name = patient_info.get('Patient Name', 'Patient')
    patient_age = patient_info.get('Age', 'Unknown age')

    system_message = f"""You are a TCM practitioner tasked with generating a diagnostic report. Your knowledge is strictly limited to the information provided in the context. Do not use any external knowledge or make assumptions beyond what is explicitly stated in the context or patient information.

    You are generating a report for {patient_name}, a {patient_age}-year-old patient. Ensure your report is based solely on the provided context and patient information. If you cannot find relevant information in the context to address a particular aspect of the report, state that there is insufficient information to make a determination on that point."""

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
        Based strictly on the following patient information and context, generate the {section} of the TCM diagnostic report.
        Only use information explicitly provided in the context or patient information. If there's insufficient information for any part of this section, clearly state this limitation.
        Patient Information: {user_input}
        """

                query_results = query_weaviate(user_message)
        section_context = "\n".join([result['text'] for result in query_results])

        with st.spinner(f"Generating {section}..."):
            section_content = generate_diagnostic_report_part(system_message, user_message, section_context)
            if section_content:
                document.add_heading(section, level=1)
                document.add_paragraph(section_content)
            else:
                st.warning(f"Failed to generate {section}. Moving to the next section.")

        progress_bar.progress((i + 1) / len(report_sections))
        time.sleep(1)  # Small delay for better UX

    return document

# --- MAIN APP ---

# Initialize resources
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
groq_client = groq.Client(api_key=GROQ_API_KEY)
sheets_service = initialize_sheets_service()

# Session state for better UX
if "patient_info" not in st.session_state:
    st.session_state.patient_info = {}
if "generated_report" not in st.session_state:
    st.session_state.generated_report = None

def patient_info_page():
    st.subheader("Patient Search")
    search_name = st.text_input("Search Patient by Name")
    search_button = st.button("Search")

    if search_button:
        found_patient = search_patient(sheets_service, search_name)
        if found_patient:
            st.success(f"Patient '{search_name}' found!")
            st.session_state.patient_info = found_patient
            st.experimental_rerun()  # Refresh the page with the found data
        else:
            st.warning(f"No patient found with name '{search_name}'")

    st.subheader("Basic Information")
    patient_data = st.session_state.get('patient_info', {})

    name = st.text_input("Patient Name", key="name", value=patient_data.get('Patient Name', ''))

    dob = patient_data.get('Date of Birth (DD/MM/YYYY)', '')
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

    try:
        dob = datetime.date(dob_year, dob_month, dob_day)
        dob_str = dob.strftime("%d/%m/%Y")
        age = calculate_age(dob)
        st.write(f"Patient Age: {age} years")
    except ValueError:
        st.error("Invalid date. Please check the day, month, and year values.")
        dob_str = ""
        age = None

    gender = st.selectbox("Gender", ["Male", "Female", "Other"], key="gender", index=["Male", "Female", "Other"].index(patient_data.get('Gender', 'Male')))

    st.subheader("Chief Complaint")
    chief_complaint = st.text_area("Main Complaint", key="chief_complaint", value=patient_data.get('Chief Complaint', ''))
    complaint_duration = st.text_input("Duration of Complaint", key="complaint_duration", value=patient_data.get('Duration of Complaint', ''))

    st.subheader("TCM Four Diagnostic Methods")

    st.write("1. Inspection (望 wàng)")
    complexion = st.text_input("Complexion", key="complexion", value=patient_data.get('Complexion', ''))
    tongue_color_options = ["Not observed", "Pale", "Red", "Dark Red", "Purple", "Bluish Purple"]
    tongue_color = st.selectbox("Tongue Color", tongue_color_options, key="tongue_color", index=tongue_color_options.index(patient_data.get('Tongue Color', 'Not observed')))
    tongue_coating = st.selectbox("Tongue Coating", ["Thin White", "Thick White", "Yellow", "Grey", "Black"], key="tongue_coating", index=["Thin White", "Thick White", "Yellow", "Grey", "Black"].index(patient_data.get('Tongue Coating', 'Thin White')))
    tongue_shape = st.text_input("Tongue Shape and Features", key="tongue_shape", value=patient_data.get('Tongue Shape and Features', ''))

    st.write("2. Auscultation and Olfaction (聞 wén)")
    voice_sound = st.text_input("Voice Sound", key="voice_sound", value=patient_data.get('Voice Sound', ''))
    breath_odor = st.text_input("Breath Odor", key="breath_odor", value=patient_data.get('Breath Odor', ''))

    st.write("3. Inquiry (問 wèn)")
    cold_heat_sensation = st.selectbox("Cold/Heat Sensation", ["Aversion to Cold", "Aversion to Heat", "Alternating Cold and Heat", "Normal"], key="cold_heat_sensation", index=["Aversion to Cold", "Aversion to Heat", "Alternating Cold and Heat", "Normal"].index(patient_data.get('Cold/Heat Sensation', 'Normal')))
    sweating = st.text_input("Sweating", key="sweating", value=patient_data.get('Sweating', ''))
    appetite = st.text_input("Appetite and Thirst", key="appetite", value=patient_data.get('Appetite and Thirst', ''))
    sleep = st.text_input("Sleep Pattern", key="sleep", value=patient_data.get('Sleep Pattern', ''))
    bowel_movements = st.text_input("Bowel Movements", key="bowel_movements", value=patient_data.get('Bowel Movements', ''))
    urination = st.text_input("Urination", key="urination", value=patient_data.get('Urination', ''))
    pain = st.text_area("Pain (location, nature, factors that alleviate or aggravate)", key="pain", value=patient_data.get('Pain (location, nature, factors that alleviate or aggravate)', ''))

    st.write("4. Palpation (切 qiè)")
    pulse_rate = st.number_input("Pulse Rate (BPM)", key="pulse_rate", min_value=40, max_value=200, value=int(patient_data.get('Pulse Rate (BPM)', 70)))

    pulse_quality_options = ["Floating", "Sinking", "Slow", "Rapid", "Strong", "Weak", "Wiry", "Slippery", "Rough"]
    stored_pulse_quality = patient_data.get('Pulse Quality', '')

    if isinstance(stored_pulse_quality, str):
        default_pulse_quality = [item.strip() for item in stored_pulse_quality.split(',') if item.strip() in pulse_quality_options]
    elif isinstance(stored_pulse_quality, list):
        default_pulse_quality = [item for item in stored_pulse_quality if item in pulse_quality_options]
    else:
        default_pulse_quality = []

    pulse_quality = st.multiselect("Pulse Quality", pulse_quality_options, key="pulse_quality", default=default_pulse_quality)

    st.subheader("Additional TCM Diagnostic Information")
    emotions = st.text_area("Emotional State", key="emotions", value=patient_data.get('Emotional State', ''))
    lifestyle = st.text_area("Lifestyle Factors (diet, exercise, stress, etc.)", key="lifestyle", value=patient_data.get('Lifestyle Factors (diet, exercise, stress, etc.)', ''))
    medical_history
    
    st.text_area("Relevant Medical History", key="medical_history", value=patient_data.get('Relevant Medical History', ''))

    # Update session state with current form values
    st.session_state.patient_info.update({
        'Patient Name': name,
        'Date of Birth (DD/MM/YYYY)': dob_str,
        'Age': str(age) if age is not None else '',
        'Gender': gender,
        'Chief Complaint': chief_complaint,
        'Duration of Complaint': complaint_duration,
        'Complexion': complexion,
        'Tongue Color': tongue_color,
        'Tongue Coating': tongue_coating,
        'Tongue Shape and Features': tongue_shape,
        'Voice Sound': voice_sound,
        'Breath Odor': breath_odor,
        'Cold/Heat Sensation': cold_heat_sensation,
        'Sweating': sweating,
        'Appetite and Thirst': appetite,
        'Sleep Pattern': sleep,
        'Bowel Movements': bowel_movements,
        'Urination': urination,
        'Pain (location, nature, factors that alleviate or aggravate)': pain,
        'Pulse Rate (BPM)': str(pulse_rate),
        'Pulse Quality': ', '.join(pulse_quality),
        'Emotional State': emotions,
        'Lifestyle Factors (diet, exercise, stress, etc.)': lifestyle,
        'Relevant Medical History': medical_history
    })


def view_report_page():
    if st.session_state.generated_report:
        doc = st.session_state.generated_report
        for paragraph in doc.paragraphs:
            st.write(paragraph.text)

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
    # Top Navigation Buttons (Reinstated)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        page = st.selectbox("Go to", ["Patient Information", "View Report"])
    with col2:
        if st.button("Save Patient Information"):
            if 'Patient Name' in st.session_state.patient_info and st.session_state.patient_info['Patient Name']:
                save_or_update_patient(sheets_service, st.session_state.patient_info)
            else:
                st.error("Please enter patient name before saving")
    with col3:
        if st.button("Generate TCM Diagnostic Report"):
            if len(st.session_state.patient_info) > 10:  # Check if enough info is filled
                try:
                    serializable_patient_info = st.session_state.patient_info.copy()
                    serializable_patient_info['Age'] = calculate_age(datetime.datetime.strptime(serializable_patient_info['Date of Birth (DD/MM/YYYY)'], "%d/%m/%Y"))

                    user_input = json.dumps(serializable_patient_info, indent=2)

                    # Query Weaviate for initial context
                    query_results = query_weaviate(user_input)
                    context = "\n".join([result['text'] for result in query_results])

                    start_time = time.time()
                    report = generate_diagnostic_report(context, user_input)
                    end_time = time.time()

                    if report:
                        st.success(f"Report generated in {end_time - start_time:.2f} seconds")
                        st.session_state.generated_report = report
                        st.write("TCM Diagnostic Report generated successfully. Please go to the 'View Report' page to see and download the report.")
                    else:
                        st.error("Failed to generate the report. Please try again.")
                except Exception as e:
                    st.error(f"An error occurred during report generation: {str(e)}")
            else:
                st.warning("Please fill in more patient information before generating a report.")
    with col4:
        if st.button("Clear Form"):
            clear_patient_data()
            st.experimental_rerun()  # Refresh the page after clearing

    if page == "Patient Information":
        st.title("AcuAssist: Patient Information")
        patient_info_page()
    elif page == "View Report":
        st.title("AcuAssist: TCM Diagnostic Report")
        view_report_page()

if __name__ == "__main__":
    main()


