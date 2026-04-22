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

    # --- SECTION: ORGANISATION CONFIGURATION (Sentiment & Churn) ---
    st.subheader("🏢 Organisation Specific Settings")
    
    # 1. Fetch List of Organizations
    orgs = []
    try:
        org_res = requests.get(f"{API_URL}/admin/organizations", headers=get_headers())
        if org_res.status_code == 200: orgs = org_res.json()
    except: pass

    org_options = {"🌍 Global Defaults (All Users)": None}
    for o in orgs:
        org_options[f"🏢 {o['name']}"] = o['id']

    # THE SELECT BUTTON / DROPDOWN
    target_label = st.selectbox("Select Organisation to Configure:", list(org_options.keys()))
    target_org_id = org_options[target_label]

    # Fetch specific config for this target
    try:
        url = f"{API_URL}/admin/get-config"
        if target_org_id is not None: url += f"?org_id={target_org_id}"
        res_target = requests.get(url, headers=get_headers())
        target_config = res_target.json() if res_target.status_code == 200 else {}
    except:
        target_config = {}

    with st.form("unified_config_form"):
        st.info(f"Currently configuring: **{target_label}**")
        
        # --- SENTIMENT RULES ---
        st.markdown("#### 💬 Sentiment Analysis Rules")
        col1, col2 = st.columns(2)
        pos_t = col1.number_input("Positive Threshold", value=float(target_config.get("pos_threshold", 0.05)), format="%.3f", step=0.01)
        neg_t = col2.number_input("Negative Threshold", value=float(target_config.get("neg_threshold", -0.05)), format="%.3f", step=0.01)
        
        col_l1, col_l2, col_l3 = st.columns(3)
        pos_l = col_l1.text_input("Positive Label", value=target_config.get("pos_label", "Positive"))
        neg_l = col_l2.text_input("Negative Label", value=target_config.get("neg_label", "Negative"))
        neu_l = col_l3.text_input("Neutral Label", value=target_config.get("neu_label", "Neutral"))
        
        pk_col, nk_col = st.columns(2)
        pos_kw = pk_col.text_area("🟢 Positive Keywords", value=target_config.get("positive_keywords", "") or target_config.get("keyword_boosters", ""), placeholder="excellent, amazing, helpful...")
        neg_kw = nk_col.text_area("🔴 Negative Keywords", value=target_config.get("negative_keywords", ""), placeholder="broken, terrible, slow, bad...")
        
        st.divider()
        
        # --- CHURN THRESHOLDS ---
        st.markdown("#### 📉 Churn Prediction Risk Thresholds")
        col3, col4, col5 = st.columns(3)
        high_t = col3.number_input("High Risk (>)", value=float(target_config.get("high_risk_threshold", 0.70)), step=0.01)
        med_t = col4.number_input("Medium Risk (>)", value=float(target_config.get("medium_risk_threshold", 0.40)), step=0.01)
        low_t = col5.number_input("Low Risk (>)", value=float(target_config.get("low_risk_threshold", 0.10)), step=0.01)
        
        st.write("🔘 **Binary Decision Threshold**")
        pred_t = st.number_input("Churn Decision Threshold (Yes/No)", value=float(target_config.get("churn_prediction_threshold", 0.50)), step=0.01, help="Probability above this value will be marked as 'Yes' for churn.")

        if st.form_submit_button(f"💾 Save Configuration for {target_label.split(' ')[-1]}", use_container_width=True):
            payload = {
                "org_id": target_org_id,
                "pos_threshold": pos_t,
                "neg_threshold": neg_t,
                "pos_label": pos_l,
                "neg_label": neg_l,
                "neu_label": neu_l,
                "positive_keywords": pos_kw,
                "negative_keywords": neg_kw,
                "high_risk_threshold": high_t,
                "medium_risk_threshold": med_t,
                "low_risk_threshold": low_t,
                "churn_prediction_threshold": pred_t
            }
            update_res = requests.put(f"{API_URL}/admin/update-config", json=payload, headers=get_headers())
            if update_res.status_code == 200:
                st.success(f"Configuration for {target_label} updated successfully!")
            else:
                st.error("Failed to update configuration.")
