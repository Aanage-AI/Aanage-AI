"""
ආනාගේ AI — StudyMate
Rebuilt with native Streamlit widgets only — no broken JS/HTML tricks.
All interactivity via st.session_state + Streamlit native components.
"""

import io
import re
import base64
import hashlib
import json
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
    initial_sidebar_state="expanded",
)

# ── Load external CSS ──────────────────────────────────────────────────────────
CSS_PATH = Path(__file__).parent / "style.css"
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

# ── Secrets ────────────────────────────────────────────────────────────────────
ROOT_FOLDER_ID  = st.secrets.get("DRIVE_ROOT_FOLDER_ID", "")
DRIVE_API_KEY   = st.secrets.get("GOOGLE_DRIVE_API_KEY", "")
ADMIN_EMAIL     = st.secrets.get("ADMIN_EMAIL", "admin@aana.lk")
ADMIN_PASS_HASH = st.secrets.get(
    "ADMIN_PASS_HASH",
    hashlib.sha256("aana@2025!".encode()).hexdigest()
)

# ── Session state defaults ─────────────────────────────────────────────────────
DEFAULTS = {
    "messages": [],
    "current_subject_id": None,
    "docs": {},
    "subject_name": "",
    "google_search": False,
    "admin_logged_in": False,
    "gemini_key": "",
    "api_key_status": None,
    "free_api_keys": [],
    "api_usage_today": {},
    "usage_date": str(datetime.date.today()),
    "greeting_shown": False,
    "show_free_keys": False,
    "show_admin": False,
    "show_about": False,
    "admin_email_input": "",
    "admin_pass_input": "",
    "admin_login_error": False,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Reset daily usage counter
today = str(datetime.date.today())
if st.session_state.usage_date != today:
    st.session_state.api_usage_today = {}
    st.session_state.usage_date = today

# ── Google Drive helpers ───────────────────────────────────────────────────────
DRIVE_API_BASE = "https://www.googleapis.com/drive/v3/files"
FOLDER_MIME    = "application/vnd.google-apps.folder"

def list_folder(folder_id, api_key):
    folders, files = [], []
    page_token = None
    while True:
        params = {
            "q": f"'{folder_id}' in parents and trashed=false",
            "fields": "nextPageToken,files(id,name,mimeType)",
            "orderBy": "name",
            "pageSize": 100,
            "key": api_key,
        }
        if page_token:
            params["pageToken"] = page_token
        r = requests.get(DRIVE_API_BASE, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise RuntimeError(data["error"].get("message", str(data["error"])))
        for f in data.get("files", []):
            if f["mimeType"] == FOLDER_MIME:
                folders.append((f["name"], f["id"]))
            else:
                files.append((f["name"], f["id"]))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return folders, files

def download_file(file_id, api_key):
    session = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0"}
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media&key={api_key}"
    r = session.get(url, headers=headers, timeout=40, allow_redirects=True)
    if r.status_code == 403 or len(r.content) < 100:
        url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t"
        r = session.get(url, headers=headers, timeout=40, allow_redirects=True)
        if b"Virus scan warning" in r.content[:4000]:
            token = re.search(r'confirm=([0-9A-Za-z_\-]+)', r.text)
            uuid  = re.search(r'uuid=([0-9A-Za-z_\-]+)', r.text)
            qs = f"&confirm={token.group(1)}" if token else ""
            qs += f"&uuid={uuid.group(1)}" if uuid else ""
            r = session.get(
                f"https://drive.google.com/uc?export=download&id={file_id}{qs}",
                headers=headers, timeout=40
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
        elif ext == ".pptx":
            try:
                from pptx import Presentation
                prs = Presentation(io.BytesIO(file_bytes))
                return "\n".join(
                    shape.text for slide in prs.slides
                    for shape in slide.shapes if hasattr(shape, "text")
                )
            except ImportError:
                return "[PPTX support requires python-pptx]"
        elif ext in (".xlsx", ".xls"):
            try:
                import openpyxl
                wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
                return "\n".join(
                    "\t".join(str(c) if c is not None else "" for c in row)
                    for ws in wb.worksheets for row in ws.iter_rows(values_only=True)
                )
            except ImportError:
                return "[XLSX support requires openpyxl]"
        elif ext in (".txt", ".md", ".csv", ".json"):
            return file_bytes.decode("utf-8", errors="ignore")
        else:
            decoded = file_bytes.decode("utf-8", errors="ignore")
            return decoded if decoded.strip() else f"[Unsupported: {ext}]"
    except Exception as e:
        return f"[Could not read {filename}: {e}]"

@st.cache_data(show_spinner=False, ttl=600)
def get_structure(root_id, api_key):
    tree = {}
    years, _ = list_folder(root_id, api_key)
    for year_name, year_id in years:
        tree[year_name] = {}
        sems, _ = list_folder(year_id, api_key)
        for sem_name, sem_id in sems:
            tree[year_name][sem_name] = {}
            subjects, _ = list_folder(sem_id, api_key)
            for subj_name, subj_id in subjects:
                tree[year_name][sem_name][subj_name] = subj_id
    return tree

@st.cache_data(show_spinner=False, ttl=300)
def load_subject_docs(subject_folder_id, api_key):
    SUPPORTED = {".pdf", ".docx", ".doc", ".txt", ".md", ".csv",
                 ".json", ".pptx", ".xlsx", ".xls"}
    _, files = list_folder(subject_folder_id, api_key)
    docs = {}
    for name, fid in files:
        if Path(name).suffix.lower() not in SUPPORTED:
            continue
        try:
            raw  = download_file(fid, api_key)
            text = extract_text(raw, name)
            if text.strip():
                docs[name] = text
        except Exception:
            pass
    return docs

# ── Gemini ─────────────────────────────────────────────────────────────────────
def check_api_key(key):
    try:
        genai.configure(api_key=key)
        m = genai.GenerativeModel("gemini-2.5-flash")
        m.generate_content("Hi")
        return True
    except Exception:
        return False

def ask_gemini(gemini_key, question, docs, use_google=False):
    genai.configure(api_key=gemini_key)
    context = "\n\n".join(
        f"=== Document: {name} ===\n{text[:12000]}"
        for name, text in docs.items()
    )
    note_prompt = f"""You are AI ආනා, a friendly Sri Lankan university study assistant.
Answer using the provided documents. Be thorough and clear.
Format in clear paragraphs. Use bullet points where helpful.
At the very end write: **Sources:** [Doc Name]
If the answer is not in the documents, say so and suggest enabling Google Search.

---DOCUMENTS---
{context}
---END---

Student question: {question}"""

    google_prompt = f"""You are AI ආනා, a friendly Sri Lankan university study assistant.
First check the provided documents. If the answer isn't fully there, supplement with web knowledge.
Format in clear paragraphs. Cite sources where possible.

---DOCUMENTS---
{context}
---END---

Student question: {question}"""

    prompt = google_prompt if use_google else note_prompt
    if use_google:
        model = genai.GenerativeModel("gemini-2.5-flash", tools="google_search_retrieval")
    else:
        model = genai.GenerativeModel("gemini-2.5-flash")
    try:
        return model.generate_content(prompt).text
    except Exception:
        return genai.GenerativeModel("gemini-2.5-flash").generate_content(note_prompt).text

def track_usage(key):
    k = key[:8] + "…"
    st.session_state.api_usage_today[k] = st.session_state.api_usage_today.get(k, 0) + 1

def get_usage(key):
    return st.session_state.api_usage_today.get(key[:8] + "…", 0)

# ── Image helper ───────────────────────────────────────────────────────────────
def img_b64(path_str):
    p = Path(path_str)
    if p.exists():
        ext = p.suffix.lstrip(".")
        return f"data:image/{ext};base64,{base64.b64encode(p.read_bytes()).decode()}"
    return ""

ADMIN_IMG_PATH = Path(__file__).parent / "assets" / "admin" / "admin.jpg"
ADMIN_IMG_SRC  = img_b64(ADMIN_IMG_PATH) or "https://ui-avatars.com/api/?name=AI&background=162b56&color=9ecfff&size=90"

# ══════════════════════════════════════════════════════════════════════════════
#   HIDE STREAMLIT CHROME (manage app, toolbar, deploy button, etc.)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
#MainMenu { visibility: hidden !important; }
header[data-testid="stHeader"] { display: none !important; }
footer { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }
[data-testid="manage-app-button"] { display: none !important; }
.stDeployButton { display: none !important; }
button[title="View app in Streamlit Community Cloud"] { display: none !important; }
[data-testid="stStatusWidget"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#   HEADER  (pure HTML for visual only — no JS interactivity needed here)
# ══════════════════════════════════════════════════════════════════════════════
google_badge = "🟢 Google ON" if st.session_state.google_search else "⚪ Google OFF"
admin_label  = "🔓 Logged In" if st.session_state.admin_logged_in else "🔐 Admin"

st.markdown(f"""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<div class="aana-header">
  <div class="hdr-left">
    <div class="hdr-avatar-wrap">
      <img src="{ADMIN_IMG_SRC}" alt="ආනා" class="hdr-avatar"
           onerror="this.src='https://ui-avatars.com/api/?name=AI&background=162b56&color=9ecfff&size=38'">
    </div>
    <div class="hdr-title-wrap">
      <div class="hdr-brand">
        <span class="hdr-sinhala">ආනාගේ</span>
        <span class="hdr-ai-text">&nbsp;AI</span>
      </div>
      <span class="hdr-sub">Himan Thathuwa Kethala Hiruwa</span>
    </div>
  </div>
  <div class="hdr-right-info">
    <span class="hdr-google-badge {'active' if st.session_state.google_search else ''}">{google_badge}</span>
    <span class="hdr-admin-badge">{admin_label}</span>
  </div>
</div>
<div class="hdr-shimmer-line"></div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#   CHECK SECRETS
# ══════════════════════════════════════════════════════════════════════════════
if not DRIVE_API_KEY or not ROOT_FOLDER_ID:
    st.error("⚠️ DRIVE_ROOT_FOLDER_ID and GOOGLE_DRIVE_API_KEY must be set in Streamlit secrets.")
    st.stop()

# ══════════════════════════════════════════════════════════════════════════════
#   SIDEBAR — all native Streamlit widgets
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown('<div class="sb-header">ආනාගේ AI</div>', unsafe_allow_html=True)

    # ── Free API keys hint ──────────────────────────────────────────────────
    if st.button("🔑 තාමත් API Key එකක් නැද්ද..?", use_container_width=True, key="btn_freekeys"):
        st.session_state.show_free_keys = not st.session_state.show_free_keys

    if st.session_state.show_free_keys:
        with st.container():
            st.markdown('<div class="fk-warn-box">', unsafe_allow_html=True)
            st.markdown("""
**මෙවුවා හැමෝම use කරනවා limit වැදිලා ඇති සමහරවිට 😠**

Video එක බලලා තමන්ටම කියලා එකක් හදාගනිං API හිඟන්නා 😤
""")
            st.markdown(f'📺 [How to get your free API key](https://youtu.be/YOUR_VIDEO_LINK_HERE)', unsafe_allow_html=False)

            free_keys = st.session_state.free_api_keys
            if free_keys:
                for k in free_keys:
                    usage = get_usage(k)
                    masked = k[:12] + "…" + k[-4:] if len(k) > 18 else k
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.code(masked, language=None)
                    with col2:
                        if st.button("📋", key=f"copy_{k[:8]}", help="Copy key"):
                            st.write(f"`{k}`")
                    st.caption(f"Used {usage}× today")
            else:
                st.caption("No free keys added yet. Admin can add them.")
            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")

    # ── API Key section ─────────────────────────────────────────────────────
    st.markdown('<div class="sb-section-title">🔑 Gemini API Key</div>', unsafe_allow_html=True)
    api_key_input = st.text_input(
        "API Key",
        value=st.session_state.gemini_key,
        type="password",
        placeholder="AIza...",
        label_visibility="collapsed",
        key="api_key_field"
    )
    if api_key_input != st.session_state.gemini_key:
        st.session_state.gemini_key = api_key_input
        st.session_state.api_key_status = None

    col_check, col_link = st.columns([1, 1])
    with col_check:
        if st.button("✓ Check Key", use_container_width=True, key="btn_check_key"):
            if st.session_state.gemini_key:
                with st.spinner("Checking…"):
                    ok = check_api_key(st.session_state.gemini_key)
                st.session_state.api_key_status = "ok" if ok else "err"
            else:
                st.warning("Paste your key first!")
    with col_link:
        st.markdown('[Get free key ↗](https://aistudio.google.com/app/apikey)', unsafe_allow_html=False)

    if st.session_state.api_key_status == "ok":
        st.success("✅ API key valid!")
    elif st.session_state.api_key_status == "err":
        st.error("❌ Invalid key — try another")

    st.markdown("---")

    # ── Google Search toggle ────────────────────────────────────────────────
    st.markdown('<div class="sb-section-title">🌐 Google Search</div>', unsafe_allow_html=True)
    google_on = st.toggle(
        "Enable Google Search",
        value=st.session_state.google_search,
        key="google_toggle",
        help="When ON, AI may search the web if notes don't have the answer"
    )
    if google_on != st.session_state.google_search:
        st.session_state.google_search = google_on
        st.rerun()
    if st.session_state.google_search:
        st.caption("🌐 Google may enhance your answers — results may vary")

    st.markdown("---")

    # ── Subject tree ────────────────────────────────────────────────────────
    st.markdown('<div class="sb-section-title">📂 Select Subject</div>', unsafe_allow_html=True)

    try:
        structure = get_structure(ROOT_FOLDER_ID, DRIVE_API_KEY)
    except Exception as e:
        st.error(f"Drive API error: {e}")
        st.stop()

    selected_id   = None
    selected_name = None

    for yi, (year_name, sems) in enumerate(structure.items()):
        with st.expander(f"🎓 {year_name}", expanded=(yi == 0)):
            for si, (sem_name, subjects) in enumerate(sems.items()):
                with st.expander(f"📖 {sem_name}", expanded=False):
                    for subj_name, subj_id in subjects.items():
                        is_selected = subj_id == st.session_state.current_subject_id
                        btn_label = f"{'✅ ' if is_selected else ''}{subj_name}"
                        if st.button(btn_label, key=f"subj_{subj_id}", use_container_width=True):
                            selected_id   = subj_id
                            selected_name = subj_name

    # Handle subject selection
    if selected_id and selected_id != st.session_state.current_subject_id:
        st.session_state.current_subject_id = selected_id
        st.session_state.subject_name = selected_name
        st.session_state.docs = {}
        st.session_state.messages = []
        st.session_state.greeting_shown = False
        st.rerun()

    st.markdown("---")

    # ── Load / New Chat buttons ─────────────────────────────────────────────
    if st.session_state.current_subject_id:
        st.markdown(f'<div class="selected-subject-info">📂 {st.session_state.subject_name}</div>', unsafe_allow_html=True)

        if st.button("⬇️ Load Subject Docs", use_container_width=True, type="primary", key="btn_load"):
            with st.spinner(f"Loading docs for {st.session_state.subject_name}…"):
                st.session_state.docs = load_subject_docs(
                    st.session_state.current_subject_id, DRIVE_API_KEY
                )
                st.session_state.messages = []
                st.session_state.greeting_shown = False
            st.rerun()

    if st.session_state.messages:
        if st.button("💬 New Chat", use_container_width=True, key="btn_new_chat"):
            st.session_state.messages = []
            st.session_state.greeting_shown = False
            st.rerun()

    st.markdown("---")

    # ── Admin section ───────────────────────────────────────────────────────
    if not st.session_state.admin_logged_in:
        if st.button("🔐 Admin Login", use_container_width=True, key="btn_admin"):
            st.session_state.show_admin = not st.session_state.show_admin

        if st.session_state.show_admin:
            with st.form("admin_login_form"):
                email_in = st.text_input("Email", placeholder="admin@aana.lk")
                pass_in  = st.text_input("Password", type="password", placeholder="Password")
                submitted = st.form_submit_button("Login", use_container_width=True)
                if submitted:
                    h = hashlib.sha256(pass_in.encode()).hexdigest()
                    if email_in == ADMIN_EMAIL and h == ADMIN_PASS_HASH:
                        st.session_state.admin_logged_in = True
                        st.session_state.show_admin = False
                        st.rerun()
                    else:
                        st.error("❌ Invalid credentials")
    else:
        st.markdown('<div class="admin-badge">⚙️ Admin Mode</div>', unsafe_allow_html=True)
        st.markdown('<div class="sb-section-title">Free API Keys</div>', unsafe_allow_html=True)

        for i, k in enumerate(st.session_state.free_api_keys):
            c1, c2 = st.columns([4, 1])
            with c1:
                new_val = st.text_input(f"Key {i+1}", value=k, key=f"adm_key_{i}", label_visibility="collapsed")
                if new_val != k:
                    st.session_state.free_api_keys[i] = new_val
            with c2:
                if st.button("🗑️", key=f"adm_del_{i}", help="Remove"):
                    st.session_state.free_api_keys.pop(i)
                    st.rerun()

        if st.button("➕ Add API Key", use_container_width=True, key="btn_add_key"):
            st.session_state.free_api_keys.append("")
            st.rerun()

        if st.button("🔓 Logout Admin", use_container_width=True, key="btn_admin_logout"):
            st.session_state.admin_logged_in = False
            st.rerun()

    st.markdown('<div class="sb-footer-note">Docs refresh every 5 min.<br>Drop new files in Drive anytime.</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#   MAIN CHAT AREA
# ══════════════════════════════════════════════════════════════════════════════
docs      = st.session_state.docs
subj_name = st.session_state.subject_name

if not docs:
    if not st.session_state.current_subject_id:
        # Landing hero
        st.markdown(f"""
        <div class="hero-wrap">
          <div class="hero-avatar-wrap">
            <img src="{ADMIN_IMG_SRC}" alt="AI ආනා" class="hero-avatar">
          </div>
          <div class="hero-title">ආනාගේ <span class="hero-ai">AI</span></div>
          <div class="hero-sub">ඔබේ lecture notes ගැන ඕනෙ ප්‍රශ්නයක් අහන්නකෝ..! 🎓</div>
          <div class="hero-steps">
            <div class="hero-step"><span class="hero-step-num">1</span>API Key paste කරන්න</div>
            <div class="hero-step"><span class="hero-step-num">2</span>Subject select කරන්න</div>
            <div class="hero-step"><span class="hero-step-num">3</span>Load කරලා අහන්න</div>
          </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="load-banner">
          <div class="lb-icon">📂</div>
          <div class="lb-title">Load Subject Docs</div>
          <div class="lb-sub"><strong>{subj_name}</strong> select කරලා තියෙනවා.<br>
          Sidebar එකේ <strong>⬇️ Load Subject Docs</strong> button එක press කරන්නකෝ!</div>
        </div>
        """, unsafe_allow_html=True)
else:
    # Status bar
    doc_names = list(docs.keys())
    gsearch_badge = " &nbsp;🌐 Google ON" if st.session_state.google_search else ""
    tags_html = " &nbsp;".join(
        f'<span class="doc-tag">{n}</span>' for n in doc_names[:4]
    )
    if len(doc_names) > 4:
        tags_html += f' <span class="doc-tag">+{len(doc_names)-4} more</span>'
    st.markdown(f"""
    <div class="status-bar">
      <span>📂 <strong>{subj_name}</strong></span>
      <span class="status-sep">|</span>
      <span>{len(doc_names)} doc{'s' if len(doc_names)!=1 else ''}</span>
      <span class="status-sep">|</span>
      {tags_html}
      <span class="gsearch-badge">{gsearch_badge}</span>
    </div>
    """, unsafe_allow_html=True)

    # Greeting
    if not st.session_state.greeting_shown:
        greeting = (
            "හෙලෝ සුද්දා, කෝමද, සැපේද ඉන්නේ..? 😊\n\n"
            f"You can now ask any question regarding the uploaded notes of **{subj_name}**.. "
            "Can't find your answer? Simply enable Google Search 🌐 in the sidebar!"
        )
        st.session_state.messages = [{"role": "assistant", "content": greeting, "is_greeting": True}]
        st.session_state.greeting_shown = True

    # Render messages
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("assistant", avatar=ADMIN_IMG_SRC if ADMIN_IMG_PATH.exists() else "🤖"):
                st.markdown(msg["content"])

                # Suggest Google Search if answer not found
                if (not st.session_state.google_search
                        and not msg.get("is_greeting")
                        and any(x in msg["content"].lower() for x in [
                            "not in the documents", "not found", "cannot find",
                            "no information", "document doesn't", "isn't in"
                        ])):
                    if st.button("🌐 Enable Google Search for a better answer",
                                 key=f"gs_suggest_{msg['content'][:20]}"):
                        st.session_state.google_search = True
                        st.rerun()

    # Display AI name below avatar
    st.markdown(f"""
    <style>
    [data-testid="stChatMessageContent"] + * {{ font-size: .7rem; color: #58a6ff; }}
    </style>
    """, unsafe_allow_html=True)

    # Chat input
    if question := st.chat_input(f"Ask about {subj_name}…"):
        key = st.session_state.gemini_key
        if not key:
            st.error("⚠️ Sidebar-ලා API key paste කරන්නකෝ first!")
        else:
            st.session_state.messages.append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)

            with st.chat_message("assistant", avatar=ADMIN_IMG_SRC if ADMIN_IMG_PATH.exists() else "🤖"):
                if st.session_state.google_search:
                    st.caption("🌐 Google Search enabled — may enhance your answer")
                with st.spinner("AI ආනා thinking… 🤔"):
                    try:
                        answer = ask_gemini(key, question, docs, st.session_state.google_search)
                        track_usage(key)
                        st.session_state.messages.append({"role": "assistant", "content": answer})
                        st.markdown(answer)
                        st.rerun()
                    except Exception as e:
                        err = str(e)
                        if "API_KEY_INVALID" in err or "invalid" in err.lower():
                            st.error("❌ Invalid Gemini API key. Get a free one at aistudio.google.com")
                            st.session_state.api_key_status = "err"
                        else:
                            st.error(f"Gemini error: {err}")

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="aana-footer">
  <div class="ftr-copy">© 2025 All Rights Reserved</div>
  <div class="ftr-dev">
    Developed with <span class="ftr-heart">❤️</span>
    <a class="ftr-name" href="https://venurakabojithananda.github.io/" rel="noopener" target="_blank">DSVB</a>
  </div>
</div>
""", unsafe_allow_html=True)
