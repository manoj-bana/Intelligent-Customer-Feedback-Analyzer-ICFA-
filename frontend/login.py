import streamlit as st
import requests
import re
from frontend.errors import ERROR_MESSAGES

API_URL = "http://127.0.0.1:8000"

def show():
    """
    Renders the login and password reset interface.
    """
    # CSS Fixes and Styling
    st.markdown("""
    <style>
    /* Hide Streamlit Password Eye Icon */
    [data-testid="stTextInput"] [data-testid="styled-input-container"] button {
        display: none !important;
    }
    input[type="password"]::-ms-reveal,
    input[type="password"]::-ms-clear,
    input[type="password"]::-webkit-credentials-auto-fill-button {
        display: none !important;
    }

    .stTextInput > div > div > input {
        height: 44px !important;
        padding: 0.75rem 1rem !important;
    }
    .stButton > button {
        border-radius: 10px !important;
        height: 44px !important;
        font-weight: 500 !important;
    }
    
    /* Checklist Styling for Reset Step */
    .checklist-item {
        font-size: 0.85rem;
        margin-bottom: 2px;
    }
    .check-valid { color: #059669; }
    .check-invalid { color: #dc2626; }
    </style>
    """, unsafe_allow_html=True)
    
    if 'show_forgot_password' not in st.session_state:
        st.session_state.show_forgot_password = False
    
    st.title("🔐 ICFA Login")
    
    # Connection Status Check using /health endpoint
    try:
        # Increased timeout to 3 seconds and bypass local proxies
        requests.get(f"{API_URL}/health", timeout=3, proxies={"http": None, "https": None})
        status = '🟢 System Online'
    except Exception as e:
        # Output exception for debugging if still offline
        status = f'🔴 System Offline ({type(e).__name__})'
    
    st.sidebar.markdown(f"**Status:** {status}")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if not st.session_state.show_forgot_password:
            render_login_form()
        else:
            render_password_reset_flow()

def render_login_form():
    """
    Internal helper to render the standard sign-in form.
    """
    st.markdown("### Sign In")
    username = st.text_input("Username", key="login_username", placeholder="Enter your username")
    password = st.text_input("Password", type="password", key="login_password", placeholder="Enter your password")
    
    if st.button("Sign In", type="primary", width='stretch'):
        if not username or not password:
            st.warning(f"⚠️ {ERROR_MESSAGES['FIELDS_REQUIRED']}")
        else:
            try:
                response = requests.post(
                    f"{API_URL}/auth/login",
                    json={"username": username, "password": password}, 
                    timeout=10
                )
                if response.status_code == 200:
                    data = response.json()
                    st.session_state.logged_in = True
                    st.session_state.username = data["username"]
                    st.session_state.token = data["access_token"]
                    
                    # Store in query params for browser refresh persistence
                    st.query_params["token"] = data["access_token"]
                    st.query_params["username"] = data["username"]
                    
                    st.success("✅ Login successful!")
                    st.rerun()
                else:
                    st.error(f"❌ {ERROR_MESSAGES['INVALID_LOGIN']}")
            except Exception:
                st.error(f"❌ {ERROR_MESSAGES['SERVICE_ERROR']}")
    
    if st.button("Forgot Password?", key="forgot_link_btn", type="secondary", width='stretch'):
        st.session_state.show_forgot_password = True
        st.rerun()

def render_password_reset_flow():
    """
    Internal helper to render the 3-step password reset workflow.
    """
    st.markdown("### 🔑 Reset Password")
    
    if 'forgot_step' not in st.session_state:
        st.session_state.forgot_step = 0
        st.session_state.forgot_username = ''
        st.session_state.forgot_question = ''
        st.session_state.forgot_temp_token = ''

    # Step Navigation
    if st.button("← Back to Login", type="secondary"):
        st.session_state.show_forgot_password = False
        for k in ['forgot_step', 'forgot_username', 'forgot_question', 'forgot_temp_token']:
            st.session_state.pop(k, None)
        st.rerun()

    st.divider()

    if st.session_state.forgot_step == 0:
        st.markdown("**Step 1: Identity Verification**")
        f_username = st.text_input("Enter Username", key="forgot_user_input")
        if st.button("Fetch Security Question", width='stretch'):
            if f_username:
                try:
                    resp = requests.post(
                        f'{API_URL}/auth/forgot-password',
                        json={"username": f_username}, 
                        timeout=10
                    )
                    if resp.status_code == 200:
                        st.session_state.forgot_username = f_username
                        st.session_state.forgot_question = resp.json()['security_question']
                        st.session_state.forgot_step = 1
                        st.rerun()
                    else:
                        st.error(f"❌ {ERROR_MESSAGES['USER_NOT_FOUND']}")
                except Exception:
                    st.error(f"❌ {ERROR_MESSAGES['SERVICE_ERROR']}")
            else:
                st.warning("Username required")

    elif st.session_state.forgot_step == 1:
        st.markdown("**Step 2: Security Verification**")
        st.info(f"**Question:** {st.session_state.forgot_question}")
        answer = st.text_input("Your Answer", type="password", key="forgot_ans_input")
        if st.button("Verify Answer", width='stretch'):
            if answer:
                try:
                    resp = requests.post(
                        f'{API_URL}/auth/verify-security-answer',
                        json={
                            "username": st.session_state.forgot_username,
                            "answer": answer
                        }, 
                        timeout=10
                    )
                    if resp.status_code == 200:
                        st.session_state.forgot_temp_token = resp.json()['temp_token']
                        st.session_state.forgot_step = 2
                        st.rerun()
                    else:
                        st.error(f"❌ {ERROR_MESSAGES['WRONG_ANSWER']}")
                except Exception:
                    st.error(f"❌ {ERROR_MESSAGES['SERVICE_ERROR']}")
            else:
                st.warning("Answer required")

    elif st.session_state.forgot_step == 2:
        st.markdown("**Step 3: New Password**")
        new_pass = st.text_input("New Password", type="password", key="reset_pass1")
        
        # Live Checklist
        rules = [
            (len(new_pass) >= 8, "8+ characters"),
            (bool(re.search(r'[A-Z]', new_pass)), "Uppercase"),
            (bool(re.search(r'[a-z]', new_pass)), "Lowercase"),
            (bool(re.search(r'\d', new_pass)), "Number"),
            (bool(re.search(r'[@$!%*?&]', new_pass)), "Special char")
        ]
        if new_pass:
            for valid, label in rules:
                color = "check-valid" if valid else "check-invalid"
                icon = "✅" if valid else "❌"
                st.markdown(
                    f'<span class="checklist-item {color}">{icon} {label}</span>', 
                    unsafe_allow_html=True
                )

        confirm_pass = st.text_input("Confirm New Password", type="password", key="reset_pass2")
        
        # Match Indicator
        if confirm_pass:
            if new_pass == confirm_pass:
                st.markdown('<p class="inline-msg check-valid">✓ Passwords match</p>', unsafe_allow_html=True)
            else:
                st.markdown(f'<p class="inline-msg check-invalid">⚠ {ERROR_MESSAGES["PASSWORD_MISMATCH"]}</p>', unsafe_allow_html=True)
        
        if st.button("Update Password", type="primary", width='stretch'):
            if not all(r[0] for r in rules):
                st.error(f"❌ {ERROR_MESSAGES['PASSWORD_REQUIREMENTS']}")
            elif new_pass != confirm_pass:
                st.error(f"❌ {ERROR_MESSAGES['PASSWORD_MISMATCH']}")
            else:
                try:
                    resp = requests.post(
                        f'{API_URL}/auth/reset-password',
                        json={
                            "temp_token": st.session_state.forgot_temp_token,
                            "new_password": new_pass
                        }, 
                        timeout=10
                    )
                    if resp.status_code == 200:
                        st.success(f"✅ {ERROR_MESSAGES['RESET_SUCCESSFUL']}")
                        st.session_state.show_forgot_password = False
                        for k in ['forgot_step', 'forgot_username', 'forgot_question', 'forgot_temp_token']:
                            st.session_state.pop(k, None)
                        st.rerun()
                    else:
                        st.error(f"❌ {ERROR_MESSAGES['TOKEN_EXPIRED']}")
                except Exception:
                    st.error(f"❌ {ERROR_MESSAGES['SERVICE_ERROR']}")
