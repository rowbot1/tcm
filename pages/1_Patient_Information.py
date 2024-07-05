import streamlit as st
import datetime

st.title("Patient Information")

# Function to calculate age
def calculate_age(born):
    today = datetime.date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

# Basic Information
st.subheader("Basic Information")
name = st.text_input("Patient Name")
min_date = datetime.date(1900, 1, 1)
max_date = datetime.date.today()

# Custom date input with UK format
dob_str = st.text_input("Date of Birth (DD/MM/YYYY)", value=max_date.strftime("%d/%m/%Y"))
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

gender = st.selectbox("Gender", ["Male", "Female", "Other"])
occupation = st.text_input("Occupation")

# Presenting Complaint
st.subheader("Presenting Complaint")
chief_complaint = st.text_area("Chief Complaint", height=100)
complaint_background = st.text_area("Background of Main Complaint (including aggravating and relieving factors)", height=150)

# Medical History & Lifestyle
st.subheader("Medical History & Lifestyle")
medical_history = st.text_area("Medical History", height=150)
lifestyle = st.text_area("Lifestyle Information", height=100)
current_medications = st.text_area("Current Medications", height=100)

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
        answers[question] = st.selectbox(f"Answer for: {question}", ["No", "Yes"], key=question)
    if answers[question] == "Yes":
        answers[f"{question}_details"] = st.text_area(f"Details for {question}", height=100, key=f"{question}_details")

# Tongue Diagnosis
st.subheader("Tongue Diagnosis")
tongue_color = st.selectbox("Tongue Color", ["Not analysed", "Pale", "Pink", "Red", "Purple", "Blue"])
tongue_coating = st.selectbox("Tongue Coating", ["None", "Thin", "Thick", "White", "Yellow", "Grey", "Black"])
tongue_shape = st.multiselect("Tongue Shape", ["Normal", "Swollen", "Thin", "Cracked", "Tooth-marked"])
tongue_moisture = st.selectbox("Tongue Moisture", ["Normal", "Dry", "Wet"])

# Pulse Diagnosis
st.subheader("Pulse Diagnosis")
pulse_rate = st.number_input("Pulse Rate (BPM)", min_value=40, max_value=200)
pulse_quality = st.multiselect("Pulse Quality", ["Floating", "Sinking", "Slow", "Rapid", "String-like", "Slippery", "Rough", "Thin", "Weak", "Strong"])

# Additional Symptoms
st.subheader("Additional Symptoms")
additional_symptoms = st.text_area("Any other symptoms or concerns", height=150)

# Save patient information to session state
if st.button("Save Patient Information"):
    st.session_state.patient_info = {
        "name": name,
        "dob": dob_str,
        "age": age,
        "gender": gender,
        "occupation": occupation,
        "chief_complaint": chief_complaint,
        "complaint_background": complaint_background,
        "medical_history": medical_history,
        "lifestyle": lifestyle,
        "current_medications": current_medications,
        "answers": answers,
        "tongue_color": tongue_color,
        "tongue_coating": tongue_coating,
        "tongue_shape": tongue_shape,
        "tongue_moisture": tongue_moisture,
        "pulse_rate": pulse_rate,
        "pulse_quality": pulse_quality,
        "additional_symptoms": additional_symptoms
    }
    st.success("Patient information saved. You can now proceed to generate the report.")
