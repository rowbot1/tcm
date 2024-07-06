import streamlit as st
import datetime

def patient_info_page():
    st.title("Patient Information")

    # Add navigation button at the top
    if st.button("Back to Home"):
        st.session_state.page = "Home"
        st.experimental_rerun()

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


    # Function to calculate age
    def calculate_age(born):
        today = datetime.date.today()
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

    # Basic Information
    st.subheader("Basic Information")
    name = st.text_input("Patient Name", st.session_state.patient_info.get('name', ''))
    min_date = datetime.date(1900, 1, 1)
    max_date = datetime.date.today()

    # Custom date input with UK format
    dob_str = st.text_input("Date of Birth (DD/MM/YYYY)", value=st.session_state.patient_info.get('dob', max_date.strftime("%d/%m/%Y")))
    try:
        dob = datetime.datetime.strptime(dob_str, "%d/%m/%Y").date()
        if dob < min_date or dob > max_date:
            st.error("Please enter a valid date between 01/01/1900 and today.")
            dob = None
    except ValueError:
        st.error("Please enter the date in the format DD/MM/YYYY.")
        dob = None

    if dob:
        age = calculate_age(dob)
        st.write(f"Age: {age} years")
    else:
        age = None
        st.write("Age: Not available")

    gender = st.selectbox("Gender", ["Male", "Female", "Other"], index=["Male", "Female", "Other"].index(st.session_state.patient_info.get('gender', 'Male')))
    occupation = st.text_input("Occupation", st.session_state.patient_info.get('occupation', ''))

    # Presenting Complaint
    st.subheader("Presenting Complaint")
    chief_complaint = st.text_area("Chief Complaint", st.session_state.patient_info.get('chief_complaint', ''), height=100)
    complaint_background = st.text_area("Background of Main Complaint (including aggravating and relieving factors)", st.session_state.patient_info.get('complaint_background', ''), height=150)

    # Medical History & Lifestyle
    st.subheader("Medical History & Lifestyle")
    medical_history = st.text_area("Medical History", st.session_state.patient_info.get('medical_history', ''), height=150)
    lifestyle = st.text_area("Lifestyle Information", st.session_state.patient_info.get('lifestyle', ''), height=100)
    current_medications = st.text_area("Current Medications", st.session_state.patient_info.get('current_medications', ''), height=100)

    # 10 Questions for Internal Diseases
    st.subheader("10 Questions for Internal Diseases")
    questions = [
        "Chills and/or fever",
        "Sweating and/or hot flushes",
        "Headaches (type, frequency, location) or dizziness",
        "Chest and/or digestion problems",
        "Food & appetite issues",
        "Stool & urination problems",
        "Sleep issues",
        "Deafness or tinnitus",
        "Thirst & drink preferences",
        "Pain (type, quality & location)"
    ]
    for i, question in enumerate(questions):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(question)
        with col2:
            answer = st.selectbox(f"Answer for: {question}", ["No", "Yes"], key=f"question_{i}", index=0 if st.session_state.patient_info.get(f'question_{i}_answer', 'No') == 'No' else 1)
        if answer == "Yes":
            details = st.text_area(f"Details for {question}", st.session_state.patient_info.get(f'question_{i}_details', ''), height=100, key=f"question_{i}_details")
            st.session_state.patient_info[f'question_{i}_details'] = details
        st.session_state.patient_info[f'question_{i}_answer'] = answer

    # Tongue Diagnosis
    st.subheader("Tongue Diagnosis")
    tongue_color = st.selectbox("Tongue Color", ["Not analysed", "Pale", "Pink", "Red", "Purple", "Blue"], index=["Not analysed", "Pale", "Pink", "Red", "Purple", "Blue"].index(st.session_state.patient_info.get('tongue_color', 'Not analysed')))
    tongue_coating = st.selectbox("Tongue Coating", ["None", "Thin", "Thick", "White", "Yellow", "Grey", "Black"], index=["None", "Thin", "Thick", "White", "Yellow", "Grey", "Black"].index(st.session_state.patient_info.get('tongue_coating', 'None')))
    tongue_shape = st.multiselect("Tongue Shape", ["Normal", "Swollen", "Thin", "Cracked", "Tooth-marked"], default=st.session_state.patient_info.get('tongue_shape', []))
    tongue_moisture = st.selectbox("Tongue Moisture", ["Normal", "Dry", "Wet"], index=["Normal", "Dry", "Wet"].index(st.session_state.patient_info.get('tongue_moisture', 'Normal')))

    # Pulse Diagnosis
    st.subheader("Pulse Diagnosis")
    pulse_rate = st.number_input("Pulse Rate (BPM)", min_value=40, max_value=200, value=st.session_state.patient_info.get('pulse_rate', 70))
    pulse_quality = st.multiselect("Pulse Quality", ["Floating", "Sinking", "Slow", "Rapid", "String-like", "Slippery", "Rough", "Thin", "Weak", "Strong"], default=st.session_state.patient_info.get('pulse_quality', []))

    # Additional Symptoms
    st.subheader("Additional Symptoms")
    additional_symptoms = st.text_area("Any other symptoms or concerns", st.session_state.patient_info.get('additional_symptoms', ''), height=150)

    # Update session state with all input values
    st.session_state.patient_info.update({
        'name': name,
        'dob': dob_str,
        'age': age,
        'gender': gender,
        'occupation': occupation,
        'chief_complaint': chief_complaint,
        'complaint_background': complaint_background,
        'medical_history': medical_history,
        'lifestyle': lifestyle,
        'current_medications': current_medications,
        'tongue_color': tongue_color,
        'tongue_coating': tongue_coating,
        'tongue_shape': tongue_shape,
        'tongue_moisture': tongue_moisture,
        'pulse_rate': pulse_rate,
        'pulse_quality': pulse_quality,
        'additional_symptoms': additional_symptoms
    })

    # Generate Report button
    if st.button("Generate Report"):
        if st.session_state.patient_info:
            st.session_state.generate_report = True
            st.session_state.page = "View Report"
            st.experimental_rerun()
        else:
            st.warning("Please fill in patient information before generating a report.")

             # Generate Report button
    if st.button("Generate Report"):
        if calculate_progress() > 0.5:  # Require at least 50% completion
            st.session_state.generate_report = True
            st.session_state.page = "View Report"
            st.experimental_rerun()
        else:
            st.warning("Please fill in more patient information before generating a report.")

# This line is not needed if this file is imported as a module
# patient_info_page()

