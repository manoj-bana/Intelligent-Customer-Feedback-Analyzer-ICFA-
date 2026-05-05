import sys
import os
import streamlit as st

# Bypass local system proxies for connection to the backend
os.environ["NO_PROXY"] = "127.0.0.1,localhost"

# Ensure project root is in sys.path for backend/frontend imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from frontend import login, register
from frontend.pages import dashboard
from frontend.utils.session import get_session_manager

# --- Page Configuration ---
st.set_page_config(
    page_title="ICFA", 
    layout="wide"
)

# Hide default Streamlit sidebar navigation to use custom router
st.markdown(
    "<style>[data-testid='stSidebarNav'] {display: none;}</style>", 
    unsafe_allow_html=True
)

# --- Session State Initialization ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "username" not in st.session_state:
    st.session_state.username = ""

if "token" not in st.session_state:
    st.session_state.token = ""

if "role" not in st.session_state:
    st.session_state.role = "user"

# --- Session Recovery Logic ---
# This allows persistence across refreshes without putting the token in the URL.
session_manager = get_session_manager()
query_sid = st.query_params.get("sid")

if not st.session_state.logged_in and query_sid:
    if query_sid in session_manager:
        persisted_session = session_manager[query_sid]
        st.session_state.logged_in = True
        st.session_state.username = persisted_session["username"]
        st.session_state.token = persisted_session["token"]
        st.session_state.role = persisted_session["role"]

# --- Routing Logic ---
if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["Login", "Register"])
    with tab1:
        login.show()
    with tab2:
        register.show()
else:
    dashboard.show()
