import streamlit as st
from pinecone import Pinecone
import groq
from sentence_transformers import SentenceTransformer
import json
import time

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

# Patient Information Page
def patient_info_page():
    st.title("Patient Information")

    # Define the sections of your form
    sections = ["Basic Information", "Presenting Complaint", "Medical History & Lifestyle", "10 Questions for Internal Diseases", "Tongue Diagnosis", "Pulse Diagnosis", "Additional Symptoms"]
    
    # Calculate progress
    completed_sections = sum(1 for section in sections if st.session_state.get(f"{section}_complete", False))
    progress = completed_sections / len(sections)

    # Display progress bar
    st.progress(progress)
    st.write(f"Progress: {progress:.0%}")

    # Initialize session state for patient info if not exists
    if 'patient_info' not in st.session_state:
        st.session_state.patient_info = {}

    # Basic Information
    st.subheader("Basic Information")
    name = st.text_input("Patient Name", st.session_state.patient_info.get('name', ''))
    st.session_state.patient_info['name'] = name

    # Add other fields here...

    # Auto-save function
    def auto_save():
        st.session_state.patient_info = {
            'name': name,
            # Add other fields here...
        }

    # Call auto_save function whenever any form field changes
    st.session_state.patient_info = auto_save()

    # Add a manual save button for user reassurance
    if st.button("Save Information"):
        st.success("Patient information saved successfully!")

    # Mark section as complete
    st.session_state["Basic Information_complete"] = True

    # Repeat similar structure for other sections...

# Generate Report Page
def generate_report_page():
    st.title("Generate TCM Diagnostic Report")

    if 'patient_info' in st.session_state:
        st.write("Patient information found. Review the details below:")
        st.json(st.session_state.patient_info)
        
        if st.button("Generate Report"):
            user_input = json.dumps(st.session_state.patient_info, indent=2)
            
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

# Main app logic
def main():
    st.title("Welcome To AcuAssist")

    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Home", "Patient Information", "Generate Report", "View Report"])

    if page == "Home":
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

        # Add a button to navigate to the Patient Information page
        if st.button("Go to Patient Information"):
            st.session_state.page = "Patient Information"
            st.experimental_rerun()

        # Add Clear Patient Data button
        if st.button("Clear Patient Data"):
            clear_patient_data()

        # Add the disclaimer at the bottom of the main content
        st.markdown("""
        ### Disclaimer
        This app is for informational purposes only and does not replace professional medical advice. 
        Always consult with a qualified TCM practitioner or healthcare provider for proper diagnosis and treatment.
        """)

    elif page == "Patient Information":
        patient_info_page()

    elif page == "Generate Report":
        generate_report_page()

    elif page == "View Report":
        st.title("View TCM Diagnostic Report")
        # Add code for viewing the report here...

if __name__ == "__main__":
    main()