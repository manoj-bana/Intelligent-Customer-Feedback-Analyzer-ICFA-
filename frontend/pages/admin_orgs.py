import streamlit as st
import requests
import pandas as pd
import os
from frontend.errors import ERROR_MESSAGES

API_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

def get_headers():
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}

def show():
    # Reuse standard styles for inline messages
    st.markdown("""
    <style>
    .checklist-item { font-size: 0.85rem; margin-bottom: 2px; }
    .check-valid { color: #059669; }
    .check-invalid { color: #dc2626; }
    .inline-msg { font-size: 0.8rem; margin-top: -15px; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

    st.title("🏢 Organization Control")
    st.markdown("Register and manage companies within the system.")

    # Section: Create New Organization
    with st.expander("➕ Register New Organization", expanded=True):
        col1, col2 = st.columns(2)
        
        # --- Organization Name ---
        org_name = col1.text_input("Organization Name", placeholder="e.g. FinCorp", key="admin_org_name")
        name_available = True
        if org_name:
            try:
                res = requests.get(f"{API_URL}/admin/check-availability?name={org_name}", headers=get_headers())
                if res.status_code == 200 and res.json().get("exists"):
                    col1.markdown(f'<p class="inline-msg check-invalid">⚠ {ERROR_MESSAGES["ORG_NAME_TAKEN"]}</p>', unsafe_allow_html=True)
                    name_available = False
                else:
                    col1.markdown(f'<p class="inline-msg check-valid">✓ Name available</p>', unsafe_allow_html=True)
            except: pass

        # --- Unique Slug ---
        org_slug = col2.text_input("Unique Slug (ID)", placeholder="e.g. fincorp", key="admin_org_slug")
        slug_available = True
        if org_slug:
            try:
                res = requests.get(f"{API_URL}/admin/check-availability?slug={org_slug}", headers=get_headers())
                if res.status_code == 200 and res.json().get("exists"):
                    col2.markdown(f'<p class="inline-msg check-invalid">⚠ {ERROR_MESSAGES["ORG_SLUG_TAKEN"]}</p>', unsafe_allow_html=True)
                    slug_available = False
                else:
                    col2.markdown(f'<p class="inline-msg check-valid">✓ Code available</p>', unsafe_allow_html=True)
            except: pass
        
        st.info("💡 The 'Slug' is the unique code users will enter during registration.")
        
        # Action Button (Outside of form for reactivity)
        if st.button("🔨 Create Organization", use_container_width=True, type="primary"):
            if not org_name or not org_slug:
                st.error(ERROR_MESSAGES["FIELDS_REQUIRED"])
            elif not name_available or not slug_available:
                st.error("Please resolve the errors above before creating.")
            else:
                try:
                    payload = {"name": org_name, "slug": org_slug.lower().strip()}
                    res = requests.post(f"{API_URL}/admin/organizations", json=payload, headers=get_headers())
                    if res.status_code == 200:
                        st.success(f"Organization '{org_name}' created successfully!")
                        st.rerun()
                    else:
                        detail = res.json().get('detail', 'Unknown error')
                        st.error(f"Error: {detail}")
                except Exception as e:
                    st.error(f"Connection error: {e}")

    st.divider()

    # Section: List Existing Organizations
    st.subheader("📋 Registered Organizations")
    try:
        res = requests.get(f"{API_URL}/admin/organizations", headers=get_headers())
        if res.status_code == 200:
            orgs = res.json()
            if not orgs:
                st.info("No organizations registered yet.")
            else:
                df = pd.DataFrame(orgs)
                # Rename columns for display
                df = df.rename(columns={
                    "id": "Internal ID",
                    "name": "Company Name",
                    "slug": "Slug / Access Code",
                    "created_at": "Registration Date"
                })
                st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.error("Failed to fetch organizations.")
    except Exception as e:
        st.error(f"Connection error: {e}")
