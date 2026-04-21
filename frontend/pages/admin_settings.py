import streamlit as st
import requests
import os

API_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

def get_headers():
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}

def show():
    st.title("⚙️ Admin System Settings")
    st.markdown("Configure global sentiment rules and custom churn thresholds for each organisation.")
    
    # 1. Fetch GLOBAL config (Sentiment usually stays global)
    try:
        res_global = requests.get(f"{API_URL}/admin/get-config", headers=get_headers())
        global_config = res_global.json() if res_global.status_code == 200 else {}
    except:
        global_config = {}

    # --- SECTION: GLOBAL SENTIMENT ---
    with st.form("sentiment_config_form"):
        st.subheader("💬 Global Sentiment Configuration")
        col1, col2 = st.columns(2)
        pos_t = col1.number_input("Positive Threshold", value=global_config.get("pos_threshold", 0.05), format="%.3f")
        neg_t = col2.number_input("Negative Threshold", value=global_config.get("neg_threshold", -0.05), format="%.3f")
        keywords = st.text_area("Keyword Boosters (comma separated)", value=global_config.get("keyword_boosters", ""))
        
        if st.form_submit_button("💾 Save Global Sentiment Settings", use_container_width=True):
            payload = {"pos_threshold": pos_t, "neg_threshold": neg_t, "keyword_boosters": keywords}
            requests.put(f"{API_URL}/admin/update-config", json=payload, headers=get_headers())
            st.success("Global sentiment settings saved.")

    st.divider()

    # --- SECTION: ORGANISATION-SPECIFIC CHURN ---
    st.subheader("📉 Organisation Churn Thresholds")
    
    # 1. Fetch List of Organizations
    orgs = []
    try:
        org_res = requests.get(f"{API_URL}/admin/organizations", headers=get_headers())
        if org_res.status_code == 200: orgs = org_res.json()
    except: pass

    org_options = {"🌍 Global Defaults (All Users)": None}
    for o in orgs:
        org_options[f"🏢 {o['name']}"] = o['id']

    # THE SELECT BUTTON / DROPDOWN (Beside the thresholds)
    sel_col1, sel_col2 = st.columns([2, 1])
    target_label = sel_col1.selectbox("Select Organisation to Configure Churn:", list(org_options.keys()))
    target_org_id = org_options[target_label]

    # Fetch specific churn thresholds for this target
    try:
        url = f"{API_URL}/admin/get-config"
        if target_org_id is not None: url += f"?org_id={target_org_id}"
        res_target = requests.get(url, headers=get_headers())
        target_config = res_target.json() if res_target.status_code == 200 else {}
    except:
        target_config = {}

    with st.form("churn_config_form"):
        st.caption(f"Configuring churn for: **{target_label}**")
        col3, col4, col5 = st.columns(3)
        high_t = col3.number_input("High Risk (>)", value=target_config.get("high_risk_threshold", 0.70), step=0.01)
        med_t = col4.number_input("Medium Risk (>)", value=target_config.get("medium_risk_threshold", 0.40), step=0.01)
        low_t = col5.number_input("Low Risk (>)", value=target_config.get("low_risk_threshold", 0.10), step=0.01)
        
        st.write("🔘 **Binary Decision Threshold**")
        pred_t = st.number_input("Churn Decision Threshold (Yes/No)", value=target_config.get("churn_prediction_threshold", 0.50), step=0.01, help="Probability above this value will be marked as 'Yes' for churn.")

        if st.form_submit_button(f"💾 Save Churn Thresholds for {target_label.split(' ')[-1]}", use_container_width=True):
            payload = {
                "org_id": target_org_id,
                "high_risk_threshold": high_t,
                "medium_risk_threshold": med_t,
                "low_risk_threshold": low_t,
                "churn_prediction_threshold": pred_t
            }
            update_res = requests.put(f"{API_URL}/admin/update-config", json=payload, headers=get_headers())
            if update_res.status_code == 200:
                st.success(f"Churn thresholds for {target_label} updated!")
                # Removed st.rerun() to prevent the success message from disappearing
            else:
                st.error("Failed to update.")
