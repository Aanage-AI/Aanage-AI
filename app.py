"""
ආනාගේ AI — StudyMate
Full Rebuild: Fixed Layout, Dark Chat Text, and Sidebar Logic
"""

import io
import re
import base64
import hashlib
import datetime
from pathlib import Path
import requests
import streamlit as st
import PyPDF2
import docx
import google.generativeai as genai

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ආනාගේ AI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── External CSS Loader ────────────────────────────────────────────────────────
CSS_PATH = Path(__file__).parent / "style.css"
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

# ── Secrets & Constants ────────────────────────────────────────────────────────
ROOT_FOLDER_ID  = st.secrets.get("DRIVE_ROOT_FOLDER_ID", "")
DRIVE_API_KEY   = st.secrets.get("GOOGLE_DRIVE_API_KEY", "")
ADMIN_IMG_PATH  = Path("assets/admin/admin.jpg")

# ── Session state defaults ─────────────────────────────────────────────────────
if "messages" not in st.session_state: st.session_state.messages = []
if "docs" not in st.session_state: st.session_state.docs = {}
if "google_search" not in st.session_state: st.session_state.google_search = False
if "current_subject" not in st.session_state: st.session_state.current_subject = None

# ── Helpers ────────────────────────────────────────────────────────────────────
def get_base64_img(path):
    if path.exists():
        with open(path, "rb") as f:
            return f"data:image/jpg;base64,{base64.b64encode(f.read()).decode()}"
    return "https://ui-avatars.com/api/?name=AI&background=0f172a&color=fff"

ADMIN_IMG_64 = get_base64_img(ADMIN_IMG_PATH)

def fetch_drive_files(folder_id):
    """Fetches list of files from a Google Drive folder."""
    url = f"https://www.googleapis.com/drive/v3/files?q='{folder_id}'+in+parents+and+trashed=false&key={DRIVE_API_KEY}"
    try:
        res = requests.get(url).json()
        return res.get('files', [])
    except:
        return []

def download_drive_file(file_id):
    """Downloads a file from Drive."""
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media&key={DRIVE_API_KEY}"
    return requests.get(url).content

def extract_text(content, mime_type):
    """Extracts text from PDF or DOCX."""
    text = ""
    try:
        if "pdf" in mime_type:
            reader = PyPDF2.PdfReader(io.BytesIO(content))
            for page in reader.pages:
                text += page.extract_text() + "\n"
        elif "word" in mime_type or "docx" in mime_type:
            doc = docx.Document(io.BytesIO(content))
            for para in doc.paragraphs:
                text += para.text + "\n"
    except:
        pass
    return text

def ask_gemini(query, context, use_web):
    """Queries Gemini with the provided context."""
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-pro')
    
    prompt = f"""
    You are 'ආනාගේ AI', a helpful study assistant.
    Context from notes: {context}
    User Question: {query}
    
    If context is provided, prioritize it. If not, use your general knowledge.
    Respond in a friendly, professional tone.
    """
    
    response = model.generate_content(prompt)
    return response.text

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🎓 Study Settings")
    st.session_state.google_search = st.toggle("Enable Web Search", value=st.session_state.google_search)
    st.divider()
    
    st.markdown("### 📂 Subjects")
    # Fetch subjects from root folder
    subjects = fetch_drive_files(ROOT_FOLDER_ID)
    for sub in subjects:
        if st.button(sub['name'], use_container_width=True):
            st.session_state.current_subject = sub['name']
            files = fetch_drive_files(sub['id'])
            all_text = ""
            with st.spinner(f"Loading {sub['name']}..."):
                for f in files:
                    content = download_drive_file(f['id'])
                    all_text += extract_text(content, f.get('mimeType', ''))
            st.session_state.docs[sub['name']] = all_text
            st.success(f"Loaded {sub['name']}")

# ── Custom Header ─────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="aana-header">
    <div class="nav-left">
        <img src="{ADMIN_IMG_64}" class="hdr-avatar">
        <div class="hdr-title">ආනාගේ AI <span style="font-size: 0.8rem; opacity: 0.7;">| StudyMate</span></div>
    </div>
    <div style="background: #1e293b; padding: 4px 12px; border-radius: 20px; border: 1px solid var(--gold);">
        <span style="color: var(--gold); font-size: 11px; font-weight: bold;">
            {st.session_state.current_subject if st.session_state.current_subject else "Select Subject"}
        </span>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Chat Logic ────────────────────────────────────────────────────────────────
chat_placeholder = st.container()

with chat_placeholder:
    for msg in st.session_state.messages:
        avatar = ADMIN_IMG_64 if msg["role"] == "assistant" else "👤"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

if prompt := st.chat_input("අහන්න බලන්න..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Generate Assistant Response
    with st.chat_message("assistant", avatar=ADMIN_IMG_64):
        with st.spinner("ආනා හිතමින් පවතියි..."):
            context = st.session_state.docs.get(st.session_state.current_subject, "")
            try:
                answer = ask_gemini(prompt, context, st.session_state.google_search)
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
            except Exception as e:
                st.error(f"Error: {str(e)}")
    st.rerun()

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="aana-footer">
    <div>© 2025 ආනාගේ AI | <span class="ftr-highlight">DSVB Production</span></div>
    <div style="margin-top: 5px; opacity: 0.6;">Helping you master your exams with AI.</div>
</div>
""", unsafe_allow_html=True)
