import streamlit as st
import requests
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()
API_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

def get_headers():
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}

def show():
    st.title("📊 Administration Hub")
    st.markdown("Global system oversight and management.")

    tab_stats, tab_users, tab_datasets, tab_notify, tab_config = st.tabs([
        "📊 System Stats", 
        "👥 User Management", 
        "📁 Dataset Inventory",
        "📢 Broadcast",
        "⚙️ Config"
    ])

    with tab_stats:
        render_stats()

    with tab_users:
        render_users()

    with tab_datasets:
        render_datasets()
    
    with tab_notify:
        render_notifications()

    with tab_config:
        render_config()

def render_stats():
    st.subheader("📈 System Health & Metrics")
    try:
        res = requests.get(f"{API_URL}/admin/stats", headers=get_headers(), timeout=5)
        if res.status_code == 200:
            stats = res.json()
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Total Users", stats["total_users"])
            k2.metric("Total Jobs", stats["total_datasets"])
            k3.metric("Failed Jobs", stats["failed_jobs"], delta=f"{stats['failed_jobs']} failed", delta_color="inverse")
            k4.metric("Active Processing", stats["processing_jobs"])
            
            st.info(f"📊 **{stats['jobs_today']}** jobs processed in the last 24 hours.")
        else:
            st.error("Failed to fetch system stats.")
    except Exception as e:
        st.error(f"Error connecting to admin API: {e}")

def render_users():
    st.subheader("👥 Registered Users")
    try:
        res = requests.get(f"{API_URL}/admin/users", headers=get_headers(), timeout=5)
        if res.status_code == 200:
            users = res.json()["users"]
            df = pd.DataFrame(users)
            
            for i, user in df.iterrows():
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([2, 2, 1.5, 1.5])
                    
                    # Column 1: Identifying Info
                    c1.markdown(f"**{user['username']}**")
                    c1.caption(f"{user['email']}")
                    
                    # Column 2: Organization (The Requested Column)
                    c2.markdown("**Organisation**")
                    c2.info(user.get('organization', 'Individual'))
                    
                    with c3:
                        if user['role'] != 'admin':
                            if st.button("⬆️ Promote", key=f"promo_{user['id']}", use_container_width=True):
                                requests.put(f"{API_URL}/admin/users/{user['id']}/role", params={"new_role": "admin"}, headers=get_headers())
                                st.rerun()
                        else:
                            if st.button("⬇️ Demote", key=f"demo_{user['id']}", use_container_width=True):
                                requests.put(f"{API_URL}/admin/users/{user['id']}/role", params={"new_role": "user"}, headers=get_headers())
                                st.rerun()
                    
                    with c4:
                        if user['is_active']:
                            if st.button("🚫 Deactivate", key=f"deact_{user['id']}", type="secondary", use_container_width=True):
                                requests.delete(f"{API_URL}/admin/users/{user['id']}", headers=get_headers())
                                st.rerun()
                        else:
                            st.warning("Deactivated")
        else:
            st.error("Could not load users.")
    except Exception as e:
        st.error(f"Error: {e}")

    except Exception as e:
        st.error(f"Error: {e}")

def render_datasets():
    st.subheader("📁 System-Wide Datasets")
    try:
        res = requests.get(f"{API_URL}/admin/datasets", headers=get_headers(), timeout=10)
        if res.status_code == 200:
            datasets = res.json()["datasets"]
            if not datasets:
                st.info("No datasets found in the system.")
                return

            for ds in datasets:
                with st.container(border=True):
                    col1, col2 = st.columns([5, 2])
                    with col1:
                        st.markdown(f"**{ds['filename']}** (ID: `{ds['case_id']}`)")
                        st.caption(f"Owner: {ds['username']} | Type: {ds['task_type']} | Created: {ds['created_date']}")
                        
                        status = ds['review_status']
                        if status == "completed": st.success("Completed")
                        elif status == "failed": 
                            st.error(f"Failed: {ds['error_message'] or 'Unknown error'}")
                        else: st.info(status.capitalize())
                    
                    with col2:
                        if status == "failed":
                            if st.button("🔄 Retry", key=f"retry_adm_{ds['case_id']}", use_container_width=True):
                                requests.post(f"{API_URL}/admin/datasets/{ds['case_id']}/retry", headers=get_headers())
                                st.toast("Retry queued!")
                                st.rerun()
                        
                        if st.button("🗑️ Delete", key=f"del_adm_{ds['case_id']}", use_container_width=True, type="secondary"):
                            requests.delete(f"{API_URL}/admin/datasets/{ds['case_id']}", headers=get_headers())
                            st.rerun()
        else:
            st.error("Failed to load datasets.")
    except Exception as e:
        st.error(f"Error: {e}")

def render_notifications():
    st.subheader("📢 Notification Management")
    
    with st.form("broadcast_form"):
        msg = st.text_area("Broadcast Message", placeholder="Enter message for all users...")
        if st.form_submit_button("📣 Send to All Users"):
            if msg:
                res = requests.post(f"{API_URL}/admin/notifications/broadcast", params={"message": msg}, headers=get_headers())
                if res.status_code == 200: st.success("Broadcast sent!")
                else: st.error("Failed to send broadcast.")
            else:
                st.warning("Message cannot be empty.")

def render_config():
    st.subheader("⚙️ Organization Analysis Tuning")
    st.markdown("Customize analysis rules and thresholds for specific organizations.")
    
    # 0. Organization Selection
    org_id = None
    try:
        org_res = requests.get(f"{API_URL}/admin/organizations", headers=get_headers())
        if org_res.status_code == 200:
            orgs = org_res.json()
            org_options = {f"🏢 {o['name']}": o['id'] for o in orgs}
            # Allow "Global / Individual" (org_id=None)
            options = ["-- Select Option --", "🌐 Global / Individual"] + list(org_options.keys())
            selected_option = st.selectbox("Select Target to Configure", options)
            
            if selected_option == "🌐 Global / Individual":
                org_id = None
            elif selected_option != "-- Select Option --":
                org_id = org_options[selected_option]
            else:
                st.info("Please select an organization or 'Global' to view and edit settings.")
                return
        else:
            st.error("Failed to load organizations.")
            return
    except Exception as e:
        st.error(f"Error loading organizations: {e}")
        return

    # 1. Fetch Configuration
    try:
        res = requests.get(f"{API_URL}/admin/config/get", params={"org_id": org_id}, headers=get_headers())
        if res.status_code == 200:
            cfg = res.json()
            
            # Sentiment Configuration
            st.divider()
            st.markdown("### 🎭 Sentiment Engine")
            with st.form("sentiment_cfg_form"):
                c1, c2 = st.columns(2)
                pos_t = c1.slider("Positive Threshold", 0.0, 1.0, float(cfg.get("pos_threshold", 0.05)), step=0.01)
                neg_t = c2.slider("Negative Threshold", -1.0, 0.0, float(cfg.get("neg_threshold", -0.05)), step=0.01)
                
                l1, l2, l3 = st.columns(3)
                pos_l = l1.text_input("Positive Label", cfg.get("pos_label", "Positive"))
                neg_l = l2.text_input("Negative Label", cfg.get("neg_label", "Negative"))
                neu_l = l3.text_input("Neutral Label", cfg.get("neu_label", "Neutral"))
                
                boosters = st.text_area("Keyword Boosters (Optional)", cfg.get("keyword_boosters", ""), placeholder="word1, word2...")
                
                if st.form_submit_button("💾 Save Sentiment Rules"):
                    update_data = {
                        "org_id": org_id,
                        "pos_threshold": pos_t, "neg_threshold": neg_t,
                        "pos_label": pos_l, "neg_label": neg_l, "neu_label": neu_l,
                        "keyword_boosters": boosters
                    }
                    requests.put(f"{API_URL}/admin/config/update", json=update_data, headers=get_headers())
                    st.toast("Sentiment rules updated!")

            # Churn Configuration
            st.divider()
            st.markdown("### 📉 Churn Predictor")
            with st.form("churn_cfg_form"):
                st.info("Thresholds determine how customers are categorized based on their churn probability.")
                
                col1, col2 = st.columns(2)
                high_t = col1.slider("High Risk Probability (%)", 0, 100, int(float(cfg.get("high_risk_threshold", 0.70)) * 100))
                med_t = col2.slider("Medium Risk Probability (%)", 0, 100, int(float(cfg.get("medium_risk_threshold", 0.40)) * 100))
                low_t = col1.slider("Low Risk Probability (%)", 0, 100, int(float(cfg.get("low_risk_threshold", 0.10)) * 100))
                
                st.markdown("#### 🔘 Binary Prediction Threshold")
                pred_t = st.slider("Churn Decision Threshold (Yes/No) (%)", 1, 99, int(float(cfg.get("churn_prediction_threshold", 0.50)) * 100), 
                                   help="Customers with churn probability above this value will be marked as 'Yes' for churn.")

                if st.form_submit_button("💾 Save Churn Rules"):
                    update_data = {
                        "org_id": org_id,
                        "high_risk_threshold": high_t / 100.0,
                        "medium_risk_threshold": med_t / 100.0,
                        "low_risk_threshold": low_t / 100.0,
                        "churn_prediction_threshold": pred_t / 100.0
                    }
                    requests.put(f"{API_URL}/admin/config/update", json=update_data, headers=get_headers())
                    st.toast("Churn rules updated!")
        else:
            st.warning("Could not fetch configuration for this organization.")
    except Exception as e:
        st.error(f"Error: {e}")
