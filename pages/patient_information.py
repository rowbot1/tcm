import streamlit as st
import datetime

def patient_info_page():
    st.title("Patient Information")

    # Initialize session state for patient info if not exists
    if 'patient_info' not in st.session_state:
        st.session_state.patient_info = {}

    # Function to calculate progress
    def calculate_progress():
        required_fields = ['name', 'dob', 'gender', 'occupation', 'chief_complaint', 'complaint_background', 
                           'medical_history', 'lifestyle', 'current_medications', 'tongue_color', 'tongue_coating', 
                           'tongue_moisture', 'pulse_rate', 'additional_symptoms']
        question_fields = [f'question_{i}_answer' for i in range(10)]
        all_fields = required_fields + question_fields
        
        filled_fields = sum(1 for field in all_fields if st.session_state.patient_info.get(field))
        return filled_fields / len(all_fields)

    # Display progress bar
    progress = calculate_progress()
    st.progress(progress)
    st.write(f"Progress: {progress:.0%}")

    # Basic Information
    st.subheader("Basic Information")
    name = st.text_input("Patient Name", st.session_state.patient_info.get('name', ''))
    dob = st.date_input("Date of Birth", value=st.session_state.patient_info.get('dob'))
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

# This line is not needed if this file is imported as a module
# patient_info_page()
