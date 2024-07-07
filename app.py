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

def calculate_progress():
    required_fields = [
        'name', 'dob', 'gender', 'occupation', 'chief_complaint', 'complaint_background', 
        'medical_history', 'lifestyle', 'current_medications', 'signs_symptoms',
        'aggravating_factors', 'relieving_factors', 'tongue_diagnosis', 'pulse_diagnosis',
        'diagnosis', 'treatment_principles', 'acupuncture_points', 'herbal_prescriptions',
        'treatment_date', 'points_used_session', 'patient_feedback', 'therapist_notes'
    ]
    
    # Add the 10 questions fields
    questions = [
        "chills_and/or_fever", "sweating_and/or_hot_flushes", "headaches",
        "any_problems_with_chest_and/or_digestion", "food_&_appetite", "stools_&_urination",
        "sleep", "deafness/tinnitus", "thirst_&_drink", "pain"
    ]
    for question in questions:
        required_fields.append(f"{question}_checkbox")
        required_fields.append(f"{question}_details")

    filled_fields = sum(1 for field in required_fields if st.session_state.patient_info.get(field))
    return filled_fields / len(required_fields)

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

def patient_info_page():
    st.title("Patient Information")
    
    # Display progress bar
    progress = calculate_progress()
    st.progress(progress)
    st.write(f"Progress: {progress:.0%}")
    
    # Basic Information
    st.subheader("Basic Information")
    st.session_state.patient_info['name'] = st.text_input("Patient Name", st.session_state.patient_info.get('name', ''))
    
    # Date of Birth with manual input
    st.write("Date of Birth (DD/MM/YYYY)")
    dob_col1, dob_col2, dob_col3 = st.columns(3)
    with dob_col1:
        dob_day = st.number_input("Day", min_value=1, max_value=31, value=st.session_state.patient_info.get('dob_day', 1))
    with dob_col2:
        dob_month = st.number_input("Month", min_value=1, max_value=12, value=st.session_state.patient_info.get('dob_month', 1))
    with dob_col3:
        dob_year = st.number_input("Year", min_value=1900, max_value=datetime.date.today().year, value=st.session_state.patient_info.get('dob_year', 1990))
    st.session_state.patient_info['dob'] = f"{dob_day:02d}/{dob_month:02d}/{dob_year}"
    
    st.session_state.patient_info['gender'] = st.selectbox("Gender", ["Male", "Female", "Other"], index=["Male", "Female", "Other"].index(st.session_state.patient_info.get('gender', 'Male')))
    st.session_state.patient_info['occupation'] = st.text_input("Occupation", st.session_state.patient_info.get('occupation', ''))
    st.session_state.patient_info['marital_status'] = st.selectbox("Marital Status", ["Single", "Married", "Divorced", "Widowed", "Other"], index=["Single", "Married", "Divorced", "Widowed", "Other"].index(st.session_state.patient_info.get('marital_status', 'Single')))
    st.session_state.patient_info['contact_number'] = st.text_input("Contact Number", st.session_state.patient_info.get('contact_number', ''))
    st.session_state.patient_info['email'] = st.text_input("Email", st.session_state.patient_info.get('email', ''))
    
    # Presenting Complaint
    st.subheader("Presenting Complaint")
    st.session_state.patient_info['chief_complaint'] = st.text_area("Chief Complaint", st.session_state.patient_info.get('chief_complaint', ''))
    st.session_state.patient_info['complaint_duration'] = st.text_input("Duration of Complaint", st.session_state.patient_info.get('complaint_duration', ''))
    st.session_state.patient_info['complaint_frequency'] = st.text_input("Frequency of Complaint", st.session_state.patient_info.get('complaint_frequency', ''))
    st.session_state.patient_info['complaint_severity'] = st.slider("Severity of Complaint", 0, 10, st.session_state.patient_info.get('complaint_severity', 5))
    st.session_state.patient_info['complaint_background'] = st.text_area("Background of Main Complaint", st.session_state.patient_info.get('complaint_background', ''))
    
    # Medical History & Lifestyle
    st.subheader("Medical History & Lifestyle")
    st.session_state.patient_info['medical_history'] = st.text_area("Medical History (past illnesses, surgeries, etc.)", st.session_state.patient_info.get('medical_history', ''))
    st.session_state.patient_info['family_medical_history'] = st.text_area("Family Medical History", st.session_state.patient_info.get('family_medical_history', ''))
    st.session_state.patient_info['allergies'] = st.text_area("Allergies", st.session_state.patient_info.get('allergies', ''))
    st.session_state.patient_info['current_medications'] = st.text_area("Current Medications (including dosages)", st.session_state.patient_info.get('current_medications', ''))
    st.session_state.patient_info['lifestyle'] = st.text_area("Lifestyle Information (diet, exercise, sleep patterns, stress levels)", st.session_state.patient_info.get('lifestyle', ''))
    st.session_state.patient_info['alcohol_consumption'] = st.text_input("Alcohol Consumption", st.session_state.patient_info.get('alcohol_consumption', ''))
    st.session_state.patient_info['smoking_habits'] = st.text_input("Smoking Habits", st.session_state.patient_info.get('smoking_habits', ''))
    
    # Signs and Symptoms
    st.subheader("Signs and Symptoms")
    st.session_state.patient_info['signs_symptoms'] = st.text_area("Detailed Signs and Symptoms", st.session_state.patient_info.get('signs_symptoms', ''))
    st.session_state.patient_info['aggravating_factors'] = st.text_area("Aggravating Factors", st.session_state.patient_info.get('aggravating_factors', ''))
    st.session_state.patient_info['relieving_factors'] = st.text_area("Relieving Factors", st.session_state.patient_info.get('relieving_factors', ''))
    
    # 10 Questions for Internal Diseases
    st.subheader("10 Questions for Internal Diseases")
    questions = [
        "Chills and/or Fever",
        "Sweating and/or Hot Flushes",
        "Headaches; type, frequency, location, dizziness",
        "Any problems with Chest and/or Digestion",
        "Food & Appetite",
        "Stools & Urination",
        "Sleep",
        "Deafness/Tinnitus",
        "Thirst & Drink",
        "Pain; type, quality & location"
    ]
    for question in questions:
        col1, col2 = st.columns([1, 3])
        with col1:
            st.session_state.patient_info[f'{question.lower().replace(" ", "_")}_checkbox'] = st.checkbox(question, st.session_state.patient_info.get(f'{question.lower().replace(" ", "_")}_checkbox', False))
        with col2:
            st.session_state.patient_info[f'{question.lower().replace(" ", "_")}_details'] = st.text_area(f"{question} Details", st.session_state.patient_info.get(f'{question.lower().replace(" ", "_")}_details', ''))
    
    # Physical Examination
    st.subheader("Physical Examination")
    st.session_state.patient_info['tongue_diagnosis'] = st.text_area("Tongue Diagnosis (color, coating, moisture, shape, etc.)", st.session_state.patient_info.get('tongue_diagnosis', ''))
    st.session_state.patient_info['pulse_diagnosis'] = st.text_area("Pulse Diagnosis (rate, rhythm, strength, quality on both wrists)", st.session_state.patient_info.get('pulse_diagnosis', ''))
    st.session_state.patient_info['palpation_findings'] = st.text_area("Palpation Findings", st.session_state.patient_info.get('palpation_findings', ''))
    st.session_state.patient_info['other_observations'] = st.text_area("Other Observations", st.session_state.patient_info.get('other_observations', ''))
    
    # Diagnosis and Treatment Plan
    st.subheader("Diagnosis and Treatment Plan")
    st.session_state.patient_info['tcm_diagnosis'] = st.text_area("TCM Diagnosis", st.session_state.patient_info.get('tcm_diagnosis', ''))
    st.session_state.patient_info['western_diagnosis'] = st.text_area("Western Medicine Diagnosis (if applicable)", st.session_state.patient_info.get('western_diagnosis', ''))
    st.session_state.patient_info['treatment_principles'] = st.text_area("Treatment Principles", st.session_state.patient_info.get('treatment_principles', ''))
    st.session_state.patient_info['acupuncture_points'] = st.text_area("Acupuncture Points Used (point names, actions, and insertion details)", st.session_state.patient_info.get('acupuncture_points', ''))
    st.session_state.patient_info['herbal_prescriptions'] = st.text_area("Herbal Prescriptions (herbs used, dosages, and preparation methods)", st.session_state.patient_info.get('herbal_prescriptions', ''))
    st.session_state.patient_info['lifestyle_recommendations'] = st.text_area("Lifestyle Recommendations", st.session_state.patient_info.get('lifestyle_recommendations', ''))
    st.session_state.patient_info['dietary_advice'] = st.text_area("Dietary Advice", st.session_state.patient_info.get('dietary_advice', ''))
    
    # Treatment Sessions
    st.subheader("Treatment Sessions")
    st.write("Treatment Date (DD/MM/YYYY)")
    td_col1, td_col2, td_col3 = st.columns(3)
    with td_col1:
        td_day = st.number_input("Day", min_value=1, max_value=31, value=st.session_state.patient_info.get('td_day', datetime.date.today().day), key="td_day")
    with td_col2:
        td_month = st.number_input("Month", min_value=1, max_value=12, value=st.session_state.patient_info.get('td_month', datetime.date.today().month), key="td_month")
    with td_col3:
        td_year = st.number_input("Year", min_value=2000, max_value=datetime.date.today().year, value=st.session_state.patient_info.get('td_year', datetime.date.today().year), key="td_year")
    st.session_state.patient_info['treatment_date'] = f"{td_day:02d}/{td_month:02d}/{td_year}"
    
    st.session_state.patient_info['points_used_session'] = st.text_area("Points Used in Session", st.session_state.patient_info.get('points_used_session', ''))
    st.session_state.patient_info['treatment_duration'] = st.number_input("Treatment Duration (minutes)", min_value=0, value=st.session_state.patient_info.get('treatment_duration', 30))
    st.session_state.patient_info['patient_feedback'] = st.text_area("Patient Feedback", st.session_state.patient_info.get('patient_feedback', ''))
    st.session_state.patient_info['immediate_results'] = st.text_area("Immediate Results/Reactions", st.session_state.patient_info.get('immediate_results', ''))
    st.session_state.patient_info['therapist_notes'] = st.text_area("Therapist's Notes", st.session_state.patient_info.get('therapist_notes', ''))
    st.session_state.patient_info['follow_up_recommendations'] = st.text_area("Follow-up Recommendations", st.session_state.patient_info.get('follow_up_recommendations', ''))

    # Generate Report button
    if st.button("Generate Report"):
        if calculate_progress() > 0.5:  # Require at least 50% completion
            try:
                # Create a copy of the patient info
                serializable_patient_info = st.session_state.patient_info.copy()
                
                user_input = json.dumps(serializable_patient_info, indent=2)
                
                # Query Pinecone for relevant context
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
                    
                    st.write("Report generated successfully. Please go to the 'View Report' page to see and download the report.")
                else:
                    st.error("Failed to generate the report. Please try again.")
            except Exception as e:
                st.error(f"An error occurred during report generation: {str(e)}")
        else:
            st.warning("Please fill in more patient information before generating a report. At least 50% completion is required.")

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
