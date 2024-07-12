import streamlit as st
import datetime
import json
import time
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
import groq
from docx import Document
from io import BytesIO
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

# Set up Streamlit
st.set_page_config(page_title="AccuAssist", layout="wide", initial_sidebar_state="collapsed")

# Custom CSS to hide the sidebar
hide_sidebar_style = """
    <style>
        div[data-testid="stSidebar"] {display: none;}
    </style>
"""
st.markdown(hide_sidebar_style, unsafe_allow_html=True)

# Load API keys from Streamlit secrets
QDRANT_URL = st.secrets["api_keys"]["QDRANT_URL"]
QDRANT_API_KEY = st.secrets["api_keys"]["QDRANT_API_KEY"]
GROQ_API_KEY = st.secrets["api_keys"]["GROQ_API_KEY"]
COLLECTION_NAME = "tcmapp"

# Set up Google Sheets credentials
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

try:
    service_account_info = st.secrets["gcp_service_account"]
    if isinstance(service_account_info, str):
        service_account_info = json.loads(service_account_info)
    
    creds = Credentials.from_service_account_info(service_account_info, scopes=scope)
    gc = gspread.authorize(creds)
    
    sheet_id = st.secrets["google_sheets"]["sheet_id"]
    sheet = gc.open_by_key(sheet_id).sheet1
    st.success("Successfully connected to Google Sheets")
except Exception as e:
    st.error(f"An error occurred while setting up Google Sheets: {str(e)}")
    sheet = None

# Initialize resources
@st.cache_resource
def init_resources():
    try:
        qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        
        # Check if collection exists, if not create it
        collections = qdrant_client.get_collections().collections
        if not any(collection.name == COLLECTION_NAME for collection in collections):
            qdrant_client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )
        
        embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        groq_client = groq.Client(api_key=GROQ_API_KEY)
        return qdrant_client, embedding_model, groq_client
    except Exception as e:
        st.error(f"Error initializing resources: {str(e)}")
        return None, None, None

qdrant_client, embedding_model, groq_client = init_resources()

# ... (rest of the code remains the same)

@st.cache_data
def query_qdrant(query_text, top_k=5):
    if qdrant_client is None:
        raise ValueError("Qdrant client is not initialized")
    query_vector = embedding_model.encode(query_text).tolist()
    results = qdrant_client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=top_k
    )
    return results

# ... (rest of the code remains the same)

def generate_diagnostic_report(context, user_input):
    # ... (same as before)
    
    # Query Qdrant for relevant context (if available)
    context = ""
    if qdrant_client is not None and embedding_model is not None:
        try:
            query_results = query_qdrant(user_input)
            context = "\n".join([match.payload.get('text', '') for match in query_results])
        except Exception as e:
            st.error(f"Error querying Qdrant: {str(e)}")
            st.warning("Proceeding with report generation without Qdrant context.")
    else:
        st.warning("Qdrant or embedding model not initialized. Proceeding without context.")
    
    # ... (rest of the function remains the same)

# ... (rest of the code remains the same)

if __name__ == "__main__":
    main()
