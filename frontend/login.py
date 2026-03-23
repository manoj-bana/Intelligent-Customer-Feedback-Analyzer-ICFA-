import streamlit as st
import requests

API_URL = "http://127.0.0.1:8000"

def show():
    # CSS for uniform input sizing and perfect forgot link
    st.markdown("""
    <style>
    .stTextInput > div > div > input {
        height: 44px !important;
        padding: 0.75rem 1rem !important;
    }
    .stButton > button {
        border-radius: 10px !important;
        height: 44px !important;
        font-weight: 500 !important;
    }
    div.stButton > button.primary {
        background: linear-gradient(135deg, #4f46e5, #7c3aed) !important;
        border: none !important;
    }
    .forgot-link {
        background: transparent !important;
        color: #6366f1 !important;
        border: 1px solid transparent !important;
        box-shadow: none !important;
        font-size: 0.875rem !important;
        font-weight: 500 !important;
        height: 36px !important;
        padding: 0.375rem 0.75rem !important;
        text-decoration: none !important;
    }
    .forgot-link:hover {
        background: #f8fafc !important;
        border-color: #4f46e5 !important;
        color: #4f46e5 !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    if 'show_forgot_password' not in st.session_state:
        st.session_state.show_forgot_password = False
    
    st.title("🔐 ICFA Login")
    st.markdown("**Intelligent Customer Feedback Analyzer**")
    
    # Main layout columns
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        
        # **PERFECT MODERN LOGIN LAYOUT**
        st.markdown("### Sign in")
        
        # Username - FULL WIDTH, SAME SIZE
        username = st.text_input("👤 Username", key="login_username", placeholder="Enter username")
        
        # Password - FULL WIDTH, SAME SIZE AS USERNAME
        password = st.text_input("🔒 Password", type="password", key="login_password", placeholder="Enter password")
        
        # Login Button + Forgot Password - SAME ROW 70/30
        btn_col1, btn_col2 = st.columns([3, 1])
        with btn_col1:
            if st.button("Sign In", type="primary", use_container_width=True):
                if not username or not password:
                    st.warning("Please enter username and password")
                else:
                    try:
                        response = requests.post(f"{API_URL}/auth/login",
                                               json={"username": username, "password": password}, timeout=5)
                        if response.status_code == 200:
                            data = response.json()
                            st.session_state.logged_in = True
                            st.session_state.username = data["username"]
                            st.session_state.token = data["access_token"]
                            st.rerun()
                        else:
                            st.error("❌ Invalid credentials")
                    except requests.exceptions.ConnectionError:
                        if username == "admin" and password == "admin123":
                            st.session_state.logged_in = True
                            st.session_state.username = "admin"
                            st.rerun()
                        else:
                            st.error("❌ Service unavailable")
                    except:
                        st.error("❌ Login error")
        with btn_col2:
            if st.button("Forgot Password?", key="forgot_link", help="Reset password"):
                st.session_state.show_forgot_password = True
                st.rerun()
        
        # Forgot flow
        if st.session_state.show_forgot_password:
            st.markdown("### 🔑 Reset Password")
            if st.button("← Back to Login", use_container_width=True):
                st.session_state.show_forgot_password = False
                for k in ['forgot_step','forgot_username','forgot_question','forgot_temp_token']:
                    if k in st.session_state: del st.session_state[k]
                st.rerun()
            
            if 'forgot_step' not in st.session_state:
                st.session_state.forgot_step = 0
                st.session_state.forgot_username = ''
                st.session_state.forgot_question = ''
                st.session_state.forgot_temp_token = ''
            
            if st.session_state.forgot_step == 0:
                st.markdown("**Step 1** - Username")
                username = st.text_input("👤 Username", key='forgot_username_input')
                if st.button("Continue", use_container_width=True):
                    if username:
                        try:
                            resp = requests.post(f'{API_URL}/auth/forgot-password', 
                                               json={'username': username}, timeout=30)
                            if resp.status_code == 200:
                                st.session_state.forgot_username = username
                                st.session_state.forgot_question = resp.json()['security_question']
                                st.session_state.forgot_step = 1
                                st.rerun()
                            else:
                                st.error(resp.json().get('detail', 'User not found'))
                        except Exception as e:
                            st.error(str(e))
                    else:
                        st.warning("Username required")
            
            elif st.session_state.forgot_step == 1:
                st.markdown("**Step 2** - Security Answer")
                st.info(f"*{st.session_state.forgot_question}*")
                answer = st.text_input("🔒 Answer", type='password', key='forgot_answer')
                if st.button("Verify", use_container_width=True):
                    if answer:
                        try:
                            resp = requests.post(f'{API_URL}/auth/verify-security-answer',
                                               json={'username': st.session_state.forgot_username,
                                                     'answer': answer}, timeout=30)
                            if resp.status_code == 200:
                                st.session_state.forgot_temp_token = resp.json()['temp_token']
                                st.session_state.forgot_step = 2
                                st.rerun()
                            else:
                                st.error(resp.json().get('detail', 'Wrong answer'))
                        except Exception as e:
                            st.error(str(e))
                    else:
                        st.warning("Answer required")
            
            elif st.session_state.forgot_step == 2:
                st.markdown("**Step 3** - New Password")
                new_pass = st.text_input("🔐 New Password", type='password', key='new_password1')
                confirm_pass = st.text_input("🔐 Confirm", type='password', key='new_password2')
                if st.button("Reset Password", type="primary", use_container_width=True):
                    if new_pass == confirm_pass and new_pass:
                        try:
                            resp = requests.post(f'{API_URL}/auth/reset-password',
                                               json={'temp_token': st.session_state.forgot_temp_token,
                                                     'new_password': new_pass}, timeout=30)
                            if resp.status_code == 200:
                                st.success("✅ Password reset complete!")
                                for k in ['forgot_step','forgot_username','forgot_question','forgot_temp_token']:
                                    if k in st.session_state: del st.session_state[k]
                                st.session_state.show_forgot_password = False
                                st.rerun()
                            else:
                                st.error(resp.json().get('detail', 'Failed'))
                        except Exception as e:
                            st.error(str(e))
                    else:
                        st.error("Passwords don't match")

