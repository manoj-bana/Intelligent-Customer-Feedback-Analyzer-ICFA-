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

    # Section: Manage / Delete Organization
    st.subheader("🗑️ Manage / Delete Organization")
    try:
        res = requests.get(f"{API_URL}/admin/organizations", headers=get_headers())
        if res.status_code == 200:
            orgs = res.json()
            if orgs:
                org_map = {f"🏢 {o['name']} ({o['slug']})": o['id'] for o in orgs}
                selected_label = st.selectbox("Select Organization to Remove", ["-- Select --"] + list(org_map.keys()), key="man_del_org_sel")
                
                if selected_label != "-- Select --":
                    selected_id = org_map[selected_label]
                    if st.button("🚨 Delete Selected Organization", type="secondary"):
                        st.session_state[f"confirm_delete_org_{selected_id}"] = True
                    
                    if st.session_state.get(f"confirm_delete_org_{selected_id}"):
                        st.error(f"⚠️ **DANGER:** Deleting this organization will wipe all its users and datasets. This cannot be undone.")
                        c1, c2 = st.columns(2)
                        if c1.button("🔥 Yes, Delete", key=f"yes_del_{selected_id}", type="primary", use_container_width=True):
                            del_res = requests.delete(f"{API_URL}/admin/organizations/{selected_id}", headers=get_headers())
                            if del_res.status_code == 200:
                                st.success("Organization deleted.")
                                del st.session_state[f"confirm_delete_org_{selected_id}"]
                                st.rerun()
                            else:
                                st.error("Failed to delete.")
                        if c2.button("❌ Cancel", key=f"no_del_{selected_id}", use_container_width=True):
                            del st.session_state[f"confirm_delete_org_{selected_id}"]
                            st.rerun()
            else:
                st.info("No organizations available to manage.")
        else:
            st.error("Could not load organizations for dismissal.")
    except Exception as e:
        st.error(f"Error loading management tools: {e}")

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
