import streamlit as st
from pinecone import Pinecone
import groq
from sentence_transformers import SentenceTransformer

# Set up Streamlit
st.set_page_config(page_title="TCM Diagnostic Assistant", layout="wide")
st.title("Welcome To AcuAssist")

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

# Main page content
st.write("""
Welcome to the AcuAssist. This application helps generate 
comprehensive Traditional Chinese Medicine (TCM) diagnostic reports based on 
patient information and symptoms.

Please use the sidebar to navigate through different sections of the application:

1. Patient Information: Enter patient details and symptoms
2. Generate Report: Review entered information and generate the TCM diagnostic report
3. View Report: View and download the generated report

Get started by entering patient information in the 'Patient Information' page.
""")

# Add the disclaimer at the bottom of the main content
st.markdown("""
### Disclaimer
This app is for informational purposes only and does not replace professional medical advice. 
Always consult with a qualified TCM practitioner or healthcare provider for proper diagnosis and treatment.
""")
