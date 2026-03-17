import streamlit as st
import requests
import json

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

        # Forgot Password option
        if st.button("Forgot Password?", key="forgot_pw"):
            st.session_state.forgot_mode = True
            st.rerun()
        
        if hasattr(st.session_state, 'forgot_mode') and st.session_state.forgot_mode:
            st.markdown("---")
            forgot_username = st.text_input("Enter username", key="forgot_username")
            if st.button("Get Security Questions", key="get_questions"):
                try:
                    response = requests.post(
                        f"{API_URL}/auth/get-security-questions",
                        json={"username": forgot_username},
                        timeout=5
                    )
                    if response.status_code == 200:
                        st.session_state.questions = response.json()["questions"]
                        st.session_state.forgot_username = forgot_username
                        st.rerun()
                    else:
                        st.error("❌ Username not found")
                except Exception as e:
                    st.error("❌ Backend not available")
            
            if hasattr(st.session_state, 'questions'):
                st.markdown("### Answer the questions:")
                ans1 = st.text_input(st.session_state.questions[0], key="ans1")
                ans2 = st.text_input(st.session_state.questions[1], key="ans2")
                ans3 = st.text_input(st.session_state.questions[2], key="ans3")
                
                if st.button("Verify and Login", key="verify_btn"):
                    answers = json.dumps({"0": ans1.strip(), "1": ans2.strip(), "2": ans3.strip()})
                    try:
                        response = requests.post(
                            f"{API_URL}/auth/verify-security",
                            json={"username": st.session_state.forgot_username, "answers": answers},
                            timeout=5
                        )
                        if response.status_code == 200:
                            data = response.json()
                            st.session_state.logged_in = True
                            st.session_state.username = data["username"]
                            st.session_state.token = data["access_token"]
                            del st.session_state.forgot_mode
                            del st.session_state.questions
                            st.rerun()
                        else:
                            st.error("❌ Invalid security answers")
                    except Exception as e:
                        st.error("❌ Backend error")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Back to Login", key="back_login"):
                        del st.session_state.forgot_mode
                        if 'questions' in st.session_state:
                            del st.session_state.questions
                        st.rerun()
            
        st.caption("Credentials: admin / admin123  |  user1 / pass123")

