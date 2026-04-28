import streamlit as st
import uuid

@st.cache_resource
def get_session_manager():
    """Returns a global dictionary for server-side session persistence."""
    return {}

def persist_session(username, token, role):
    """Stores session data in the global manager and updates query params with a session ID."""
    manager = get_session_manager()
    sid = str(uuid.uuid4())
    manager[sid] = {
        "username": username,
        "token": token,
        "role": role
    }
    st.session_state.logged_in = True
    st.session_state.username = username
    st.session_state.token = token
    st.session_state.role = role
    st.query_params["sid"] = sid
    return sid

def clear_persisted_session():
    """Removes the current session from the global manager and clears query params."""
    sid = st.query_params.get("sid")
    if sid:
        manager = get_session_manager()
        if sid in manager:
            del manager[sid]
    st.query_params.clear()
