import streamlit as st
import datetime
import json
import time
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
from qdrant_client.http.exceptions import UnexpectedResponse
import groq
from docx import Document
from io import BytesIO
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

# Set up Streamlit
st.set_page_config(page_title="AccuAssist", layout="wide", initial_sidebar_state="collapsed")

# Custom CSS to hide the sidebar
hide_sidebar_style = """
    <style>
        div[data-testid="stSidebar"] {display: none;}
    </style>
"""
st.markdown(hide_sidebar_style, unsafe_allow_html=True)

# Load API keys from Streamlit secrets
QDRANT_URL = st.secrets["api_keys"]["QDRANT_URL"]
QDRANT_API_KEY = st.secrets["api_keys"]["QDRANT_API_KEY"]
GROQ_API_KEY = st.secrets["api_keys"]["GROQ_API_KEY"]
COLLECTION_NAME = "tcmapp"

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
        qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        
        # Check if collection exists, if not create it
        try:
            collections = qdrant_client.get_collections()
            if not any(collection.name == COLLECTION_NAME for collection in collections.collections):
                qdrant_client.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config=rest.VectorParams(size=384, distance=rest.Distance.COSINE),
                )
        except UnexpectedResponse as e:
            st.error(f"Error connecting to Qdrant: {str(e)}")
            st.error(f"Response status: {e.status_code}")
            st.error(f"Response content: {e.content}")
            return None, None, None
        
        embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        groq_client = groq.Client(api_key=GROQ_API_KEY)
        return qdrant_client, embedding_model, groq_client
    except Exception as e:
        st.error(f"Error initializing resources: {str(e)}")
        return None, None, None

qdrant_client, embedding_model, groq_client = init_resources()

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
def query_qdrant(query_text, top_k=5):
    if qdrant_client is None:
        raise ValueError("Qdrant client is not initialized")
    query_vector = embedding_model.encode(query_text).tolist()
    results = qdrant_client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=top_k
    )
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
        # Ensure headers are correct and get them
        headers = sheet.row_values(1)
        
        # Prepare row data to match the headers
        row_data = []
        for header in headers:
            value = patient_info.get(header, "")
            row_data.append(value)

        # Check if patient already exists
        existing_patient = search_patient(patient_info['name'])
        if existing_patient:
            cell = sheet.find(patient_info['name'])
            for col, value in enumerate(row_data, start=1):
                sheet.update_cell(cell.row, col, value)
            st.success(f"Updated information for patient: {patient_info['name']}")
        else:
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
    cold_heat_sensation = st.selectbox("Cold/Heat Sensation", ["Aversion to Cold", "Aversion to Heat", "Alternating Cold and Heat", "Normal"], key="cold_heat_sensation", index=["Aversion to Cold", "Aversion to Heat", "Alternating Cold and Heat", "Normal"].index(
