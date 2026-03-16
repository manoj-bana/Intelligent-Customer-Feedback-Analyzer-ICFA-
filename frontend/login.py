import streamlit as st
import requests

API_URL = "http://127.0.0.1:8000"


def show():
    st.title("🔐 ICFA - Login")
    st.markdown("### Intelligent Customer Feedback Analyzer")
    st.divider()

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")

        if st.button("Login", width="stretch", key="login_button"):
            if not username or not password:
                st.warning("Please enter both username and password")
                return
            try:
                response = requests.post(
                    f"{API_URL}/auth/login",
                    json={"username": username, "password": password},
                    timeout=5
                )
                if response.status_code == 200:
                    data = response.json()
                    st.session_state.logged_in = True
                    st.session_state.username = data["username"]
                    st.session_state.token = data["access_token"]
                    st.rerun()
                else:
                    st.error("❌ Invalid username or password")
            except requests.exceptions.ConnectionError:
                # Fallback for demo when backend not running
                if username == "admin" and password == "admin123":
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("❌ Backend not running. Try admin / admin123 for demo mode.")
            except Exception as e:
                st.error(f"Unexpected error: {e}")

        st.caption("Credentials: admin / admin123  |  user1 / pass123")

