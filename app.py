import streamlit as st
from pinecone import Pinecone
import groq
from sentence_transformers import SentenceTransformer
import datetime

# Set up Streamlit
st.set_page_config(page_title="AcuAssist", layout="wide")

# Load API keys from Streamlit secrets
PINECONE_API_KEY = st.secrets["api_keys"]["PINECONE_API_KEY"]
GROQ_API_KEY = st.secrets["api_keys"]["GROQ_API_KEY"]
INDEX_NAME = "tcmapp"

# Initialize Pinecone client
@st.cache_resource
def init_pinecone():
    pc = Pinecone(api_key=PINECONE_API_KEY)
    return pc.Index(INDEX_NAME)

# Initialize the embedding model
@st.cache_resource
def init_embedding_model():
    return SentenceTransformer('all-MiniLM-L6-v2')

# Initialize Groq client
@st.cache_resource
def init_groq_client():
    return groq.Client(api_key=GROQ_API_KEY)

# Initialize resources
index = init_pinecone()
embedding_model = init_embedding_model()
groq_client = init_groq_client()

# Function to clear patient data
def clear_patient_data():
    for key in list(st.session_state.keys()):
        if key.startswith('patient_') or key in ['generated_report']:
            del st.session_state[key]
    st.session_state.patient_info = {}  # Reinitialize patient_info as an empty dict
    st.success("Patient data has been cleared.")

# Patient Information Page
def patient_info_page():
    st.title("Patient Information")
    
    # Initialize session state for patient info if not exists
    if 'patient_info' not in st.session_state:
        st.session_state.patient_info = {}
    
    # Function to calculate progress
    def calculate_progress():
        required_fields = ['name', 'dob', 'gender', 'occupation', 'chief_complaint', 'complaint_background', 
                           'medical_history', 'lifestyle', 'current_medications']
        filled_fields = sum(1 for field in required_fields if st.session_state.patient_info.get(field))
        return filled_fields / len(required_fields)
    
    # Display progress bar
    progress = calculate_progress()
    st.progress(progress)
    st.write(f"Progress: {progress:.0%}")
    
    # Basic Information
    st.subheader("Basic Information")
    name = st.text_input("Patient Name", st.session_state.patient_info.get('name', ''))
    dob = st.date_input("Date of Birth", value=st.session_state.patient_info.get('dob', datetime.date.today()))
    gender = st.selectbox("Gender", ["Male", "Female", "Other"], index=["Male", "Female", "Other"].index(st.session_state.patient_info.get('gender', 'Male')))
    occupation = st.text_input("Occupation", st.session_state.patient_info.get('occupation', ''))
    
    # Presenting Complaint
    st.subheader("Presenting Complaint")
    chief_complaint = st.text_area("Chief Complaint", st.session_state.patient_info.get('chief_complaint', ''))
    complaint_background = st.text_area("Background of Main Complaint", st.session_state.patient_info.get('complaint_background', ''))
    
    # Medical History & Lifestyle
    st.subheader("Medical History & Lifestyle")
    medical_history = st.text_area("Medical History", st.session_state.patient_info.get('medical_history', ''))
    lifestyle = st.text_area("Lifestyle Information", st.session_state.patient_info.get('lifestyle', ''))
    current_medications = st.text_area("Current Medications", st.session_state.patient_info.get('current_medications', ''))
    
    # Update session state
    st.session_state.patient_info.update({
        'name': name,
        'dob': dob,
        'gender': gender,
        'occupation': occupation,
        'chief_complaint': chief_complaint,
        'complaint_background': complaint_background,
        'medical_history': medical_history,
        'lifestyle': lifestyle,
        'current_medications': current_medications,
    })
    
    # Generate Report button
    if st.button("Generate Report"):
        if calculate_progress() > 0.5:  # Require at least 50% completion
            st.session_state.generate_report = True
            st.success("Report generation initiated. Please go to the 'View Report' page to see the results.")
        else:
            st.warning("Please fill in more patient information before generating a report. At least 50% completion is required.")

# Home page
def home_page():
    st.title("Welcome to AcuAssist")
    st.write("This application helps generate comprehensive Traditional Chinese Medicine (TCM) diagnostic reports based on patient information and symptoms.")
    
    st.write("Please use the sidebar to navigate through the application:")
    st.write("1. Patient Information: Enter patient details and symptoms")
    st.write("2. Generate Report: Review entered information and generate the TCM diagnostic report")
    st.write("3. View Report: View and download the generated report")

# Generate Report page
def generate_report_page():
    st.title("Generate Report")
    # Add your generate report logic here

# View Report page
def view_report_page():
    st.title("View Report")
    # Add your view report logic here

# Main app function
def main():
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Home", "Patient Information", "Generate Report", "View Report"])

    # Clear Patient Data button in sidebar
    if st.sidebar.button("Clear Patient Data"):
        clear_patient_data()

    # Display the selected page
    if page == "Home":
        home_page()
    elif page == "Patient Information":
        patient_info_page()
    elif page == "Generate Report":
        generate_report_page()
    elif page == "View Report":
        view_report_page()

if __name__ == "__main__":
    main()
