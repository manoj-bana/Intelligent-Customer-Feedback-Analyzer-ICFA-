import streamlit as st
import requests
import re

from frontend.errors import ERROR_MESSAGES

API_URL = "http://127.0.0.1:8000"

PASSWORD_RE = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$')


def _inline_error(msg: str):
    st.markdown(
        f'<p style="color:#ef4444;font-size:0.8rem;margin-top:-0.5rem;margin-bottom:0.5rem;">⚠ {msg}</p>',
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
    .status-badge {
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 500;
    }
    .status-online  { background: #dcfce7; color: #166534; }
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

    if "show_forgot_password" not in st.session_state:
        st.session_state.show_forgot_password = False

    st.title("🔐 ICFA Login")

    try:
        requests.get(f"{API_URL}/auth/test", timeout=2)
        status, cls = "🟢 Online", "status-online"
    except Exception:
        status, cls = "🔴 Offline", "status-offline"

    _, c2, _ = st.columns([1, 4, 1])
    with c2:
        st.markdown(f'<span class="status-badge {cls}">{status}</span>', unsafe_allow_html=True)

    _, col, _ = st.columns([1, 2, 1])
    with col:

        # ── Normal Login ──
        if not st.session_state.show_forgot_password:
            st.markdown("### Sign in")
            username = st.text_input("👤 Username", key="login_username", placeholder="Enter username")
            password = st.text_input("🔒 Password", type="password", key="login_password", placeholder="Enter password")

            btn1, btn2 = st.columns([3, 1])
            with btn1:
                if st.button("Sign In", type="primary", use_container_width=True):
                    if not username or not password:
                        st.warning(f"⚠️ {ERROR_MESSAGES['LOGIN_FIELDS_REQUIRED']}")
                    else:
                        try:
                            resp = requests.post(
                                f"{API_URL}/auth/login",
                                json={"username": username, "password": password},
                                timeout=5,
                            )
                            if resp.status_code == 200:
                                data = resp.json()
                                st.session_state.logged_in = True
                                st.session_state.username = data["username"]
                                st.session_state.token = data["access_token"]
                                st.success("✅ Login successful!")
                                st.rerun()
                            else:
                                detail = resp.json().get("detail", ERROR_MESSAGES["INVALID_LOGIN"])
                                st.error(f"❌ {detail}")
                        except requests.exceptions.ConnectionError:
                            st.error(f"❌ {ERROR_MESSAGES['BACKEND_OFFLINE']}")
                        except Exception as exc:
                            st.error(f"❌ {ERROR_MESSAGES['UNEXPECTED_ERROR']}: {exc}")
            with btn2:
                if st.button("Forgot?", key="forgot_link", help="Reset your password"):
                    st.session_state.show_forgot_password = True
                    st.rerun()

        # ── Forgot Password Flow ──
        else:
            st.markdown("### 🔑 Reset Password")
            _, back_col = st.columns([3, 1])
            with back_col:
                if st.button("← Back"):
                    st.session_state.show_forgot_password = False
                    for k in ["forgot_step", "forgot_username", "forgot_question", "forgot_temp_token"]:
                        st.session_state.pop(k, None)
                    st.rerun()

            for k, v in [("forgot_step", 0), ("forgot_username", ""), ("forgot_question", ""), ("forgot_temp_token", "")]:
                if k not in st.session_state:
                    st.session_state[k] = v

            step = st.session_state.forgot_step

            # Step 0 — enter username
            if step == 0:
                st.markdown("*Step 1 of 3 — Enter your username*")
                fu = st.text_input("👤 Username", key="forgot_username_input")
                if st.button("Continue", use_container_width=True):
                    if not fu.strip():
                        st.warning(ERROR_MESSAGES["FORGOT_USERNAME_REQUIRED"])
                    else:
                        try:
                            resp = requests.post(
                                f"{API_URL}/auth/forgot-password",
                                json={"username": fu.strip()},
                                timeout=5,
                            )
                            if resp.status_code == 200:
                                st.session_state.forgot_username = fu.strip()
                                st.session_state.forgot_question = resp.json()["security_question"]
                                st.session_state.forgot_step = 1
                                st.rerun()
                            else:
                                st.error(resp.json().get("detail", ERROR_MESSAGES["FORGOT_USER_NOT_FOUND"]))
                        except Exception as exc:
                            st.error(f"{ERROR_MESSAGES['FORGOT_SERVICE_ERROR']}: {exc}")

            # Step 1 — answer security question
            elif step == 1:
                st.markdown("*Step 2 of 3 — Answer your security question*")
                st.info(f"**Q:** {st.session_state.forgot_question}")
                ans = st.text_input("🔒 Answer", type="password", key="forgot_answer")
                if st.button("Verify Answer", use_container_width=True):
                    if not ans.strip():
                        st.warning(ERROR_MESSAGES["FORGOT_ANSWER_REQUIRED"])
                    else:
                        try:
                            resp = requests.post(
                                f"{API_URL}/auth/verify-security-answer",
                                json={"username": st.session_state.forgot_username, "answer": ans},
                                timeout=5,
                            )
                            if resp.status_code == 200:
                                st.session_state.forgot_temp_token = resp.json()["temp_token"]
                                st.session_state.forgot_step = 2
                                st.rerun()
                            else:
                                st.error(resp.json().get("detail", ERROR_MESSAGES["FORGOT_WRONG_ANSWER"]))
                        except Exception as exc:
                            st.error(f"{ERROR_MESSAGES['FORGOT_SERVICE_ERROR']}: {exc}")

            # Step 2 — set new password
            elif step == 2:
                st.markdown("*Step 3 of 3 — Set a new password*")
                new_pass = st.text_input("🔐 New Password", type="password", key="new_password1")
                confirm  = st.text_input("🔐 Confirm Password", type="password", key="new_password2")

                if new_pass:
                    checks = {
                        "length":  len(new_pass) >= 8,
                        "upper":   bool(re.search(r'[A-Z]', new_pass)),
                        "lower":   bool(re.search(r'[a-z]', new_pass)),
                        "digit":   bool(re.search(r'\d', new_pass)),
                        "special": bool(re.search(r'[@$!%*?&]', new_pass)),
                    }
                    labels = {
                        "length":  "At least 8 characters",
                        "upper":   "Uppercase letter",
                        "lower":   "Lowercase letter",
                        "digit":   "Number",
                        "special": "Special character (@$!%*?&)",
                    }
                    lines = []
                    for k, label in labels.items():
                        icon  = "✅" if checks[k] else "❌"
                        color = "#22c55e" if checks[k] else "#ef4444"
                        lines.append(f'<span style="color:{color};font-size:0.78rem;">{icon} {label}</span>')
                    st.markdown(
                        '<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:0.6rem 0.9rem;margin-top:-0.4rem;margin-bottom:0.6rem;">'
                        + "<br>".join(lines)
                        + "</div>",
                        unsafe_allow_html=True,
                    )

                if confirm and new_pass != confirm:
                    _inline_error(ERROR_MESSAGES["PASSWORD_MISMATCH"])

                if st.button("Reset Password", type="primary", use_container_width=True):
                    if not new_pass or not confirm:
                        st.warning(ERROR_MESSAGES["PASSWORD_FIELDS_REQUIRED"])
                    elif new_pass != confirm:
                        st.error(f"❌ {ERROR_MESSAGES['PASSWORD_MISMATCH']}")
                    elif not PASSWORD_RE.match(new_pass):
                        st.error(f"❌ {ERROR_MESSAGES['PASSWORD_REQUIREMENTS']}")
                    else:
                        try:
                            resp = requests.post(
                                f"{API_URL}/auth/reset-password",
                                json={
                                    "temp_token": st.session_state.forgot_temp_token,
                                    "username": st.session_state.forgot_username,
                                    "new_password": new_pass,
                                },
                                timeout=5,
                            )
                            if resp.status_code == 200:
                                st.success(f"✅ {ERROR_MESSAGES['FORGOT_RESET_SUCCESS']}")
                                for k in ["forgot_step", "forgot_username", "forgot_question", "forgot_temp_token"]:
                                    st.session_state.pop(k, None)
                                st.session_state.show_forgot_password = False
                                st.rerun()
                            else:
                                st.error(resp.json().get("detail", ERROR_MESSAGES["FORGOT_RESET_FAILED"]))
                        except Exception as exc:
                            st.error(f"{ERROR_MESSAGES['FORGOT_SERVICE_ERROR']}: {exc}")