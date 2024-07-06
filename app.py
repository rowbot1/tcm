import streamlit as st
from pinecone import Pinecone
import groq
from sentence_transformers import SentenceTransformer
import json
import time

# Import the patient_info_page function
from pages.patient_information import patient_info_page

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

# ... (rest of your functions remain the same)

# Main app logic
def main():
    if 'page' not in st.session_state:
        st.session_state.page = "Home"
    
    # Initialize patient_info if it doesn't exist
    if 'patient_info' not in st.session_state:
        st.session_state.patient_info = {}

    if st.session_state.page == "Home":
        home_page()
    elif st.session_state.page == "Patient Information":
        patient_info_page()
    elif st.session_state.page == "Generate Report":
        generate_report_page()
    elif st.session_state.page == "View Report":
        view_report_page()

if __name__ == "__main__":
    main()