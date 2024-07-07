import streamlit as st
import datetime

# Set up Streamlit
st.set_page_config(page_title="AcuAssist", layout="wide")

# Initialize session state for patient info if not exists
if 'patient_info' not in st.session_state:
    st.session_state.patient_info = {}

def clear_patient_data():
    st.session_state.patient_info = {}
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
    
    # Generate Report button
    if st.button("Generate Report"):
        if calculate_progress() > 0.5:  # Require at least 50% completion
            st.session_state.generate_report = True
            st.success("Report generation initiated. Please go to the 'View Report' page to see the results.")
        else:
            st.warning("Please fill in more patient information before generating a report. At least 50% completion is required.")

def generate_report_page():
    st.title("Generate Report")
    st.write("Report generation logic will be implemented here.")

def view_report_page():
    st.title("View Report")
    st.write("Report viewing logic will be implemented here.")

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
