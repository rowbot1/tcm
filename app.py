import streamlit as st
from pinecone import Pinecone
import groq
from sentence_transformers import SentenceTransformer
import json
import time
from io import BytesIO
from docx import Document
from docx.shared import Inches
import sys
sys.path.append(".") 

from patient_information import patient_info_page  # Import from your separate file

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

# ... (rest of your functions: clear_patient_data, query_pinecone, generate_diagnostic_report_part, 
#      generate_diagnostic_report, create_word_document are the same) ...



# Navigation function
def navigation():
    col1, col2, col3 = st.columns(3)  
    with col1:
        if st.button("Home"):
            st.session_state.page = "home"  
            st.experimental_rerun()   
    with col2:
        if st.button("Patient Information"):
            st.session_state.page = "patient_info"
            st.experimental_rerun()
    with col3:
        if st.button("View Report"):
            st.session_state.page = "view_report"
            st.experimental_rerun()


# Main app logic
def main():
    if 'page' not in st.session_state:
        st.session_state.page = "home"

    navigation()

    if st.session_state.page == "home":
        st.title("Welcome to AcuAssist")
        st.write("This application helps generate comprehensive Traditional Chinese Medicine (TCM) diagnostic reports based on patient information and symptoms.")
        if st.button("Clear Patient Data"):
            clear_patient_data()

    elif st.session_state.page == "patient_info":
        patient_info_page()
        if st.session_state.get('generate_report', False):
            # Generate the report
            user_input = json.dumps(st.session_state.patient_info, indent=2)
            query_results = query_pinecone(user_input)
            context = "\n".join([match['metadata']['text'] for match in query_results['matches'] if 'text' in match['metadata']])
            report = generate_diagnostic_report(context, user_input)
            st.session_state.generated_report = report
            st.session_state.generate_report = False  # Reset the flag
            st.session_state.page = "view_report"
            st.experimental_rerun()

    elif st.session_state.page == "view_report":
        st.title("TCM Diagnostic Report")
        if 'generated_report' in st.session_state and st.session_state.generated_report:
            st.write(st.session_state.generated_report)
            
            # Create Word document
            doc = create_word_document(st.session_state.generated_report)
            
            # Save document to BytesIO object
            docx_file = BytesIO()
            doc.save(docx_file)
            docx_file.seek(0)
            
            # Create download button
            st.download_button(
                label="Download Report as Word Document",
                data=docx_file,
                file_name="TCM_Diagnostic_Report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
        else:
            st.warning("No report has been generated yet. Please enter patient information and generate a report first.")


if __name__ == "__main__":
    main()

