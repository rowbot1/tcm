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

    # --- Patient Information Form ---
    
    with st.form("patient_form"):
        st.subheader("Basic Information")
        st.text_input("Name", key='name', value=st.session_state.patient_info.get('name', ''))
        st.date_input("Date of Birth (DOB)", key='dob', value=st.session_state.patient_info.get('dob', datetime.date.today()))
        st.selectbox("Gender", options=["Male", "Female", "Other"], key='gender', index=0)
        st.text_input("Occupation", key='occupation', value=st.session_state.patient_info.get('occupation', ''))

        st.subheader("Primary Complaint")
        st.text_area("Chief Complaint", key='chief_complaint', value=st.session_state.patient_info.get('chief_complaint', ''))
        st.text_area("Complaint Background (How long has this been a problem? etc.)", key='complaint_background', value=st.session_state.patient_info.get('complaint_background', ''))

        st.subheader("Medical History")
        st.text_area("Medical History (Any relevant illnesses, surgeries, medications, etc.)", key='medical_history', value=st.session_state.patient_info.get('medical_history', ''))
        st.text_area("Lifestyle (Diet, exercise, sleep, stress levels)", key='lifestyle', value=st.session_state.patient_info.get('lifestyle', ''))
        st.text_area("Current Medications", key='current_medications', value=st.session_state.patient_info.get('current_medications', ''))

        st.subheader("Tongue & Pulse Diagnosis")
        st.selectbox("Tongue Color", options=["Red", "Pale", "Purple", "Other"], key='tongue_color', index=0)
        st.selectbox("Tongue Coating", options=["Thick", "Thin", "White", "Yellow", "Other"], key='tongue_coating', index=0)
        st.selectbox("Tongue Moisture", options=["Dry", "Moist", "Sticky"], key='tongue_moisture', index=0)
        st.number_input("Pulse Rate (beats per minute)", key='pulse_rate', value=70, min_value=0)

        st.subheader("Additional Symptoms")
        st.text_area("Any other relevant symptoms not mentioned above?", key='additional_symptoms', value=st.session_state.patient_info.get('additional_symptoms', ''))

        st.form_submit_button("Save Information")


        for i in range(10):
            st.text_area(f"Question {i+1} Answer", key=f'question_{i}_answer', value=st.session_state.patient_info.get(f'question_{i}_answer', ''))

    
    if st.button("Generate Report"):
        if calculate_progress() > 0.5:  # Require at least 50% completion
            st.session_state.generate_report = True
            st.success("Report generation initiated. Please go to the 'View Report' page to see the results.")
        else:
            st.warning("Please fill in more patient information before generating a report. At least 50% completion is required.")

