"""
ආනාගේ AI — StudyMate
Premium rebuild — SVG icons, sticky footer, sidebar always visible.
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
    initial_sidebar_state="expanded",
    menu_items={},
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
    "admin_login_error": False,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

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

@st.cache_data(show_spinner=False, ttl=1800)
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

@st.cache_data(show_spinner=False, ttl=600)
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

# ── SVG icon helpers ───────────────────────────────────────────────────────────
def ico(path, size=14, color="currentColor"):
    """Return inline SVG for Lucide-style icons."""
    icons = {
        "key":      '<path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0 3 3L22 7l-3-3m-3.5 3.5L19 4"/>', 
        "check":    '<path d="M20 6 9 17l-5-5"/>',
        "search":   '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
        "folder":   '<path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2z"/>',
        "book":     '<path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/>', 
        "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>',
        "chat":     '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
        "lock":     '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
        "unlock":   '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/>',
        "trash":    '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>',
        "plus":     '<path d="M5 12h14"/><path d="M12 5v14"/>',
        "copy":     '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
        "globe":    '<circle cx="12" cy="12" r="10"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/><path d="M2 12h20"/>',
        "settings": '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
        "video":    '<polygon points="23 7 16 12 23 17 23 7"/><rect width="15" height="14" x="1" y="5" rx="2" ry="2"/>',
        "star":     '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
    }
    svg_content = icons.get(path, '<circle cx="12" cy="12" r="5"/>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{svg_content}</svg>'

def sb_btn_label(icon_name, text, color="rgba(184,196,216,.8)"):
    return f'{ico(icon_name, 13, color)}&nbsp;&nbsp;{text}'

# ══════════════════════════════════════════════════════════════════════════════
#   HIDE STREAMLIT CHROME (but NOT sidebar collapse)
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
[data-testid="stDecoration"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#   HEADER
# ══════════════════════════════════════════════════════════════════════════════
google_active = st.session_state.google_search
admin_in      = st.session_state.admin_logged_in

google_icon = ico("globe", 12, "#4ade80" if google_active else "rgba(255,255,255,.35)")
google_txt  = "Google ON" if google_active else "Google OFF"
admin_icon  = ico("unlock" if admin_in else "lock", 12, "#e8c840")
admin_txt   = "Logged In" if admin_in else "Admin"

st.markdown(f"""
<div class="aana-header">
  <div class="hdr-left">
    <div class="hdr-avatar-wrap">
      <img src="{ADMIN_IMG_SRC}" alt="ආනා" class="hdr-avatar"
           onerror="this.src='https://ui-avatars.com/api/?name=AI&background=0f1628&color=3b82f6&size=38'">
    </div>
    <div class="hdr-title-wrap">
      <div class="hdr-brand">
        <span class="hdr-sinhala">ආනාගේ</span>
        <span class="hdr-ai-text">&nbsp;AI</span>
      </div>
      <span class="hdr-sub">Himan Thathuwa Kethala Hiruwa</span>
    </div>
  </div>
  <div class="hdr-right">
    <span class="hdr-pill hdr-pill-google {'active' if google_active else ''}">{google_icon}&nbsp;{google_txt}</span>
    <span class="hdr-pill hdr-pill-admin">{admin_icon}&nbsp;{admin_txt}</span>
  </div>
</div>
<div class="hdr-shimmer"></div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#   CHECK SECRETS
# ══════════════════════════════════════════════════════════════════════════════
if not DRIVE_API_KEY or not ROOT_FOLDER_ID:
    st.error("⚠️ DRIVE_ROOT_FOLDER_ID and GOOGLE_DRIVE_API_KEY must be set in Streamlit secrets.")
    st.stop()

# ══════════════════════════════════════════════════════════════════════════════
#   SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown('<div class="sb-brand"><span class="sb-brand-sinhala">ආනාගේ</span><span class="sb-brand-ai">&nbsp;AI</span></div>', unsafe_allow_html=True)

    # ── Free API keys ───────────────────────────────────────────────────────
    if st.button("🔑 API Key නැද්ද..?", use_container_width=True, key="btn_freekeys"):
        st.session_state.show_free_keys = not st.session_state.show_free_keys

    if st.session_state.show_free_keys:
        st.markdown('<div class="fk-warn-box">', unsafe_allow_html=True)
        st.markdown("**මෙවුවා හැමෝම use කරනවා — limit වැදිලා ඇති** 😤\n\nVideo බලලා තමන්ගේ key හදාගනිං:")
        st.markdown(f'[{ico("video",12,"#58a6ff")}&nbsp; How to get your free API key](https://youtu.be/YOUR_VIDEO_LINK_HERE)', unsafe_allow_html=False)
        free_keys = st.session_state.free_api_keys
        if free_keys:
            for k in free_keys:
                masked = k[:12] + "…" + k[-4:] if len(k) > 18 else k
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.code(masked, language=None)
                with col2:
                    if st.button("📋", key=f"copy_{k[:8]}", help="Copy key"):
                        st.write(f"`{k}`")
                st.caption(f"Used {get_usage(k)}× today")
        else:
            st.caption("No free keys yet. Admin can add them.")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sb-divider"></div>', unsafe_allow_html=True)

    # ── API Key ─────────────────────────────────────────────────────────────
    st.markdown(f'<div class="sb-label">{ico("key",11,"#58a6ff")}&nbsp; Gemini API Key</div>', unsafe_allow_html=True)
    api_key_input = st.text_input(
        "API Key", value=st.session_state.gemini_key,
        type="password", placeholder="AIza…",
        label_visibility="collapsed", key="api_key_field"
    )
    if api_key_input != st.session_state.gemini_key:
        st.session_state.gemini_key = api_key_input
        st.session_state.api_key_status = None

    col_check, col_link = st.columns([1, 1])
    with col_check:
        if st.button("Check Key", use_container_width=True, key="btn_check_key"):
            if st.session_state.gemini_key:
                with st.spinner("Checking…"):
                    ok = check_api_key(st.session_state.gemini_key)
                st.session_state.api_key_status = "ok" if ok else "err"
            else:
                st.warning("Paste your key first!")
    with col_link:
        st.markdown('[Get free key ↗](https://aistudio.google.com/app/apikey)')

    if st.session_state.api_key_status == "ok":
        st.success("API key valid!")
    elif st.session_state.api_key_status == "err":
        st.error("Invalid key — try another")

    st.markdown('<div class="sb-divider"></div>', unsafe_allow_html=True)

    # ── Google Search ───────────────────────────────────────────────────────
    st.markdown(f'<div class="sb-label">{ico("globe",11,"#58a6ff")}&nbsp; Google Search</div>', unsafe_allow_html=True)
    google_on = st.toggle(
        "Enable Google Search", value=st.session_state.google_search,
        key="google_toggle",
        help="When ON, AI may search the web if notes don't have the answer"
    )
    if google_on != st.session_state.google_search:
        st.session_state.google_search = google_on
        st.rerun()
    if st.session_state.google_search:
        st.caption("Google may enhance your answers — results may vary")

    st.markdown('<div class="sb-divider"></div>', unsafe_allow_html=True)

    # ── Subject tree ─────────────────────────────────────────────────────────
    st.markdown(f'<div class="sb-label">{ico("folder",11,"#58a6ff")}&nbsp; Select Subject</div>', unsafe_allow_html=True)

    try:
        with st.spinner("Loading subjects…"):
            structure = get_structure(ROOT_FOLDER_ID, DRIVE_API_KEY)
    except Exception as e:
        st.error(f"Drive API error: {e}")
        st.stop()

    selected_id = selected_name = None

    for yi, (year_name, sems) in enumerate(structure.items()):
        with st.expander(f"{year_name}", expanded=(yi == 0)):
            for si, (sem_name, subjects) in enumerate(sems.items()):
                with st.expander(f"{sem_name}", expanded=False):
                    for subj_name, subj_id in subjects.items():
                        is_sel = subj_id == st.session_state.current_subject_id
                        label = f"{'✓ ' if is_sel else ''}{subj_name}"
                        if st.button(label, key=f"subj_{subj_id}", use_container_width=True):
                            selected_id, selected_name = subj_id, subj_name

    if selected_id and selected_id != st.session_state.current_subject_id:
        st.session_state.current_subject_id = selected_id
        st.session_state.subject_name = selected_name
        st.session_state.docs = {}
        st.session_state.messages = []
        st.session_state.greeting_shown = False
        st.rerun()

    st.markdown('<div class="sb-divider"></div>', unsafe_allow_html=True)

    # ── Load / New Chat ──────────────────────────────────────────────────────
    if st.session_state.current_subject_id:
        st.markdown(f'<div class="sb-subject-pill">{ico("folder",12,"#9ecfff")}&nbsp; {st.session_state.subject_name}</div>', unsafe_allow_html=True)
        if st.button("Load Subject Docs", use_container_width=True, type="primary", key="btn_load"):
            with st.spinner(f"Loading docs for {st.session_state.subject_name}…"):
                st.session_state.docs = load_subject_docs(st.session_state.current_subject_id, DRIVE_API_KEY)
                st.session_state.messages = []
                st.session_state.greeting_shown = False
            st.rerun()

    if st.session_state.messages:
        if st.button("New Chat", use_container_width=True, key="btn_new_chat"):
            st.session_state.messages = []
            st.session_state.greeting_shown = False
            st.rerun()

    st.markdown('<div class="sb-divider"></div>', unsafe_allow_html=True)

    # ── Admin ────────────────────────────────────────────────────────────────
    if not st.session_state.admin_logged_in:
        if st.button("Admin Login", use_container_width=True, key="btn_admin"):
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
                        st.error("Invalid credentials")
    else:
        st.markdown(f'<div class="sb-admin-on">{ico("settings",12,"#e8c840")}&nbsp; Admin Mode</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="sb-label">{ico("key",11,"#58a6ff")}&nbsp; Free API Keys</div>', unsafe_allow_html=True)

        for i, k in enumerate(st.session_state.free_api_keys):
            c1, c2 = st.columns([4, 1])
            with c1:
                new_val = st.text_input(f"Key {i+1}", value=k, key=f"adm_key_{i}", label_visibility="collapsed")
                if new_val != k:
                    st.session_state.free_api_keys[i] = new_val
            with c2:
                if st.button("✕", key=f"adm_del_{i}", help="Remove"):
                    st.session_state.free_api_keys.pop(i)
                    st.rerun()

        if st.button("Add API Key", use_container_width=True, key="btn_add_key"):
            st.session_state.free_api_keys.append("")
            st.rerun()

        if st.button("Logout Admin", use_container_width=True, key="btn_admin_logout"):
            st.session_state.admin_logged_in = False
            st.rerun()

    st.markdown('<div class="sb-footer">Docs refresh every 5 min · Drop new files in Drive anytime</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#   MAIN CONTENT WRAPPER — ensures footer stays at bottom
# ══════════════════════════════════════════════════════════════════════════════
docs      = st.session_state.docs
subj_name = st.session_state.subject_name

st.markdown('<div class="main-content">', unsafe_allow_html=True)

if not docs:
    if not st.session_state.current_subject_id:
        st.markdown(f"""
        <div class="hero-wrap">
          <div class="hero-avatar-wrap">
            <img src="{ADMIN_IMG_SRC}" alt="AI ආනා" class="hero-avatar">
          </div>
          <div class="hero-title">ආනාගේ <span class="hero-ai">AI</span></div>
          <div class="hero-sub">ඔබේ lecture notes ගැන ඕනෙ ප්‍රශ්නයක් අහන්නකෝ..!</div>
          <div class="hero-steps">
            <div class="hero-step">
              <span class="hero-step-num">1</span>
              <span>API Key paste කරන්න</span>
            </div>
            <div class="hero-step">
              <span class="hero-step-num">2</span>
              <span>Subject select කරන්න</span>
            </div>
            <div class="hero-step">
              <span class="hero-step-num">3</span>
              <span>Load කරලා අහන්න</span>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="load-banner">
          <div class="lb-icon-wrap">{ico("download", 28, "#1b3568")}</div>
          <div class="lb-title">Load Subject Docs</div>
          <div class="lb-sub"><strong>{subj_name}</strong> select කරලා තියෙනවා.<br>
          Sidebar එකේ <strong>Load Subject Docs</strong> button එක press කරන්නකෝ!</div>
        </div>
        """, unsafe_allow_html=True)
else:
    doc_names = list(docs.keys())
    gsearch_badge = f'&nbsp;{ico("globe",11,"#16a34a")}&nbsp;<span class="gsearch-badge">Google ON</span>' if st.session_state.google_search else ""
    tags_html = "&nbsp;".join(f'<span class="doc-tag">{n}</span>' for n in doc_names[:4])
    if len(doc_names) > 4:
        tags_html += f' <span class="doc-tag">+{len(doc_names)-4} more</span>'
    st.markdown(f"""
    <div class="status-bar">
      <span>{ico("folder",13,"#1b3568")}&nbsp;<strong>{subj_name}</strong></span>
      <span class="status-sep">·</span>
      <span>{len(doc_names)} doc{'s' if len(doc_names)!=1 else ''}</span>
      <span class="status-sep">·</span>
      {tags_html}{gsearch_badge}
    </div>
    """, unsafe_allow_html=True)

    if not st.session_state.greeting_shown:
        greeting = (
            "හෙලෝ සුද්දා, කෝමද, සැපේද ඉන්නේ..? 😊\n\n"
            f"You can now ask any question regarding the uploaded notes of **{subj_name}**. "
            "Can't find your answer? Enable Google Search in the sidebar!"
        )
        st.session_state.messages = [{"role": "assistant", "content": greeting, "is_greeting": True}]
        st.session_state.greeting_shown = True

    for msg in st.session_state.messages:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.markdown(msg["content"])
        else:
            # Use the admin image as avatar (circle with glow via CSS)
            with st.chat_message("assistant", avatar=ADMIN_IMG_SRC if ADMIN_IMG_PATH.exists() else "🤖"):
                st.markdown(msg["content"])
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

    if question := st.chat_input(f"Ask about {subj_name}…"):
        key = st.session_state.gemini_key
        if not key:
            st.error("Sidebar එකේ API key paste කරන්න!")
        else:
            st.session_state.messages.append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)
            with st.chat_message("assistant", avatar=ADMIN_IMG_SRC if ADMIN_IMG_PATH.exists() else "🤖"):
                if st.session_state.google_search:
                    st.caption("🌐 Google Search enabled — may enhance your answer")
                with st.spinner("AI ආනා thinking…"):
                    try:
                        answer = ask_gemini(key, question, docs, st.session_state.google_search)
                        track_usage(key)
                        st.session_state.messages.append({"role": "assistant", "content": answer})
                        st.markdown(answer)
                        st.rerun()
                    except Exception as e:
                        err = str(e)
                        if "API_KEY_INVALID" in err or "invalid" in err.lower():
                            st.error("Invalid Gemini API key. Get a free one at aistudio.google.com")
                            st.session_state.api_key_status = "err"
                        else:
                            st.error(f"Gemini error: {err}")

st.markdown('</div>', unsafe_allow_html=True)  # close main-content

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="aana-footer">
  <div class="ftr-inner">
    <div class="ftr-copy">©2025 All Rights Reserved</div>
    <div class="ftr-dev">
      Developed by&nbsp;<span class="ftr-heart">❤</span>&nbsp;<a class="ftr-name" href="https://venurakabojithananda.github.io/" rel="noopener" target="_blank">DSVB</a>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)
