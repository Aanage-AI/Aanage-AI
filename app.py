import streamlit as st
import io
import requests
import re
from pathlib import Path

import PyPDF2
import docx
import google.generativeai as genai

st.set_page_config(
    page_title="StudyMate AI",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Instrument+Serif:ital@0;1&display=swap');

html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }

section[data-testid="stSidebar"] {
    background: #0d1117;
    border-right: 1px solid #21262d;
}
section[data-testid="stSidebar"] > div { padding: 1.5rem 1rem; }
section[data-testid="stSidebar"] * { color: #c9d1d9 !important; }
section[data-testid="stSidebar"] label {
    font-size: 0.78rem !important;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: #8b949e !important;
}
section[data-testid="stSidebar"] .stTextInput input {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    color: #f0f6fc !important;
    border-radius: 8px !important;
    font-size: 0.88rem !important;
}
section[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: #161b22 !important;
    border-color: #30363d !important;
    border-radius: 8px !important;
    color: #f0f6fc !important;
}
section[data-testid="stSidebar"] .stButton button {
    background: #1f6feb !important;
    border: none !important;
    color: #fff !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
}
section[data-testid="stSidebar"] .stButton button:hover { background: #388bfd !important; }

.main { background: #0d1117; }
.main .block-container { padding: 2rem 2rem 4rem; max-width: 820px; margin: 0 auto; }

.hero { text-align: center; padding: 80px 20px 60px; }
.hero-badge {
    display: inline-block;
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 0.75rem;
    color: #58a6ff;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 24px;
}
.hero h1 {
    font-family: 'Instrument Serif', serif;
    font-size: 3.2rem;
    font-weight: 400;
    color: #f0f6fc;
    line-height: 1.15;
    margin: 0 0 16px;
}
.hero h1 em { font-style: italic; color: #58a6ff; }
.hero p { font-size: 1.05rem; color: #8b949e; max-width: 420px; margin: 0 auto; line-height: 1.7; }
.hero-steps { display: flex; justify-content: center; gap: 12px; margin-top: 40px; flex-wrap: wrap; }
.hero-step {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 10px;
    padding: 12px 18px;
    font-size: 0.82rem;
    color: #8b949e;
    display: flex;
    align-items: center;
    gap: 8px;
}
.hero-step-num {
    background: #21262d;
    color: #58a6ff;
    border-radius: 50%;
    width: 20px; height: 20px;
    display: inline-flex;
    align-items: center; justify-content: center;
    font-size: 0.72rem; font-weight: 700; flex-shrink: 0;
}

.status-bar {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 10px;
    padding: 10px 16px;
    font-size: 0.82rem;
    color: #8b949e;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
}
.status-subject { font-weight: 600; color: #f0f6fc; font-size: 0.88rem; }
.doc-tag {
    background: #1f2937;
    border: 1px solid #2d3748;
    color: #58a6ff;
    border-radius: 6px;
    font-size: 0.72rem;
    padding: 2px 8px;
    white-space: nowrap;
    max-width: 160px;
    overflow: hidden;
    text-overflow: ellipsis;
    display: inline-block;
}

.msg-user { display: flex; justify-content: flex-end; margin: 8px 0; }
.msg-user-bubble {
    background: #1f6feb;
    color: #fff;
    border-radius: 16px 16px 4px 16px;
    padding: 12px 18px;
    max-width: 78%;
    font-size: 0.95rem;
    line-height: 1.6;
}
.msg-ai { display: flex; gap: 12px; align-items: flex-start; margin: 8px 0; }
.msg-ai-avatar {
    width: 32px; height: 32px;
    background: #1f6feb;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.75rem; font-weight: 700; color: #fff; flex-shrink: 0; margin-top: 2px;
}
.msg-ai-bubble {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 4px 16px 16px 16px;
    padding: 14px 18px;
    max-width: 88%;
    font-size: 0.95rem;
    line-height: 1.75;
    color: #c9d1d9;
}
.msg-ai-bubble strong { color: #f0f6fc; }
</style>
""", unsafe_allow_html=True)


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def scrape_folder(folder_id):
    url = f"https://drive.google.com/drive/folders/{folder_id}"
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    html = r.text
    pattern = re.compile(
        r'\[null,null,null,"([a-zA-Z0-9_\-]{25,})",null,null,null,(\d+),null,"([^"]+)"'
    )
    folders, files = [], []
    seen_f, seen_fi = set(), set()
    for m in pattern.finditer(html):
        item_id, item_type, name = m.group(1), m.group(2), m.group(3)
        if item_type == "0":
            if item_id not in seen_f:
                folders.append((name, item_id)); seen_f.add(item_id)
        else:
            if item_id not in seen_fi:
                files.append((name, item_id)); seen_fi.add(item_id)
    return folders, files


def download_file(file_id):
    session = requests.Session()
    url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t"
    r = session.get(url, headers=HEADERS, timeout=40, allow_redirects=True)
    if b"Virus scan warning" in r.content[:3000] or "virus scan warning" in r.text[:3000].lower():
        token = re.search(r'confirm=([0-9A-Za-z_\-]+)', r.text)
        if token:
            r = session.get(
                f"https://drive.google.com/uc?export=download&id={file_id}&confirm={token.group(1)}",
                headers=HEADERS, timeout=40
            )
    r.raise_for_status()
    return r.content


def extract_text(file_bytes, filename):
    ext = Path(filename).suffix.lower()
    try:
        if ext == ".pdf":
            reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
            return "\n".join(p.extract_text() or "" for p in reader.pages)
        elif ext in (".docx", ".doc"):
            d = docx.Document(io.BytesIO(file_bytes))
            return "\n".join(p.text for p in d.paragraphs)
        else:
            return file_bytes.decode("utf-8", errors="ignore")
    except Exception as e:
        return f"[Could not read {filename}: {e}]"


@st.cache_data(show_spinner=False, ttl=600)
def get_structure(root_id):
    tree = {}
    years, _ = scrape_folder(root_id)
    for year_name, year_id in years:
        tree[year_name] = {}
        sems, _ = scrape_folder(year_id)
        for sem_name, sem_id in sems:
            tree[year_name][sem_name] = {}
            subjects, _ = scrape_folder(sem_id)
            for subj_name, subj_id in subjects:
                tree[year_name][sem_name][subj_name] = subj_id
    return tree


@st.cache_data(show_spinner=False, ttl=300)
def load_subject_docs(subject_folder_id):
    _, files = scrape_folder(subject_folder_id)
    supported = {".pdf", ".docx", ".doc", ".txt"}
    docs = {}
    for name, fid in files:
        if Path(name).suffix.lower() not in supported:
            continue
        try:
            raw = download_file(fid)
            text = extract_text(raw, name)
            if text.strip():
                docs[name] = text
        except Exception:
            pass
    return docs


def ask_gemini(api_key, question, docs):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    context = "\n\n".join(
        f"=== Document: {name} ===\n{text[:12000]}" for name, text in docs.items()
    )
    prompt = f"""You are a helpful university study assistant.
Answer ONLY using the provided documents. Be thorough and clear.
Format your answer in clear paragraphs. Use bullet points where helpful.
At the very end write: **Sources:** [Doc Name], [Doc Name]
If the answer is not in the documents, say so clearly.

---DOCUMENTS---
{context}
---END---

Student question: {question}"""
    return model.generate_content(prompt).text


for k, v in [("messages", []), ("current_subject_id", None), ("docs", {})]:
    if k not in st.session_state:
        st.session_state[k] = v

ROOT_FOLDER_ID = st.secrets.get("DRIVE_ROOT_FOLDER_ID", "16fXr2rCCz_5zROjH_BGAGXPRar3Rr9Ud")

with st.sidebar:
    st.markdown("## 📚 StudyMate AI")
    st.markdown("<hr style='border-color:#21262d;margin:0.75rem 0'>", unsafe_allow_html=True)

    st.markdown("### 🔑 Gemini API Key")
    api_key = st.text_input("", type="password", placeholder="AIza...", label_visibility="collapsed")
    st.markdown(
        "<small style='color:#8b949e'>Get free key → "
        "<a href='https://aistudio.google.com/app/apikey' style='color:#58a6ff'>aistudio.google.com</a></small>",
        unsafe_allow_html=True,
    )

    st.markdown("<hr style='border-color:#21262d;margin:1rem 0'>", unsafe_allow_html=True)
    st.markdown("### 📂 Your Subject")

    with st.spinner("Loading folders…"):
        try:
            structure = get_structure(ROOT_FOLDER_ID)
        except Exception as e:
            st.error(f"Drive error: {e}")
            st.stop()

    if not structure:
        st.warning("No folders found. Check Drive sharing settings.")
        st.stop()

    year_choice = st.selectbox("Year",     list(structure.keys()))
    sem_choice  = st.selectbox("Semester", list(structure[year_choice].keys()))
    subjects    = structure[year_choice][sem_choice]

    if not subjects:
        st.warning("No subject folders in this semester.")
        st.stop()

    subj_choice = st.selectbox("Subject", list(subjects.keys()))
    subj_id     = subjects[subj_choice]

    if subj_id != st.session_state.current_subject_id:
        st.session_state.messages = []
        st.session_state.current_subject_id = subj_id
        st.session_state.docs = {}

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    load_btn = st.button("📥 Load Subject Docs", use_container_width=True)

    st.markdown("<hr style='border-color:#21262d;margin:1rem 0'>", unsafe_allow_html=True)
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []

    st.markdown(
        "<small style='color:#484f58'>Docs refresh every 5 min.<br>Drop new files in Drive anytime.</small>",
        unsafe_allow_html=True,
    )

if load_btn:
    with st.spinner(f"Loading docs for {subj_choice}…"):
        st.session_state.docs = load_subject_docs(subj_id)
    if not st.session_state.docs:
        st.warning("No readable PDF or DOCX files found in this subject folder.")

docs = st.session_state.docs

if not docs:
    st.markdown("""
    <div class="hero">
      <div class="hero-badge">AI Study Assistant</div>
      <h1>Study smarter,<br><em>not harder</em></h1>
      <p>Ask questions about your lecture notes and get instant, cited answers.</p>
      <div class="hero-steps">
        <div class="hero-step"><span class="hero-step-num">1</span> Paste your Gemini key</div>
        <div class="hero-step"><span class="hero-step-num">2</span> Select your subject</div>
        <div class="hero-step"><span class="hero-step-num">3</span> Load docs &amp; ask away</div>
      </div>
    </div>
    """, unsafe_allow_html=True)
else:
    doc_names = list(docs.keys())
    tags_html = "".join(f"<span class='doc-tag' title='{n}'>{n}</span>" for n in doc_names[:5])
    if len(doc_names) > 5:
        tags_html += f"<span class='doc-tag'>+{len(doc_names)-5} more</span>"

    st.markdown(f"""
    <div class="status-bar">
      <span>📂</span>
      <span class="status-subject">{subj_choice}</span>
      <span style="color:#30363d">|</span>
      <span>{len(doc_names)} doc{'s' if len(doc_names)!=1 else ''}</span>
      <span style="color:#30363d">|</span>
      {tags_html}
    </div>
    """, unsafe_allow_html=True)

    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f"""
            <div class="msg-user">
              <div class="msg-user-bubble">{msg['content']}</div>
            </div>""", unsafe_allow_html=True)
        else:
            content = msg['content'].replace('\n', '<br>')
            st.markdown(f"""
            <div class="msg-ai">
              <div class="msg-ai-avatar">AI</div>
              <div class="msg-ai-bubble">{content}</div>
            </div>""", unsafe_allow_html=True)

    question = st.chat_input(f"Ask about {subj_choice}…")
    if question:
        if not api_key:
            st.error("⚠️ Paste your Gemini API key in the sidebar first.")
        else:
            st.session_state.messages.append({"role": "user", "content": question})
            with st.spinner("Thinking…"):
                try:
                    answer = ask_gemini(api_key, question, docs)
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                    st.rerun()
                except Exception as e:
                    err = str(e)
                    if "API_KEY_INVALID" in err or "invalid" in err.lower():
                        st.error("❌ Invalid Gemini API key. Get a free one at aistudio.google.com")
                    else:
                        st.error(f"Error: {err}")
