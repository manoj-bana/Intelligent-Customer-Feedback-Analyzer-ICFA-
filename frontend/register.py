import streamlit as st
import requests
import re
 
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

        security_questions = [
            "What was your first pet's name?",
            "What is your mother's maiden name?", 
            "What city were you born in?",
            "What was your first school?",
            "What is the name of your favorite teacher?"
        ]
        question = st.selectbox("Security Question", security_questions, key="register_question")
        answer = st.text_input("Security Answer (case insensitive)", help="Answer will be securely hashed", key="register_answer")

        # Password regex: min 8, upper, lower, digit, special
        password_pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$'
        email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
 
        if st.button("Register", width="stretch", key="register_button"):
            # Client-side validation
            if not username or not email or not password or not confirm_password:
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
            elif not question or not answer:
                st.error("❌ Security question and answer required")
            else:
                # All validation passed, try API
                try:
                    response = requests.post(
                        f"{API_URL}/auth/register",
                    json={"username": username, "email": email, "password": password, "security_question": question, "security_answer": answer},
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
 