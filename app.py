def main():
    if 'page' not in st.session_state:
        st.session_state.page = "Home"
    
    # Initialize patient_info if it doesn't exist
    if 'patient_info' not in st.session_state:
        st.session_state.patient_info = {}

    if st.session_state.page == "Home":
        home_page()
    elif st.session_state.page == "Patient Information":
        patient_info_page()
    elif st.session_state.page == "View Report":
        if st.session_state.get('generate_report', False):
            # Generate the report
            user_input = json.dumps(st.session_state.patient_info, indent=2)
            query_results = query_pinecone(user_input)
            context = "\n".join([match['metadata']['text'] for match in query_results['matches'] if 'text' in match['metadata']])
            report = generate_diagnostic_report(context, user_input)
            st.session_state.generated_report = report
            st.session_state.generate_report = False  # Reset the flag
        view_report_page()

if __name__ == "__main__":
    main()