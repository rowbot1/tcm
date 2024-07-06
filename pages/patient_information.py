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
        if calculate_progress() > 0.5:  # Require at least 50% completion
            st.session_state.generate_report = True
            st.success("Report generation initiated. Please go to the 'View Report' page to see the results.")
        else:
            st.warning("Please fill in more patient information before generating a report. At least 50% completion is required.")

# This line is not needed if this file is imported as a module
# patient_info_page()