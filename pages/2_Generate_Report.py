import streamlit as st
import json
import time
from app import index, embedding_model, groq_client

st.title("Generate TCM Diagnostic Report")

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
