import streamlit as st
import requests
 
API_URL = "http://127.0.0.1:8000"
 
def show():
    # CSS for uniform inputs + forgot link
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
    }
    .forgot-link {
        background: transparent !important;
        color: #6366f1 !important;
        font-size: 0.875rem !important;
        height: auto !important;
        padding: 0 0 !important;
    }
    .status-badge {
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 500;
    }
    .status-online { background: #dcfce7; color: #166534; }
    .status-offline { background: #fee2e2; color: #991b1b; }
    
    [data-testid="stTextInput"] [data-testid="styled-input-container"] button {
        display: none !important;
    }
    input[type="password"]::-ms-reveal,
    input[type="password"]::-ms-clear,
    input[type="password"]::-webkit-credentials-auto-fill-button {
        display: none !important;
    }
    </style>
    """, unsafe_allow_html=True)
   
    if 'show_forgot_password' not in st.session_state:
        st.session_state.show_forgot_password = False
   
    st.title("🔐 ICFA Login")
   
    # Backend status check
    try:
        status_resp = requests.get(f"{API_URL}/auth/test", timeout=2)
        status = '🟢 Online'
        status_class = 'status-online'
    except:
        status = '🔴 Offline'
        status_class = 'status-offline'
   
    col1, col2, col3 = st.columns([1, 4, 1])
    with col2:
        st.markdown(f'<span class="status-badge {status_class}">{status}</span>', unsafe_allow_html=True)
   
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### Sign in")
       
        # Username & Password - SAME SIZE
        username = st.text_input("👤 Username", key="login_username", placeholder="Enter username")
        password = st.text_input("🔒 Password", type="password", key="login_password", placeholder="Enter password")
       
        # Login (70%) + Forgot (30%)
        btn_col1, btn_col2 = st.columns([3, 1])
        with btn_col1:
            if st.button("Sign In", type="primary", use_container_width=True):
                if not username or not password:
                    st.warning("⚠️ Username and password required")
                elif username == "admin" and password == "admin123":
                    st.session_state.logged_in = True
                    st.session_state.username = "admin"
                    st.session_state.token = "demo-token"
                    st.success("✅ Demo login successful!")
                    st.rerun()
                else:
                    try:
                        response = requests.post(f"{API_URL}/auth/login",
                                               json={"username": username, "password": password},
                                               timeout=5)
                        if response.status_code == 200:
                            data = response.json()
                            st.session_state.logged_in = True
                            st.session_state.username = data["username"]
                            st.session_state.token = data["access_token"]
                            st.success("✅ Login successful!")
                            st.rerun()
                        else:
                            st.error("❌ Invalid credentials")
                    except requests.exceptions.ConnectionError:
                        st.error("❌ Backend offline - use demo: admin/admin123")
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
       
        with btn_col2:
            if st.button("Forgot Password?", key="forgot_link", help="Reset password"):
                st.session_state.show_forgot_password = True
                st.rerun()
       
        # Forgot flow
        if st.session_state.show_forgot_password:
            st.markdown("### 🔑 Reset Password")
           
            col_back1, col_back2 = st.columns([3, 1])
            with col_back2:
                if st.button("← Back", use_container_width=False):
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
                st.markdown("*Step 1: Enter username*")
                st.text_input("👤 Username", key="forgot_username_input")
                if st.button("Get Security Question", type="primary", use_container_width=True):
                    username = st.session_state.get('forgot_username_input', '').strip()
                    if username:
                        try:
                            resp = requests.post(f'{API_URL}/auth/forgot-password',
                                                 json={"username": username}, timeout=10)
                            if resp.status_code == 200:
                                st.session_state.forgot_username = username
                                st.session_state.forgot_question = resp.json()['security_question']
                                st.session_state.forgot_step = 1
                                st.rerun()
                            else:
                                st.error(resp.json().get("detail", "User not found"))
                                return False
                            return True
                        except Exception as e:
                            st.error(f"Service error: {e}")
                            return False
                    else:
                        st.warning("Username required")
            elif st.session_state.forgot_step == 1:
                st.markdown("*Step 2: Answer security question*")
                st.info(f"**Q:** {st.session_state.forgot_question}")
                answer = st.text_input("🔒 Answer", type="password", key="forgot_answer")
                if st.button("Verify Answer", type="primary", use_container_width=True):
                    if answer:
                        try:
                            resp = requests.post(f'{API_URL}/auth/verify-security-answer',
                                               json={"username": st.session_state.forgot_username,
                                                     "answer": answer}, timeout=10)
                            if resp.status_code == 200:
                                st.session_state.forgot_temp_token = resp.json()['temp_token']
                                st.session_state.forgot_step = 2
                                st.rerun()
                            else:
                                st.error(resp.json().get("detail", "Wrong answer"))
                        except Exception as e:
                            st.error(f"Service error: {e}")
                    else:
                        st.warning("Answer required")
            elif st.session_state.forgot_step == 2:
                st.markdown("*Step 3: Set new password*")

                new_pass = st.text_input("🔐 New Password", type="password", key="new_password1")
                confirm_pass = st.text_input("🔐 Confirm", type="password", key="new_password2")
                if st.button("Reset Password", type="primary", use_container_width=True):
                    if new_pass == confirm_pass and len(new_pass) > 0:
                        resp = requests.post(f'{API_URL}/auth/reset-password',
                                           json={"temp_token": st.session_state.forgot_temp_token,
                                                 "new_password": new_pass}, timeout=10)
                        if resp.status_code == 200:
                            st.success("✅ Password reset successful!")
                            for k in ['forgot_step','forgot_username','forgot_question','forgot_temp_token']:
                                if k in st.session_state: del st.session_state[k]
                            st.session_state.show_forgot_password = False
                            st.rerun()
                        else:
                            st.error(resp.json().get("detail", "Reset failed"))
                    else:
                        st.error("Passwords don't match")

 
 
 