import streamlit as st
from pinecone import Pinecone
import groq
from sentence_transformers import SentenceTransformer
import json
import time
from io import BytesIO
from docx import Document
from docx.shared import Inches

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

# Function to query Pinecone
@st.cache_data
def query_pinecone(query_text, top_k=5):
    query_vector = embedding_model.encode(query_text).tolist()
    results = index.query(vector=query_vector, top_k=top_k, include_metadata=True)
    return results

# Function to generate diagnostic report part
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

# Function to generate a full diagnostic report
def generate_diagnostic_report(context, user_input):
    system_message = "You are a world-renowned Traditional Chinese Medicine practitioner with decades of experience and deep knowledge of both traditional and modern TCM practices. Your diagnostic reports are known for their exceptional detail, insight, and thoroughness."
    
    report_sections = [
        "1. Case Abstract",
        "2. Case Study",
        "3. TCM Diagnosis",
        "4. Diagnosis and Treatment Plan",
        "5. TCM Pattern Differentiation Diagram",
        "6. References"
    ]
    
    full_report = ""
    progress_bar = st.progress(0)
    
    for i, section in enumerate(report_sections):
        user_message = f"""
        Based on the following patient information and context, generate a comprehensive and detailed TCM diagnostic report section for: {section}

        Ensure your response is extremely thorough and professional, demonstrating deep understanding of TCM principles and providing well-reasoned insights.

        Context: {context}

        Patient Input: {user_input}

        Generate the {section} of the TCM Diagnostic Report:
        """
        
        with st.spinner(f"Generating {section}..."):
            section_content = generate_diagnostic_report_part(system_message, user_message)
            if section_content:
                full_report += f"\n\n{section}\n{section_content}"
            else:
                st.warning(f"Failed to generate {section}. Moving to the next section.")
        
        progress_bar.progress((i + 1) / len(report_sections))
        time.sleep(1)  # Add a small delay to avoid rate limiting
    
    return full_report

# Function to create Word document
def create_word_document(report):
    doc = Document()
    doc.add_heading('TCM Diagnostic Report', 0)
    
    for line in report.split('\n'):
        if line.startswith('#'):
            level = line.count('#')
            doc.add_heading(line.strip('#').strip(), level)
        else:
            doc.add_paragraph(line)
    
    return doc

# View Report Page
def view_report_page():
    st.title("View TCM Diagnostic Report")
    
    if st.button("Back to Patient Information"):
        st.session_state.page = "Patient Information"
        st.experimental_rerun()
    
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
        st.warning("No report has been generated yet. Please generate a report first.")

# Main app logic
def main():
    if 'page' not in st.session_state:
        st.session_state.page = "Patient Information"
    
    # Initialize patient_info if it doesn't exist
    if 'patient_info' not in st.session_state:
        st.session_state.patient_info = {}

    if st.session_state.page == "Patient Information":
        patient_info_page()
        if st.session_state.get('generate_report', False):
            # Generate the report
            user_input = json.dumps(st.session_state.patient_info, indent=2)
            query_results = query_pinecone(user_input)
            context = "\n".join([match['metadata']['text'] for match in query_results['matches'] if 'text' in match['metadata']])
            report = generate_diagnostic_report(context, user_input)
            st.session_state.generated_report = report
            st.session_state.generate_report = False  # Reset the flag
            st.session_state.page = "View Report"
            st.experimental_rerun()
    elif st.session_state.page == "View Report":
        view_report_page()

if __name__ == "__main__":
    main()