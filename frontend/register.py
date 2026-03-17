import streamlit as st
import requests
import re
import json

API_URL = "http://127.0.0.1:8000"


def show():
    st.title("🔐 ICFA - Register")
    st.markdown("### Intelligent Customer Feedback Analyzer")
    st.divider()

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username = st.text_input("Username", key="register_username")
        email = st.text_input("Email", key="register_email")
        password = st.text_input("Password", type="password", key="register_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="register_confirm")
        
        st.markdown("### Security Questions (for password recovery)")
        sec_q1 = st.text_input("1. What was the name of your first pet?", key="reg_sec1")
        sec_q2 = st.text_input("2. What is your mother\\'s maiden name?", key="reg_sec2")
        sec_q3 = st.text_input("3. What was the name of your first school?", key="reg_sec3")

        # Password regex: min 8, upper, lower, digit, special
        password_pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$'
        email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'

        if st.button("Register", width="stretch", key="register_button"):
            # Client-side validation
            if not username or not email or not password or not confirm_password or not sec_q1 or not sec_q2 or not sec_q3:
                st.warning("Please fill all fields")
            elif password != confirm_password:
                st.error("❌ Passwords do not match")
            elif not re.match(email_pattern, email):
                st.error("❌ Invalid email format")
            elif len(password) < 8:
                st.error("❌ Password must be 8+ chars")
            elif not re.search(r'[A-Z]', password):
                st.error("❌ Password must have uppercase letter")
            elif not re.search(r'[a-z]', password):
                st.error("❌ Password must have lowercase letter")
            elif not re.search(r'\d', password):
                st.error("❌ Password must have number")
            elif not re.search(r'[@$!%*?&]', password):
                st.error("❌ Password must have special char (@$!%*?&)")
            else:
                # All validation passed, try API
                try:
                    response = requests.post(
                        f"{API_URL}/auth/register",
                        json={"username": username, "email": email, "password": password, "security_answers": json.dumps({"0": sec_q1.strip(), "1": sec_q2.strip(), "2": sec_q3.strip()})},
                        timeout=5
                    )
                    if response.status_code == 200:
                        data = response.json()
                        st.session_state.logged_in = True
                        st.session_state.username = data["username"]
                        st.session_state.token = data["access_token"]
                        st.success("✅ Registration successful!")
                        st.rerun()
                    else:
                        error_detail = response.json().get("detail", "Registration failed")
                        st.error(f"❌ {error_detail}")
                except requests.exceptions.ConnectionError:
                    st.error("❌ Backend not available. Start `cd backend && uvicorn main:app --reload --port 8000`")
                except Exception as e:
                    st.error(f"Unexpected error: {e}")

        st.caption("Example: Valid password 'Passw0rd!'")

