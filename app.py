import streamlit as st
import os
import hashlib
import json
import time
import datetime
import PyPDF2
import re
from llama_index.core import (
    VectorStoreIndex,
    SimpleDirectoryReader,
    Document,
    StorageContext,
    load_index_from_storage,
)
from docx import Document as DocxDocument
from io import BytesIO
from urllib.parse import quote
import streamlit.components.v1 as components
from pinecone import Pinecone
import groq
from sentence_transformers import SentenceTransformer

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up Streamlit
st.set_page_config(page_title="TCM Diagnostic Assistant", layout="wide")
st.title("TCM Diagnostic Assistant")

# Load API keys from Streamlit secrets
PINECONE_API_KEY = st.secrets["api_keys"]["PINECONE_API_KEY"]
GROQ_API_KEY = st.secrets["api_keys"]["GROQ_API_KEY"]
INDEX_NAME = "tcmapp"

# Initialize Pinecone client
pc = Pinecone(api_key=PINECONE_API_KEY)

# Initialize the embedding model
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

# Check if the index exists and create if it does not
if INDEX_NAME not in pc.list_indexes().names():
    pc.create_index(
        name=INDEX_NAME,
        dimension=384,  # Matches the 'all-MiniLM-L6-v2' model output
        metric='cosine'
    )

# Connect to the index
index = pc.Index(INDEX_NAME)

# Initialize Groq client
groq_client = groq.Client(api_key=GROQ_API_KEY)

# Function to add a record to Pinecone
def add_record_to_pinecone(record_id, vector, metadata=None):
    try:
        index.upsert(vectors=[(record_id, vector, metadata)])
        print(f"Record {record_id} added to Pinecone successfully.")  # Changed to print for debugging
    except Exception as e:
        print(f"Error adding record to Pinecone: {e}")  # Changed to print for debugging

# Function to get file hash
def get_file_hash(file_path):
    with open(file_path, "rb") as f:
        file_hash = hashlib.md5()
        chunk = f.read(8192)
        while chunk:
            file_hash.update(chunk)
            chunk = f.read(8192)
    return file_hash.hexdigest()

# Function to check if index needs rebuilding
def index_needs_rebuild():
    if not os.path.exists("./storage") or not os.path.exists("./storage/file_hashes.json"):
        return True
    
    with open("./storage/file_hashes.json", "r") as f:
        stored_hashes = json.load(f)
    
    current_files = {f: get_file_hash(os.path.join("./data", f)) for f in os.listdir("./data") if f.endswith('.pdf')}
    
    return current_files != stored_hashes

# Create or load index
@st.cache_resource
def create_or_load_index():
    if index_needs_rebuild():
        with st.spinner("Creating new index... This may take a while."):
            logger.info("Starting index rebuild process")
            # Check if data directory contains PDF files
            pdf_files = [f for f in os.listdir("./data") if f.endswith('.pdf')]
            if not pdf_files:
                logger.error("No PDF files found in the ./data directory")
                st.error("No PDF files found in the ./data directory. Please add TCM-related PDF files and restart the app.")
                return None
            
            # Load PDF documents manually
            documents = []
            file_hashes = {}
            failed_files = []
            for pdf_file in pdf_files:
                try:
                    logger.info(f"Processing file: {pdf_file}")
                    file_path = os.path.join("./data", pdf_file)
                    with open(file_path, 'rb') as file:
                        pdf_reader = PyPDF2.PdfReader(file)
                        text = ""
                        for page in pdf_reader.pages:
                            text += page.extract_text()
                        if text:
                            doc = Document(text=text, metadata={"file_name": pdf_file})
                            documents.append(doc)
                            file_hashes[pdf_file] = get_file_hash(file_path)
                            
                            logger.info(f"Processing document: {doc.metadata['file_name']}")
                            # Generate embeddings
                            vector = embedding_model.encode(text[:512]).tolist()
                            logger.info(f"Generated vector of length: {len(vector)}")
                            
                            # Add to Pinecone
                            metadata = {"file_name": doc.metadata["file_name"]}
                            add_record_to_pinecone(doc.metadata["file_name"], vector, metadata)
                        else:
                            logger.warning(f"No text extracted from {pdf_file}")
                            failed_files.append(pdf_file)
                except Exception as e:
                    logger.error(f"Error processing {pdf_file}: {str(e)}")
                    failed_files.append(pdf_file)
            
            if not documents:
                logger.error("Failed to load any PDF files")
                st.error("Failed to load any PDF files. Please check your PDF files and ensure they are not corrupted.")
                return None
            
            # Convert documents to index
            logger.info("Creating VectorStoreIndex")
            index = VectorStoreIndex.from_documents(documents)
            index.storage_context.persist("./storage")

            # Save file hashes
            with open("./storage/file_hashes.json", "w") as f:
                json.dump(file_hashes, f)
            
            logger.info(f"Index created successfully with {len(documents)} documents")
        
        st.success(f"Index created successfully with {len(documents)} documents.")
        if failed_files:
            logger.warning(f"Failed to load {len(failed_files)} file(s): {', '.join(failed_files)}")
            st.warning(f"Failed to load {len(failed_files)} file(s): {', '.join(failed_files)}")
    else:
        with st.spinner("Loading existing index..."):
            logger.info("Loading existing index")
            storage_context = StorageContext.from_defaults(persist_dir="./storage")
            index = load_index_from_storage(storage_context)
        logger.info("Index loaded successfully")
        st.success("Index loaded successfully.")
    
    return index

# Load or create index
index = create_or_load_index()

# Function to calculate age
def calculate_age(born):
    today = datetime.date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

# Define report sections globally
report_sections = [
    "1. Case Abstract",
    "2. Case Study",
    "3. TCM Diagnosis",
    "4. Diagnosis and Treatment Plan",
    "5. TCM Pattern Differentiation Diagram",
    "6. References"
]

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
    
    full_report = ""
    
    for section in report_sections:
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
        
        # Add a small delay to avoid rate limiting
        time.sleep(1)
    
    return full_report

# Function to create DOCX report
def create_docx_report(report_text, mermaid_diagrams):
    doc = DocxDocument()
    doc.add_heading('TCM Diagnostic Report', 0)

    # Add report text
    for paragraph in report_text.split('\n'):
        doc.add_paragraph(paragraph)

    # Add Mermaid diagrams
    if mermaid_diagrams:
        doc.add_heading('TCM Pattern Differentiation Diagrams', level=1)
        for i, diagram in enumerate(mermaid_diagrams):
            doc.add_paragraph(f"Diagram {i+1}:")
            doc.add_paragraph(diagram)

    return doc

# Main app layout
if 'index' not in st.session_state:
    st.session_state.index = None

if st.session_state.index is None:
    index = create_or_load_index()
    
    if index is not None:
        st.session_state.index = index
    else:
        st.error("Failed to create or load index. Please check the errors above.")

st.header("TCM Patient Information Form")

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

if st.button("Generate Diagnostic Report"):
    if st.session_state.index is not None:
        user_input = f"""
        Name: {name}
        Date of Birth: {dob.strftime('%d/%m/%Y') if dob else 'Not provided'}
        Age: {age if age is not None else 'Not available'}
        Gender: {gender}
        Occupation: {occupation}
        Chief Complaint: {chief_complaint}
        Complaint Background: {complaint_background}
        Medical History: {medical_history}
        Lifestyle: {lifestyle}
        Current Medications: {current_medications}
        
        10 Questions for Internal Diseases:
        {json.dumps(answers, indent=2)}
        
        Tongue Diagnosis:
        Color: {tongue_color}
        Coating: {tongue_coating}
        Shape: {", ".join(tongue_shape)}
        Moisture: {tongue_moisture}
        
        Pulse Diagnosis:
        Rate: {pulse_rate} BPM
        Quality: {", ".join(pulse_quality)}
        
        Additional Symptoms: {additional_symptoms}
        """
        
        query_engine = st.session_state.index.as_query_engine()
        context = query_engine.query(user_input).response
        
        # Estimate time for report generation (adjust as needed based on your observations)
        estimated_time = len(report_sections) * 30  # 30 seconds per section
        st.write(f"Estimated time for report generation: {estimated_time // 60} minutes and {estimated_time % 60} seconds")
        
        start_time = time.time()
        with st.spinner("Generating diagnostic report..."):
            report = generate_diagnostic_report(context, user_input)
        end_time = time.time()
        
        st.success(f"Report generated in {end_time - start_time:.2f} seconds")
        
        st.header("TCM Diagnostic Report")# Extract Mermaid diagrams
        pattern = r'```mermaid\n(.*?)```'
        matches = re.findall(pattern, report, re.DOTALL)
        
        # Remove the Mermaid code blocks from the text
        report_without_diagrams = re.sub(pattern, '', report, flags=re.DOTALL)
        
        # Display the report text
        st.markdown(report_without_diagrams)
        
        # Render Mermaid diagrams at the bottom
        st.header("TCM Pattern Differentiation Diagrams")
        for i, match in enumerate(matches):
            # Create a unique key for each Mermaid diagram
            key = f"mermaid_diagram_{i}"
            
            # Encode the Mermaid diagram content
            encoded_diagram = quote(match.strip())
            
            # Render the Mermaid diagram using a custom component
            components.html(
                f"""
                <script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script>
                <div id="{key}_container">
                    <div class="mermaid" id="{key}"></div>
                </div>
                <pre id="{key}_fallback" style="display:none; white-space: pre-wrap; word-wrap: break-word;">
                    {match.strip()}
                </pre>
                <script>
                    mermaid.initialize({{ startOnLoad: false }});
                    function renderDiagram() {{
                        var encodedDiagram = "{encoded_diagram}";
                        var decodedDiagram = decodeURIComponent(encodedDiagram);
                        mermaid.render('{key}_svg', decodedDiagram).then(function(result) {{
                            document.getElementById('{key}').innerHTML = result.svg;
                        }}).catch(function(error) {{
                            console.error('Error rendering Mermaid diagram:', error);document.getElementById('{key}_container').style.display = 'none';
                            document.getElementById('{key}_fallback').style.display = 'block';
                        }});
                    }}
                    function adjustHeight() {{
                        var diagram = document.getElementById("{key}");
                        var svg = diagram.querySelector('svg');
                        if (svg) {{
                            var height = svg.getBoundingClientRect().height;
                            diagram.style.height = height + 'px';
                            parent.postMessage({{type: 'setFrameHeight', height: height + 50}}, '*');
                        }}
                    }}
                    renderDiagram();
                    window.addEventListener('load', adjustHeight);
                    new MutationObserver(adjustHeight).observe(document.getElementById("{key}"), {{ attributes: true, childList: true, subtree: true }});
                </script>
                """,
                height=600,  # Initial height, will be adjusted by JavaScript
                scrolling=True
            )
            st.write("\n")

        # Create Word document
        doc = create_docx_report(report_without_diagrams, matches)
        
        # Save the document to a BytesIO object
        docx_io = BytesIO()
        doc.save(docx_io)
        docx_io.seek(0)

        # Create a download button for the Word document
        st.download_button(
            label="Download Report as Word Document",
            data=docx_io,
            file_name=f"TCM_Report_{name}_{datetime.date.today().strftime('%Y-%m-%d')}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    else:
        st.error("Knowledge base is not available. Please check the errors above and ensure TCM-related PDF files are in the ./data directory.")

# Add the disclaimer at the bottom of the main content
st.markdown("""
### Disclaimer
This app is for informational purposes only and does not replace professional medical advice. Always consult with a qualified TCM practitioner or healthcare provider for proper diagnosis and treatment.
""")
