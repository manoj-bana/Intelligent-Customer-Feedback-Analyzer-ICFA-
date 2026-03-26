import streamlit as st
import requests
import re
import time

API_URL = "http://127.0.0.1:8000"

EMAIL_RE = re.compile(r'^[\w\.-]+@[\w\.-]+\.\w+$')
PASSWORD_RE = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$')

SECURITY_QUESTIONS = [
    "What was your first pet's name?",
    "What is your mother's maiden name?",
    "What city were you born in?",
    "What was your first school?",
    "What is the name of your favorite teacher?",
]


def _check_username_available(username: str):
    try:
        r = requests.get(f"{API_URL}/auth/check-username", params={"username": username}, timeout=3)
        return not r.json().get("exists", False)
    except Exception:
        return None


def _check_email_available(email: str):
    try:
        r = requests.get(f"{API_URL}/auth/check-email", params={"email": email}, timeout=3)
        return not r.json().get("exists", False)
    except Exception:
        return None


def _inline_error(msg: str):
    st.markdown(
        f'<p style="color:#ef4444;font-size:0.8rem;margin-top:-0.5rem;margin-bottom:0.5rem;">⚠ {msg}</p>',
        unsafe_allow_html=True,
    )


def _inline_ok(msg: str):
    st.markdown(
        f'<p style="color:#22c55e;font-size:0.8rem;margin-top:-0.5rem;margin-bottom:0.5rem;">✓ {msg}</p>',
        unsafe_allow_html=True,
    )


def _password_strength(pwd: str) -> dict:
    return {
        "length":  len(pwd) >= 8,
        "upper":   bool(re.search(r'[A-Z]', pwd)),
        "lower":   bool(re.search(r'[a-z]', pwd)),
        "digit":   bool(re.search(r'\d', pwd)),
        "special": bool(re.search(r'[@$!%*?&]', pwd)),
    }


def _render_password_checklist(pwd: str):
    if not pwd:
        return
    checks = _password_strength(pwd)
    labels = {
        "length":  "At least 8 characters",
        "upper":   "Uppercase letter (A–Z)",
        "lower":   "Lowercase letter (a–z)",
        "digit":   "Number (0–9)",
        "special": "Special character (@$!%*?&)",
    }
    lines = []
    for key, label in labels.items():
        icon  = "✅" if checks[key] else "❌"
        color = "#22c55e" if checks[key] else "#ef4444"
        lines.append(f'<span style="color:{color};font-size:0.78rem;">{icon} {label}</span>')
    st.markdown(
        '<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:0.6rem 0.9rem;margin-top:-0.4rem;margin-bottom:0.6rem;">'
        + "<br>".join(lines)
        + "</div>",
        unsafe_allow_html=True,
    )


def show():
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

    st.title("🔐 ICFA — Register")
    st.markdown("### Intelligent Customer Feedback Analyzer")
    st.divider()

    defaults = {
        "rv_username": "",
        "rv_username_ok": None,
        "rv_email": "",
        "rv_email_ok": None,
        "rv_submitted": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:

        # ── Username ──
        username = st.text_input("👤 Username", key="reg_username", placeholder="Choose a username")

        if username and username != st.session_state.rv_username:
            st.session_state.rv_username = username
            st.session_state.rv_username_ok = _check_username_available(username)

        if username:
            if st.session_state.rv_username_ok is False:
                _inline_error("Username already exists")
            elif st.session_state.rv_username_ok is True:
                _inline_ok("Username available")
        elif st.session_state.rv_submitted:
            _inline_error("Username is required")

        # ── Email ──
        email = st.text_input("📧 Email", key="reg_email", placeholder="you@example.com")

        if email:
            if not EMAIL_RE.match(email):
                _inline_error("Invalid email format")
            else:
                if email != st.session_state.rv_email:
                    st.session_state.rv_email = email
                    st.session_state.rv_email_ok = _check_email_available(email)
                if st.session_state.rv_email_ok is False:
                    _inline_error("Email already registered")
                elif st.session_state.rv_email_ok is True:
                    _inline_ok("Email available")
        elif st.session_state.rv_submitted:
            _inline_error("Email is required")

        # ── Password ──
        password = st.text_input("🔒 Password", type="password", key="reg_password",
                                 placeholder="Min 8 chars, mixed case, number, symbol")
        _render_password_checklist(password)

        # ── Confirm Password ──
        confirm = st.text_input("🔒 Confirm Password", type="password", key="reg_confirm",
                                placeholder="Re-enter password")
        if confirm and password and confirm != password:
            _inline_error("Passwords do not match")
        elif confirm and password and confirm == password:
            _inline_ok("Passwords match")

        # ── Security Question ──
        question = st.selectbox("🔑 Security Question", SECURITY_QUESTIONS, key="reg_question")
        answer = st.text_input("🔑 Security Answer", key="reg_answer",
                               placeholder="Case-insensitive — stored securely",
                               help="Your answer will be hashed before storage")
        if st.session_state.rv_submitted and not answer.strip():
            _inline_error("Security answer is required")

        st.markdown("---")

        # ── Submit ──
        if st.button("Create Account", type="primary", use_container_width=True, key="register_button"):
            st.session_state.rv_submitted = True
            errors = []

            if not username:
                errors.append("Username is required")
            elif st.session_state.rv_username_ok is False:
                errors.append("Username already exists")

            if not email:
                errors.append("Email is required")
            elif not EMAIL_RE.match(email):
                errors.append("Invalid email format")
            elif st.session_state.rv_email_ok is False:
                errors.append("Email already registered")

            pwd_checks = _password_strength(password)
            if not password:
                errors.append("Password is required")
            elif not all(pwd_checks.values()):
                errors.append("Password does not meet all requirements (see checklist above)")

            if not confirm:
                errors.append("Please confirm your password")
            elif password != confirm:
                errors.append("Passwords do not match")

            if not answer.strip():
                errors.append("Security answer is required")

            if errors:
                for e in errors:
                    st.error(f"❌ {e}")
                st.stop()

            try:
                response = requests.post(
                    f"{API_URL}/auth/register",
                    json={
                        "username": username,
                        "email": email,
                        "password": password,
                        "security_question": question,
                        "security_answer": answer,
                    },
                    timeout=5,
                )
                if response.status_code == 200:
                    data = response.json()
                    st.session_state.logged_in = True
                    st.session_state.username = data["username"]
                    st.session_state.token = data["access_token"]
                    st.success("✅ Registration successful! Redirecting…")
                    time.sleep(0.8)
                    st.rerun()
                else:
                    detail = response.json().get("detail", "Registration failed")
                    if "Username" in detail:
                        st.session_state.rv_username_ok = False
                    if "Email" in detail:
                        st.session_state.rv_email_ok = False
                    st.error(f"❌ {detail}")
            except requests.exceptions.ConnectionError:
                st.error("❌ Backend not reachable. Run: `uvicorn backend.main:app --reload --port 8000`")
            except Exception as exc:
                st.error(f"❌ Unexpected error: {exc}")

        st.caption("Passwords are stored using bcrypt hashing — never in plain text.")