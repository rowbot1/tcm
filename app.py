import streamlit as st
import datetime
import json
import time
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone
import groq

# Set up Streamlit
st.set_page_config(page_title="AcuAssist", layout="wide")

# Load API keys from Streamlit secrets
PINECONE_API_KEY = st.secrets["api_keys"]["PINECONE_API_KEY"]
GROQ_API_KEY = st.secrets["api_keys"]["GROQ_API_KEY"]
INDEX_NAME = "tcmapp"

# Initialize resources
@st.cache_resource
def init_resources():
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index(INDEX_NAME)
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    groq_client = groq.Client(api_key=GROQ_API_KEY)
    return index, embedding_model, groq_client

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

def calculate_progress():
    required_fields = ['name', 'dob', 'gender', 'occupation', 'chief_complaint', 'complaint_background', 
                       'medical_history', 'lifestyle', 'current_medications']
    filled_fields = sum(1 for field in required_fields if st.session_state.patient_info.get(field))
    return filled_fields / len(required_fields)

def patient_info_page():
    st.title("Patient Information")
    
    # Display progress bar
    progress = calculate_progress()
    st.progress(progress)
    st.write(f"Progress: {progress:.0%}")
    
    # Basic Information
    st.subheader("Basic Information")
    st.session_state.patient_info['name'] = st.text_input("Patient Name", st.session_state.patient_info.get('name', ''))
    st.session_state.patient_info['dob'] = st.date_input("Date of Birth", value=st.session_state.patient_info.get('dob', datetime.date.today()))
    st.session_state.patient_info['gender'] = st.selectbox("Gender", ["Male", "Female", "Other"], index=["Male", "Female", "Other"].index(st.session_state.patient_info.get('gender', 'Male')))
    st.session_state.patient_info['occupation'] = st.text_input("Occupation", st.session_state.patient_info.get('occupation', ''))
    
    # Presenting Complaint
    st.subheader("Presenting Complaint")
    st.session_state.patient_info['chief_complaint'] = st.text_area("Chief Complaint", st.session_state.patient_info.get('chief_complaint', ''))
    st.session_state.patient_info['complaint_background'] = st.text_area("Background of Main Complaint", st.session_state.patient_info.get('complaint_background', ''))
    
    # Medical History & Lifestyle
    st.subheader("Medical History & Lifestyle")
    st.session_state.patient_info['medical_history'] = st.text_area("Medical History", st.session_state.patient_info.get('medical_history', ''))
    st.session_state.patient_info['lifestyle'] = st.text_area("Lifestyle Information", st.session_state.patient_info.get('lifestyle', ''))
    st.session_state.patient_info['current_medications'] = st.text_area("Current Medications", st.session_state.patient_info.get('current_medications', ''))

@st.cache_data
def query_pinecone(query_text, top_k=5):
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

def generate_report_page():
    st.title("Generate TCM Diagnostic Report")
    
    if st.session_state.patient_info:
        st.write("Patient information found. Review the details below:")
        
        # Create a copy of the patient info and convert date to string
        serializable_patient_info = st.session_state.patient_info.copy()
        if 'dob' in serializable_patient_info and isinstance(serializable_patient_info['dob'], datetime.date):
            serializable_patient_info['dob'] = serializable_patient_info['dob'].isoformat()
        
        st.json(serializable_patient_info)
        
        if st.button("Generate Report"):
            user_input = json.dumps(serializable_patient_info, indent=2)
            
            # Query Pinecone for relevant context
            query_results = query_pinecone(user_input)
            context = "\n".join([match['metadata']['text'] for match in query_results['matches'] if 'text' in match['metadata']])
            
            start_time = time.time()
            report = generate_diagnostic_report(context, user_input)
            end_time = time.time()
            
            st.success(f"Report generated in {end_time - start_time:.2f} seconds")
            
            # Save the report to session state
            st.session_state.generated_report = report
            
            st.write("Report generated successfully. Go to the 'View Report' page to see and download the report.")
    else:
        st.warning("No patient information found. Please enter patient information in the 'Patient Information' page first.")

def view_report_page():
    st.title("View Report")
    if st.session_state.generated_report:
        st.write(st.session_state.generated_report)
        # Add a download button for the report
        st.download_button(
            label="Download Report",
            data=st.session_state.generated_report,
            file_name="tcm_diagnostic_report.txt",
            mime="text/plain"
        )
    else:
        st.warning("No report has been generated yet. Please go to the 'Generate Report' page to create a report.")

def main():
    st.title("Welcome to AcuAssist")
    st.write("This application helps generate comprehensive Traditional Chinese Medicine (TCM) diagnostic reports based on patient information and symptoms.")

    # Navigation
    st.write("## Navigation")
    page = st.radio("Go to", ["Patient Information", "Generate Report", "View Report"])

    # Clear Patient Data button
    if st.button("Clear Patient Data"):
        clear_patient_data()

    # Display the selected page
    if page == "Patient Information":
        patient_info_page()
    elif page == "Generate Report":
        generate_report_page()
    elif page == "View Report":
        view_report_page()

if __name__ == "__main__":
    main()
