import streamlit as st
import datetime

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

    # Auto-save function for Basic Information
    def auto_save_basic():
        st.session_state.patient_info.update({
            'name': name,
            'dob': dob_str,
            'age': age,
            'gender': gender,
            'occupation': occupation,
        })

    auto_save_basic()
    st.session_state["Basic Information_complete"] = True

    # Presenting Complaint
    st.subheader("Presenting Complaint")
    chief_complaint = st.text_area("Chief Complaint", st.session_state.patient_info.get('chief_complaint', ''), height=100)
    complaint_background = st.text_area("Background of Main Complaint (including aggravating and relieving factors)", st.session_state.patient_info.get('complaint_background', ''), height=150)

    # Auto-save function for Presenting Complaint
    def auto_save_complaint():
        st.session_state.patient_info.update({
            'chief_complaint': chief_complaint,
            'complaint_background': complaint_background,
        })

    auto_save_complaint()
    st.session_state["Presenting Complaint_complete"] = True

    # Medical History & Lifestyle
    st.subheader("Medical History & Lifestyle")
    medical_history = st.text_area("Medical History", st.session_state.patient_info.get('medical_history', ''), height=150)
    lifestyle = st.text_area("Lifestyle Information", st.session_state.patient_info.get('lifestyle', ''), height=100)
    current_medications = st.text_area("Current Medications", st.session_state.patient_info.get('current_medications', ''), height=100)

    # Auto-save function for Medical History & Lifestyle
    def auto_save_medical():
        st.session_state.patient_info.update({
            'medical_history': medical_history,
            'lifestyle': lifestyle,
            'current_medications': current_medications,
        })

    auto_save_medical()
    st.session_state["Medical History & Lifestyle_complete"] = True

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
    answers = {}
    for question in questions:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(question)
        with col2:
            answers[question] = st.selectbox(f"Answer for: {question}", ["No", "Yes"], key=question, index=0 if st.session_state.patient_info.get(f'{question}_answer', 'No') == 'No' else 1)
        if answers[question] == "Yes":
            answers[f"{question}_details"] = st.text_area(f"Details for {question}", st.session_state.patient_info.get(f'{question}_details', ''), height=100, key=f"{question}_details")

    # Auto-save function for 10 Questions
    def auto_save_questions():
        for question in questions:
            st.session_state.patient_info[f'{question}_answer'] = answers[question]
            if answers[question] == "Yes":
                st.session_state.patient_info[f'{question}_details'] = answers[f"{question}_details"]

    auto_save_questions()
    st.session_state["10 Questions for Internal Diseases_complete"] = True

    # Tongue Diagnosis
    st.subheader("Tongue Diagnosis")
    tongue_color = st.selectbox("Tongue Color", ["Not analysed", "Pale", "Pink", "Red", "Purple", "Blue"], index=["Not analysed", "Pale", "Pink", "Red", "Purple", "Blue"].index(st.session_state.patient_info.get('tongue_color', 'Not analysed')))
    tongue_coating = st.selectbox("Tongue Coating", ["None", "Thin", "Thick", "White", "Yellow", "Grey", "Black"], index=["None", "Thin", "Thick", "White", "Yellow", "Grey", "Black"].index(st.session_state.patient_info.get('tongue_coating', 'None')))
    tongue_shape = st.multiselect("Tongue Shape", ["Normal", "Swollen", "Thin", "Cracked", "Tooth-marked"], default=st.session_state.patient_info.get('tongue_shape', []))
    tongue_moisture = st.selectbox("Tongue Moisture", ["Normal", "Dry", "Wet"], index=["Normal", "Dry", "Wet"].index(st.session_state.patient_info.get('tongue_moisture', 'Normal')))

    # Auto-save function for Tongue Diagnosis
    def auto_save_tongue():
        st.session_state.patient_info.update({
            'tongue_color': tongue_color,
            'tongue_coating': tongue_coating,
            'tongue_shape': tongue_shape,
            'tongue_moisture': tongue_moisture,
        })

    auto_save_tongue()
    st.session_state["Tongue Diagnosis_complete"] = True

    # Pulse Diagnosis
    st.subheader("Pulse Diagnosis")
    pulse_rate = st.number_input("Pulse Rate (BPM)", min_value=40, max_value=200, value=st.session_state.patient_info.get('pulse_rate', 70))
    pulse_quality = st.multiselect("Pulse Quality", ["Floating", "Sinking", "Slow", "Rapid", "String-like", "Slippery", "Rough", "Thin", "Weak", "Strong"], default=st.session_state.patient_info.get('pulse_quality', []))

    # Auto-save function for Pulse Diagnosis
    def auto_save_pulse():
        st.session_state.patient_info.update({
            'pulse_rate': pulse_rate,
            'pulse_quality': pulse_quality,
        })

    auto_save_pulse()
    st.session_state["Pulse Diagnosis_complete"] = True

    # Additional Symptoms
    st.subheader("Additional Symptoms")
    additional_symptoms = st.text_area("Any other symptoms or concerns", st.session_state.patient_info.get('additional_symptoms', ''), height=150)

    # Auto-save function for Additional Symptoms
    def auto_save_additional():
        st.session_state.patient_info['additional_symptoms'] = additional_symptoms

    auto_save_additional()
    st.session_state["Additional Symptoms_complete"] = True

    # Add a manual save button for user reassurance
    if st.button("Save All Information"):
        st.success("All patient information saved successfully!")

# Call the function
patient_info_page()