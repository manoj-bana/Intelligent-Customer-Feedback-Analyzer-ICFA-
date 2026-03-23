import streamlit as st
import requests
 
API_URL = "http://127.0.0.1:8000"
 
def show():
    st.title("🔐 ICFA - Login")
    st.markdown("### Intelligent Customer Feedback Analyzer")
    st.divider()
 
    tab1, tab2 = st.tabs(["Login", "Forgot Password"])
 
    with tab1:
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
                    if username == "admin" and password == "admin123":
                        st.session_state.logged_in = True
                        st.session_state.username = username
                        st.rerun()
                    else:
                        st.error("❌ Backend not running. Try admin / admin123 for demo mode.")
                except Exception as e:
                    st.error(f"Unexpected error: {e}")
 
            st.caption("Demo: admin / admin123")
 
    with tab2:
        st.markdown("**Forgot Password?** Recover using your security question.")
       
        if 'forgot_step' not in st.session_state:
            st.session_state.forgot_step = 0
            st.session_state.forgot_username = ''
            st.session_state.forgot_question = ''
            st.session_state.forgot_temp_token = ''
 
        if st.session_state.forgot_step == 0:
            username = st.text_input("Username", key='forgot_username_input')
            if st.button("Get Security Question", key='get_question'):
                if username:
                    try:
                        resp = requests.post(f'{API_URL}/auth/forgot-password',
                                           json={'username': username}, timeout=30)
                        if resp.status_code == 200:
                            q = resp.json()['security_question']
                            st.session_state.forgot_username = username
                            st.session_state.forgot_question = q
                            st.session_state.forgot_step = 1
                            st.success("Question retrieved!")
                            st.rerun()
                        else:
                            st.error(resp.json().get('detail', 'User not found'))
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.warning("Enter username first")
 
        elif st.session_state.forgot_step == 1:
            st.info(f"**Security Question:** {st.session_state.forgot_question}")
            answer = st.text_input("Answer", type='password', key='forgot_answer')
            if st.button("Verify Answer", key='verify_answer'):
                if answer:
                    try:
                        resp = requests.post(f'{API_URL}/auth/verify-security-answer',
                                           json={'username': st.session_state.forgot_username,
                                                 'answer': answer}, timeout=30)
                        if resp.status_code == 200:
                            st.session_state.forgot_temp_token = resp.json()['temp_token']
                            st.session_state.forgot_step = 2
                            st.success("Answer verified! Set new password.")
                            st.rerun()
                        else:
                            st.error(resp.json().get('detail', 'Wrong answer'))
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.warning("Enter answer")
 
        elif st.session_state.forgot_step == 2:
            new_password = st.text_input("New Password", type='password', key='new_password1')
            confirm_password = st.text_input("Confirm New Password", type='password', key='new_password2')
            if st.button("Reset Password", key='reset_pw'):
                if new_password == confirm_password and new_password:
                    try:
                        resp = requests.post(f'{API_URL}/auth/reset-password',
                                           json={'temp_token': st.session_state.forgot_temp_token,
                                                 'new_password': new_password}, timeout=30)
                        if resp.status_code == 200:
                            st.success("✅ Password reset successful! You can now login with new password.")
                            for k in ['forgot_step', 'forgot_username', 'forgot_question', 'forgot_temp_token']:
                                if k in st.session_state:
                                    del st.session_state[k]
                            st.rerun()
                        else:
                            st.error(resp.json().get('detail', 'Reset failed'))
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.error("Passwords don't match or empty")
 
        if st.button("← Back to Login", key='back_to_login'):
            for k in ['forgot_step', 'forgot_username', 'forgot_question', 'forgot_temp_token']:
                if k in st.session_state:
                    del st.session_state[k]
            st.rerun()
 
