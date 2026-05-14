import streamlit as st
import io
import requests
import re
from pathlib import Path

import PyPDF2
import docx
import google.generativeai as genai

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ආනාගේ AI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Secrets ────────────────────────────────────────────────────────────────────
ROOT_FOLDER_ID   = st.secrets.get("DRIVE_ROOT_FOLDER_ID", "")
DRIVE_API_KEY    = st.secrets.get("GOOGLE_DRIVE_API_KEY", "")
ADMIN_PASSWORD   = st.secrets.get("ADMIN_PASSWORD", "admin123")
SHARED_GEMINI_KEY = st.secrets.get("GEMINI_API_KEY", "")
ADMIN_AVATAR_URL = "https://venurakabojithananda.github.io/assets/admin/admin.jpg"

# ── Styles ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Sinhala:wght@400;700&family=Syne:wght@700;800&family=Lora:ital@0;1&family=Nunito:wght@400;600;700;800&display=swap');

*, *:before, *:after { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; }

#MainMenu, footer, .stDeployButton,
[data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stSidebarCollapseButton"] { display: none !important; }
header[data-testid="stHeader"] { display: none !important; }

body, [class*="css"] {
    font-family: 'Nunito', sans-serif;
    background: #f4f1eb;
    color: #1a1a2e;
}
.main .block-container { padding: 0 !important; max-width: 100% !important; }

/* ─── HEADER ─── */
.aana-header {
    background: linear-gradient(135deg,#06101e,#0d1e3b 55%,#162b56);
    padding: .3rem clamp(.7rem,3vw,1.5rem);
    display: flex; align-items: center;
    justify-content: space-between; gap: .5rem;
    position: sticky; top: 0; z-index: 300;
    box-shadow: 0 4px 24px rgba(0,0,0,.55);
    min-height: 50px; overflow: visible;
}
.aana-header::after {
    content: ""; position: absolute;
    bottom: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg,transparent,#3b82f6,#ffd84d,#3b82f6,transparent);
    animation: shimmer 3s ease-in-out infinite;
}
@keyframes shimmer { 0%,100%{opacity:.3} 50%{opacity:1} }

.hdr-avatar {
    width:38px;height:38px;border-radius:50%;object-fit:cover;
    border:2.5px solid rgba(59,130,246,.55);
    box-shadow:0 0 14px rgba(59,130,246,.4);
    flex-shrink:0;transition:transform .25s,box-shadow .25s;
}
.hdr-center { display:flex;align-items:center;gap:.55rem;flex:1;min-width:0;margin-left:.5rem; }
.hdr-title {
    font-family:'Syne',sans-serif;
    font-size:clamp(1rem,2.6vw,1.3rem);font-weight:800;
    color:#f0f4ff;letter-spacing:.02em;
    display:flex;align-items:center;gap:.3rem;
    text-shadow:0 0 20px rgba(59,130,246,.45);white-space:nowrap;
}
.hdr-sinhala {
    font-family:'Noto Sans Sinhala',sans-serif;
    font-weight:700;color:#9ecfff;
    font-size:clamp(1.05rem,2.8vw,1.35rem);
}
.hdr-sub {
    font-family:'Lora',serif;font-style:italic;
    font-size:clamp(.55rem,1.1vw,.68rem);
    color:rgba(168,210,255,.82);display:block;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.1;
}
.hdr-new-btn {
    display:flex;align-items:center;gap:.38rem;
    background:rgba(59,130,246,.12);
    border:1px solid rgba(59,130,246,.35);
    color:#f0f4ff;padding:.3rem .65rem;border-radius:7px;
    font-size:.65rem;font-weight:700;letter-spacing:.05em;
    cursor:pointer;transition:all .2s;white-space:nowrap;
    font-family:'Nunito',sans-serif; flex-shrink:0;
}
.hdr-new-btn:hover {
    background:rgba(59,130,246,.25);
    border-color:rgba(59,130,246,.7);
    box-shadow:0 0 12px rgba(59,130,246,.28);
}

/* ─── FOOTER ─── */
.aana-footer {
    background:linear-gradient(135deg,#06101e,#0d1e3b 60%,#162b56);
    border-top:1px solid rgba(59,130,246,.16);
    padding:.35rem clamp(.75rem,3vw,1.5rem);
    text-align:center;position:fixed;bottom:0;left:0;right:0;
    z-index:9999;box-shadow:0 -4px 18px rgba(0,0,0,.45);line-height:1.2;
}
.ftr-copy{font-size:.6rem;color:rgba(240,244,255,.38);margin-bottom:.18rem;}
.ftr-dev{display:flex;align-items:center;justify-content:center;gap:.3rem;font-size:.68rem;color:rgba(240,244,255,.5);}
.ftr-heart{color:#ff6b8a;font-size:.9rem;animation:hb 1.4s ease-in-out infinite;}
@keyframes hb{0%,100%{transform:scale(1)}14%{transform:scale(1.38)}28%{transform:scale(1)}42%{transform:scale(1.22)}}
.ftr-name{color:#ffd84d;font-weight:800;letter-spacing:.03em;text-decoration:none;animation:nameGlow 2.5s ease-in-out infinite alternate;}
@keyframes nameGlow{0%{text-shadow:0 0 6px rgba(255,216,77,.7)}100%{text-shadow:0 0 12px #ffd84d,0 0 28px rgba(255,216,77,.7)}}

/* ─── SIDEBAR ─── */
section[data-testid="stSidebar"] {
    background:#0d1e3b !important;
    border-right:1px solid rgba(59,130,246,.2) !important;
}
section[data-testid="stSidebar"] > div { padding:1rem .85rem 7rem !important; }
section[data-testid="stSidebar"] * { color:#c9d1d9 !important; }
section[data-testid="stSidebar"] label {
    font-size:.72rem !important;letter-spacing:.07em;
    text-transform:uppercase;color:#6a85a8 !important;font-weight:700 !important;
}
section[data-testid="stSidebar"] .stTextInput input {
    background:#0c1625 !important;border:1px solid rgba(59,130,246,.3) !important;
    color:#f0f6fc !important;border-radius:8px !important;font-size:.85rem !important;
}
section[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background:#0c1625 !important;border-color:rgba(59,130,246,.3) !important;
    border-radius:8px !important;color:#f0f6fc !important;
}
section[data-testid="stSidebar"] [data-baseweb="menu"] { background:#0c1625 !important; }
section[data-testid="stSidebar"] [data-baseweb="option"] { background:#0c1625 !important; }
section[data-testid="stSidebar"] .stButton button {
    background:#1f6feb !important;border:none !important;
    color:#fff !important;border-radius:8px !important;
    font-weight:700 !important;font-size:.85rem !important;
}
section[data-testid="stSidebar"] .stButton button:hover { background:#388bfd !important; }
section[data-testid="stSidebar"] hr { border-color:rgba(59,130,246,.15) !important;margin:.6rem 0 !important; }
.sb-section {
    font-size:.7rem;letter-spacing:.08em;text-transform:uppercase;
    color:#4a6080 !important;font-weight:800;
    padding:.4rem 0 .2rem;border-bottom:1px solid rgba(59,130,246,.1);
    margin-bottom:.45rem;
}
.admin-badge {
    display:inline-flex;align-items:center;gap:.3rem;
    background:rgba(255,216,77,.12);border:1px solid rgba(255,216,77,.35);
    border-radius:20px;padding:.18rem .6rem;
    font-size:.68rem;color:#ffd84d;font-weight:700;
    letter-spacing:.05em;margin-bottom:.6rem;
}
.key-ok{color:#22c55e !important;font-size:.78rem;margin-top:.3rem;}
.key-fail{color:#ef4444 !important;font-size:.78rem;margin-top:.3rem;}

/* ─── MAIN CONTENT ─── */
.main-wrap {
    max-width:860px;margin:0 auto;
    padding:1.25rem 1.25rem 9rem;
}

/* ─── HERO CARD ─── */
.hero-card {
    background:linear-gradient(135deg,#06101e,#0d1e3b 55%,#162b56);
    border:1px solid rgba(59,130,246,.25);border-radius:18px;
    padding:2rem 1.75rem;text-align:center;margin-bottom:1.5rem;
    position:relative;overflow:hidden;
}
.hero-card::before {
    content:"";position:absolute;inset:0;
    background:radial-gradient(ellipse at 30% 50%,rgba(59,130,246,.08),transparent 60%);
    pointer-events:none;
}
.hero-avatar {
    width:72px;height:72px;border-radius:50%;object-fit:cover;
    border:3px solid rgba(59,130,246,.6);
    box-shadow:0 0 28px rgba(59,130,246,.4);
    margin:0 auto 1rem;display:block;
}
.hero-greeting {
    font-family:'Noto Sans Sinhala',sans-serif;
    font-size:1.12rem;font-weight:700;color:#9ecfff;margin-bottom:.5rem;
}
.hero-sub { font-size:.9rem;color:rgba(200,215,240,.8);line-height:1.65; }

/* ─── STATUS BAR ─── */
.status-bar {
    background:#fff;border:1px solid #e5e0d5;border-radius:10px;
    padding:.6rem 1rem;font-size:.82rem;color:#6b7280;
    margin-bottom:1.1rem;display:flex;align-items:center;
    gap:.6rem;flex-wrap:wrap;box-shadow:0 2px 8px rgba(0,0,0,.05);
}
.status-subject{font-weight:700;color:#1a1a2e;font-size:.88rem;}
.doc-tag {
    background:#eff6ff;border:1px solid #bfdbfe;color:#2563eb;
    border-radius:6px;font-size:.72rem;padding:2px 7px;
    white-space:nowrap;max-width:140px;overflow:hidden;
    text-overflow:ellipsis;display:inline-block;
}
.google-on-tag{background:#fef9ee;border:1px solid #fde68a;color:#92400e;border-radius:6px;font-size:.72rem;padding:2px 7px;}

/* ─── CHAT ─── */
[data-testid="stChatMessage"] { background:transparent !important;border:none !important;padding:.2rem 0 !important; }
[data-testid="stChatMessageContent"] {
    background:#fff !important;border:1px solid #e5e0d5 !important;
    border-radius:4px 14px 14px 14px !important;
    padding:.8rem 1rem !important;
    box-shadow:0 2px 8px rgba(0,0,0,.06) !important;
    color:#1a1a2e !important;font-size:.94rem !important;line-height:1.7 !important;
}

/* ─── GOOGLE HINT ─── */
.google-hint {
    background:#fffbeb;border:1px solid #fde68a;border-radius:12px;
    padding:.65rem .9rem;margin:.6rem 0;
    display:flex;align-items:flex-start;gap:.55rem;
}
.google-hint-text{font-size:.82rem;color:#78350f;line-height:1.5;}

/* ─── TOGGLE ─── */
section[data-testid="stSidebar"] [data-testid="stToggle"] label { text-transform:none !important; letter-spacing:0 !important; font-size:.84rem !important; }
</style>
""", unsafe_allow_html=True)


# ── Session state ──────────────────────────────────────────────────────────────
for k, v in [
    ("messages", []),
    ("current_subject_id", None),
    ("docs", {}),
    ("admin_logged_in", False),
    ("gemini_key", SHARED_GEMINI_KEY),
    ("key_status", None),
    ("google_search_enabled", False),
    ("greeted", False),
]:
    if k not in st.session_state:
        st.session_state[k] = v

# Pre-fill shared key
if not st.session_state.gemini_key and SHARED_GEMINI_KEY:
    st.session_state.gemini_key = SHARED_GEMINI_KEY


# ── Drive helpers ──────────────────────────────────────────────────────────────
DRIVE_API_URL = "https://www.googleapis.com/drive/v3/files"
FOLDER_MIME   = "application/vnd.google-apps.folder"

def list_folder(folder_id, api_key):
    folders, files = [], []
    page_token = None
    while True:
        params = {
            "q": f"'{folder_id}' in parents and trashed=false",
            "fields": "nextPageToken,files(id,name,mimeType)",
            "orderBy": "name", "pageSize": 100, "key": api_key,
        }
        if page_token:
            params["pageToken"] = page_token
        r = requests.get(DRIVE_API_URL, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise RuntimeError(data["error"].get("message", str(data["error"])))
        for f in data.get("files", []):
            (folders if f["mimeType"] == FOLDER_MIME else files).append((f["name"], f["id"]))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return folders, files


def download_file(file_id, api_key):
    session = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0"}
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media&key={api_key}"
    r   = session.get(url, headers=headers, timeout=40, allow_redirects=True)
    if r.status_code == 403 or len(r.content) < 100:
        url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t"
        r   = session.get(url, headers=headers, timeout=40, allow_redirects=True)
        if b"Virus scan warning" in r.content[:4000]:
            token = re.search(r'confirm=([0-9A-Za-z_\-]+)', r.text)
            uuid_ = re.search(r'uuid=([0-9A-Za-z_\-]+)', r.text)
            qs = (f"&confirm={token.group(1)}" if token else "") + (f"&uuid={uuid_.group(1)}" if uuid_ else "")
            r = session.get(f"https://drive.google.com/uc?export=download&id={file_id}{qs}", headers=headers, timeout=40)
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
            parts = [p.text for p in d.paragraphs]
            for table in d.tables:
                for row in table.rows:
                    parts.append(" | ".join(c.text for c in row.cells))
            return "\n".join(parts)
        elif ext == ".pptx":
            try:
                from pptx import Presentation
                prs = Presentation(io.BytesIO(file_bytes))
                return "\n".join(
                    shape.text for slide in prs.slides
                    for shape in slide.shapes if hasattr(shape, "text")
                )
            except ImportError:
                return "[Install python-pptx for PPTX support]"
        elif ext in (".xlsx", ".xls"):
            try:
                import openpyxl
                wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True)
                parts = []
                for ws in wb.worksheets:
                    for row in ws.iter_rows(values_only=True):
                        parts.append(" | ".join(str(c) for c in row if c is not None))
                return "\n".join(parts)
            except ImportError:
                return "[Install openpyxl for XLSX support]"
        elif ext in (".csv",):
            return file_bytes.decode("utf-8", errors="ignore")
        else:
            return file_bytes.decode("utf-8", errors="ignore")
    except Exception as e:
        return f"[Could not read {filename}: {e}]"


@st.cache_data(show_spinner=False, ttl=600)
def get_structure(root_id, api_key):
    tree = {}
    years, _ = list_folder(root_id, api_key)
    for yn, yi in years:
        tree[yn] = {}
        sems, _ = list_folder(yi, api_key)
        for sn, si in sems:
            tree[yn][sn] = {}
            subjects, _ = list_folder(si, api_key)
            for subj_n, subj_i in subjects:
                tree[yn][sn][subj_n] = subj_i
    return tree


@st.cache_data(show_spinner=False, ttl=300)
def load_subject_docs(subject_folder_id, api_key):
    _, files = list_folder(subject_folder_id, api_key)
    supported = {".pdf",".docx",".doc",".txt",".pptx",".xlsx",".xls",".md",".csv"}
    docs = {}
    for name, fid in files:
        if Path(name).suffix.lower() not in supported:
            continue
        try:
            raw  = download_file(fid, api_key)
            text = extract_text(raw, name)
            if text.strip():
                docs[name] = text
        except Exception:
            pass
    return docs


def validate_key(key):
    try:
        genai.configure(api_key=key)
        genai.GenerativeModel("gemini-2.5-flash").generate_content("Hi", request_options={"timeout": 10})
        return True
    except Exception:
        return False


def ask_gemini(api_key, question, docs, use_google=False):
    genai.configure(api_key=api_key)
    context = "\n\n".join(
        f"=== Document: {name} ===\n{text[:12000]}" for name, text in docs.items()
    ) if docs else ""
    google_note = "\nIf the notes don't have the answer, use Google Search to supplement — clearly label it as from web search." if use_google else ""
    prompt = f"""You are ආනා's AI study assistant for university students. Answer thoroughly and clearly.
Use headings and bullet points where helpful.
At the end always write: **Sources:** [doc names or "Google Search"]
If not found in docs and Google Search not enabled, say so and suggest enabling it.{google_note}

---DOCUMENTS---
{context if context else "(No documents loaded)"}
---END---

Student question: {question}"""
    try:
        if use_google:
            model = genai.GenerativeModel("gemini-2.5-flash", tools=[{"google_search": {}}])
        else:
            model = genai.GenerativeModel("gemini-2.5-flash")
        return model.generate_content(prompt).text
    except Exception:
        model = genai.GenerativeModel("gemini-2.5-flash")
        return model.generate_content(prompt).text


# ── HEADER ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="aana-header">
  <img src="{ADMIN_AVATAR_URL}" class="hdr-avatar" width="38" height="38" alt="ආනා"
       onerror="this.style.opacity='.3'">
  <div class="hdr-center">
    <div>
      <div class="hdr-title">
        <span class="hdr-sinhala">ආනාගේ</span>&nbsp;<span>AI</span>&nbsp;💡
      </div>
      <span class="hdr-sub">Himan Thathuwa Kethala Hiruwa</span>
    </div>
  </div>
  <button class="hdr-new-btn" onclick="window.location.reload()">✨ New Chat</button>
</div>
""", unsafe_allow_html=True)


# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("<div style='height:.2rem'></div>", unsafe_allow_html=True)

    # Admin login / panel
    if not st.session_state.admin_logged_in:
        st.markdown("<div class='sb-section'>🔐 Admin Login</div>", unsafe_allow_html=True)
        pwd = st.text_input("", type="password", placeholder="Admin password…",
                            key="admin_pwd_in", label_visibility="collapsed")
        if st.button("Login as Admin", use_container_width=True, key="admin_login_btn"):
            if pwd == ADMIN_PASSWORD:
                st.session_state.admin_logged_in = True
                st.rerun()
            else:
                st.error("Wrong password")
        st.markdown("<hr>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='admin-badge'>⭐ Admin Panel</div>", unsafe_allow_html=True)
        st.markdown("<div class='sb-section'>🔑 Gemini API Key</div>", unsafe_allow_html=True)

        key_val = st.text_input("", type="password", placeholder="AIza…",
                                 value=st.session_state.gemini_key,
                                 label_visibility="collapsed", key="gemini_key_in")
        if key_val != st.session_state.gemini_key:
            st.session_state.gemini_key = key_val
            st.session_state.key_status = None

        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Test Key", use_container_width=True, key="test_key_btn"):
                if st.session_state.gemini_key:
                    with st.spinner("Checking…"):
                        ok = validate_key(st.session_state.gemini_key)
                    st.session_state.key_status = "ok" if ok else "fail"
                else:
                    st.warning("Enter a key first")
        with c2:
            if st.button("🚪 Logout", use_container_width=True, key="logout_btn"):
                st.session_state.admin_logged_in = False
                st.rerun()

        if st.session_state.key_status == "ok":
            st.markdown("<div class='key-ok'>✅ Key is valid and working!</div>", unsafe_allow_html=True)
        elif st.session_state.key_status == "fail":
            st.markdown("<div class='key-fail'>❌ Key invalid or quota exceeded</div>", unsafe_allow_html=True)

        st.markdown(
            "<small style='color:#3a5070'>Get free key → <a href='https://aistudio.google.com/app/apikey' style='color:#58a6ff'>aistudio.google.com</a></small>",
            unsafe_allow_html=True,
        )
        st.markdown("<hr>", unsafe_allow_html=True)

    # Subject selector
    st.markdown("<div class='sb-section'>📂 Your Subject</div>", unsafe_allow_html=True)

    if not DRIVE_API_KEY or not ROOT_FOLDER_ID:
        st.error("Drive secrets not configured.")
        st.stop()

    with st.spinner("Loading folders…"):
        try:
            structure = get_structure(ROOT_FOLDER_ID, DRIVE_API_KEY)
        except Exception as e:
            st.error(f"Drive error: {e}")
            st.stop()

    if not structure:
        st.warning("No folders found in Drive.")
        st.stop()

    year_choice = st.selectbox("Year", list(structure.keys()))
    sem_choice  = st.selectbox("Semester", list(structure[year_choice].keys()))
    subjects    = structure[year_choice][sem_choice]
    if not subjects:
        st.warning("No subject folders in this semester.")
        st.stop()

    subj_choice = st.selectbox("Subject", list(subjects.keys()))
    subj_id     = subjects[subj_choice]

    if subj_id != st.session_state.current_subject_id:
        st.session_state.messages           = []
        st.session_state.current_subject_id = subj_id
        st.session_state.docs               = {}
        st.session_state.greeted            = False

    st.markdown("<div style='height:5px'></div>", unsafe_allow_html=True)
    load_btn = st.button("📥 Load Subject Docs", use_container_width=True, key="load_docs_btn")

    # Google search toggle
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("<div class='sb-section'>🌐 Google Search</div>", unsafe_allow_html=True)
    google_on = st.toggle("Enable Google Search", value=st.session_state.google_search_enabled)
    if google_on != st.session_state.google_search_enabled:
        st.session_state.google_search_enabled = google_on
    if google_on:
        st.markdown(
            "<small style='color:#c9a830'>⚠️ Google may enhance answers beyond your notes.</small>",
            unsafe_allow_html=True,
        )

    st.markdown("<hr>", unsafe_allow_html=True)
    if st.button("✨ New Chat", use_container_width=True, key="new_chat_btn"):
        st.session_state.messages = []
        st.session_state.greeted  = False
        st.rerun()
    if st.button("🗑️ Clear Chat", use_container_width=True, key="clear_chat_btn"):
        st.session_state.messages = []
        st.session_state.greeted  = False
        st.rerun()

    st.markdown(
        "<small style='color:#2d4060'>Supports PDF, DOCX, PPTX, XLSX, TXT, CSV, MD</small>",
        unsafe_allow_html=True,
    )


# ── Load docs ──────────────────────────────────────────────────────────────────
if load_btn:
    with st.spinner(f"Loading {subj_choice} docs…"):
        st.session_state.docs   = load_subject_docs(subj_id, DRIVE_API_KEY)
        st.session_state.greeted = False
    if not st.session_state.docs:
        st.warning("No readable files found in this subject folder.")

docs = st.session_state.docs


# ── MAIN CONTENT ──────────────────────────────────────────────────────────────
st.markdown("<div class='main-wrap'>", unsafe_allow_html=True)

if not docs:
    # Welcome hero — no docs loaded
    st.markdown(f"""
    <div class="hero-card">
      <img src="{ADMIN_AVATAR_URL}" class="hero-avatar" alt="ආනා"
           onerror="this.style.display='none'">
      <div class="hero-greeting">හෙලෝ! 👋 ආනාගේ AI වෙත සාදරයෙන් පිළිගනිමු!</div>
      <div class="hero-sub">
        ← Subject එකක් select කරල <strong>Load Subject Docs</strong> click කරන්න.<br>
        ඊට පස්සේ ඕන ප්‍රශ්නයක් අහන්න.
      </div>
    </div>
    """, unsafe_allow_html=True)
else:
    # Status bar
    doc_names = list(docs.keys())
    tags = "".join(f"<span class='doc-tag' title='{n}'>{n}</span>" for n in doc_names[:4])
    if len(doc_names) > 4:
        tags += f"<span class='doc-tag'>+{len(doc_names)-4} more</span>"
    gtag = "<span class='google-on-tag'>🌐 Google ON</span>" if st.session_state.google_search_enabled else ""
    st.markdown(f"""
    <div class="status-bar">
      📂 <span class="status-subject">{subj_choice}</span>
      <span style="color:#ddd">|</span>
      <span>{len(doc_names)} file{'s' if len(doc_names)!=1 else ''}</span>
      <span style="color:#ddd">|</span>
      {tags} {gtag}
    </div>
    """, unsafe_allow_html=True)

    # Greeting
    if not st.session_state.greeted:
        st.session_state.messages.insert(0, {
            "role": "assistant",
            "content": f"""හෙලෝ සුද්දා, කෝමද, සැපේද ඉන්නේ..? 😊

You can now ask any question regarding the uploaded notes of **{subj_choice}**.

> 💡 Can't find your answer? Simply enable **Google Search** in the sidebar!""",
        })
        st.session_state.greeted = True

    # Chat history
    for msg in st.session_state.messages:
        if msg["role"] == "assistant":
            with st.chat_message("AI ආනා", avatar=ADMIN_AVATAR_URL):
                st.markdown(msg["content"])
        else:
            with st.chat_message("user"):
                st.markdown(msg["content"])

    # Google search nudge
    if (st.session_state.messages and not st.session_state.google_search_enabled):
        last = st.session_state.messages[-1]
        triggers = ["not in the documents", "cannot find", "enable google", "not found in"]
        if last["role"] == "assistant" and any(t in last["content"].lower() for t in triggers):
            st.markdown("""
            <div class="google-hint">
              <span>🌐</span>
              <span class="google-hint-text">
                Can't find the answer in your notes?
                Enable <strong>Google Search</strong> in the sidebar to search the web!
              </span>
            </div>
            """, unsafe_allow_html=True)

    # Chat input
    question = st.chat_input(f"Ask about {subj_choice}…")
    if question:
        api_key = st.session_state.gemini_key or SHARED_GEMINI_KEY
        if not api_key:
            st.error("⚠️ No Gemini API key. Login as admin to configure one.")
        else:
            st.session_state.messages.append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)
            with st.chat_message("AI ආනා", avatar=ADMIN_AVATAR_URL):
                with st.spinner("ආනා හිතනවා… 🤔"):
                    try:
                        answer = ask_gemini(api_key, question, docs,
                                            use_google=st.session_state.google_search_enabled)
                        st.markdown(answer)
                        st.session_state.messages.append({"role": "assistant", "content": answer})
                    except Exception as e:
                        err = str(e)
                        if "API_KEY_INVALID" in err or "invalid" in err.lower():
                            st.error("❌ Invalid Gemini API key.")
                        elif "429" in err or "quota" in err.lower():
                            st.error("❌ API quota exceeded. Try a different key.")
                        else:
                            st.error(f"Error: {err}")

st.markdown("</div>", unsafe_allow_html=True)

# ── FOOTER ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="aana-footer">
  <div class="ftr-copy">© 2025 All Rights Reserved</div>
  <div class="ftr-dev">
    Developed with <span class="ftr-heart">❤️</span>
    <a class="ftr-name" href="https://venurakabojithananda.github.io/" target="_blank" rel="noopener">DSVB</a>
  </div>
</div>
""", unsafe_allow_html=True)
