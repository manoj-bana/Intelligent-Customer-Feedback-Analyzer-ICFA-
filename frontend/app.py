import sys
import os
import streamlit as st

# Ensure project root is in sys.path for backend/frontend imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from frontend import login, register
from frontend.pages import dashboard

# --- Page Configuration ---
st.set_page_config(
    page_title="ICFA", 
    page_icon="📊", 
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

# --- Routing Logic ---
if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["Login", "Register"])
    with tab1:
        login.show()
    with tab2:
        register.show()
else:
    dashboard.show()
