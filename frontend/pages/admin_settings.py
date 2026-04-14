import streamlit as st
import requests
import os

API_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

def get_headers():
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}

def show():
   
    st.title("⚙️ Admin System Settings")
    st.markdown("Configure global thresholds, keywords, and churn rules.")
    
    # Fetch current config
    try:
        res = requests.get(f"{API_URL}/admin/get-config", headers=get_headers())
        config = res.json() if res.status_code == 200 else {}
    except:
        config = {}

    with st.form("admin_config_form"):
        st.subheader("💬 Sentiment Configuration")
        col1, col2 = st.columns(2)
        pos_t = col1.number_input("Positive Threshold", value=config.get("pos_threshold", 0.05))
        neg_t = col2.number_input("Negative Threshold", value=config.get("neg_threshold", -0.05))
        
        keywords = st.text_area("Keyword Boosters (comma separated)", value=config.get("keyword_boosters", ""))
        
        st.divider()
        st.subheader("📉 Churn Risk Thresholds")
        col3, col4 = st.columns(2)
        high_t = col3.number_input("High Risk (>)", value=config.get("high_risk_threshold", 0.70))
        med_t = col4.number_input("Medium Risk (>)", value=config.get("medium_risk_threshold", 0.40))
        
        submitted = st.form_submit_button("💾 Save All Configurations", use_container_width=True)
        
        if submitted:
            payload = {
                "pos_threshold": pos_t,
                "neg_threshold": neg_t,
                "keyword_boosters": keywords,
                "high_risk_threshold": high_t,
                "medium_risk_threshold": med_t
            }
            try:
                update_res = requests.put(f"{API_URL}/admin/update-config", json=payload, headers=get_headers())
                if update_res.status_code == 200:
                    st.success("Configuration updated successfully!")
                else:
                    st.error("Failed to update configuration.")
            except:
                st.error("Connection error.")
