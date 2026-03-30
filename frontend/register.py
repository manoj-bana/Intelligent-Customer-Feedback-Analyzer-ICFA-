import streamlit as st
import requests
import re
from frontend.errors import ERROR_MESSAGES

API_URL = "http://127.0.0.1:8000"

def show():
    """
    Renders the registration interface with real-time validation for usernames, 
    emails, and password strength.
    """
    # CSS Eye Icon Fix + Custom Styling
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
    
    /* Checklist Styling */
    .checklist-item {
        font-size: 0.85rem;
        margin-bottom: 2px;
    }
    .check-valid { color: #059669; }
    .check-invalid { color: #dc2626; }
    
    /* Inline Message Styling */
    .inline-msg {
        font-size: 0.8rem;
        margin-top: -15px;
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

    st.title("🔐 ICFA - Register")
    st.markdown("### Create Your Account")
    st.divider()

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Username with real-time check
        username = st.text_input(
            "Username", 
            key="reg_username", 
            placeholder="Choose a unique username"
        )
        if username:
            try:
                resp = requests.get(f"{API_URL}/auth/check-username?username={username}", timeout=2)
                if resp.status_code == 200 and resp.json().get("exists"):
                    st.markdown(
                        f'<p class="inline-msg check-invalid">⚠ {ERROR_MESSAGES["USERNAME_TAKEN"]}</p>', 
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        f'<p class="inline-msg check-valid">✓ Username available</p>', 
                        unsafe_allow_html=True
                    )
            except Exception:
                # Silently handle connection errors during real-time check
                pass

        # Email with real-time check
        email = st.text_input("Email", key="reg_email", placeholder="Enter your email")
        email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        if email:
            if not re.match(email_pattern, email):
                st.markdown(
                    f'<p class="inline-msg check-invalid">⚠ {ERROR_MESSAGES["EMAIL_INVALID_FORMAT"]}</p>', 
                    unsafe_allow_html=True
                )
            else:
                try:
                    resp = requests.get(f"{API_URL}/auth/check-email?email={email}", timeout=2)
                    if resp.status_code == 200 and resp.json().get("exists"):
                        st.markdown(
                            f'<p class="inline-msg check-invalid">⚠ {ERROR_MESSAGES["EMAIL_TAKEN"]}</p>', 
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown(
                            f'<p class="inline-msg check-valid">✓ Email available</p>', 
                            unsafe_allow_html=True
                        )
                except Exception:
                    # Silently handle connection errors during real-time check
                    pass

        # Password with live checklist
        password = st.text_input(
            "Password", 
            type="password", 
            key="reg_password", 
            placeholder="Create a strong password"
        )
        
        # Checklist logic
        rules = [
            (len(password) >= 8, "At least 8 characters"),
            (bool(re.search(r'[A-Z]', password)), "Uppercase letter (A–Z)"),
            (bool(re.search(r'[a-z]', password)), "Lowercase letter (a–z)"),
            (bool(re.search(r'\d', password)), "Number (0–9)"),
            (bool(re.search(r'[@$!%*?&]', password)), "Special character (@$!%*?&)")
        ]
        
        if password:
            for valid, label in rules:
                icon = "✅" if valid else "❌"
                color = "check-valid" if valid else "check-invalid"
                st.markdown(
                    f'<div class="checklist-item {color}">{icon} {label}</div>', 
                    unsafe_allow_html=True
                )
        
        confirm_password = st.text_input("Confirm Password", type="password", key="reg_confirm")
        if confirm_password:
            if password == confirm_password:
                st.markdown(
                    '<p class="inline-msg check-valid">✓ Passwords match</p>', 
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f'<p class="inline-msg check-invalid">⚠ {ERROR_MESSAGES["PASSWORD_MISMATCH"]}</p>', 
                    unsafe_allow_html=True
                )

        security_questions = [
            "What was your first pet's name?",
            "What is your mother's maiden name?", 
            "What city were you born in?",
            "What was your first school?",
            "What is the name of your favorite teacher?"
        ]
        question = st.selectbox("Security Question", security_questions, key="reg_question")
        answer = st.text_input(
            "Security Answer", 
            help="Answer will be securely hashed", 
            key="reg_answer", 
            placeholder="Your secret answer"
        )
        # st.caption("🔒 Your answer is normalized and hashed for security.")

        if st.button("Complete Registration", use_container_width=True, type="primary"):
            # Final validation
            errors = []
            if not username or not email or not password or not confirm_password or not answer:
                errors.append(ERROR_MESSAGES["FIELDS_REQUIRED"])
            if password != confirm_password:
                errors.append(ERROR_MESSAGES["PASSWORD_MISMATCH"])
            if not all(r[0] for r in rules):
                errors.append(ERROR_MESSAGES["PASSWORD_REQUIREMENTS"])
            if not re.match(email_pattern, email):
                errors.append(ERROR_MESSAGES["EMAIL_INVALID_FORMAT"])
            
            if errors:
                for err in errors:
                    st.error(err)
            else:
                try:
                    with st.spinner("Creating account..."):
                        response = requests.post(
                            f"{API_URL}/auth/register",
                            json={
                                "username": username,
                                "email": email,
                                "password": password,
                                "security_question": question,
                                "security_answer": answer
                            },
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
                            
                            st.success(f"✅ {ERROR_MESSAGES['REGISTRATION_SUCCESSFUL']}")
                            st.rerun()
                        else:
                            detail = response.json().get("detail", "Registration failed")
                            st.error(f"❌ {detail}")
                except Exception:
                    st.error(f"❌ {ERROR_MESSAGES['SERVICE_ERROR']}")