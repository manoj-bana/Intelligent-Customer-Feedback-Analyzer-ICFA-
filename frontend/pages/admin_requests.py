import streamlit as st
import requests
import pandas as pd

API_URL = "http://127.0.0.1:8000"

def show():
    st.title("🛡️ Admin Requests Dashboard")
    st.markdown("---")
    
    username = st.session_state.get("username", "")
    if not username:
        st.error("You must be logged in to view this page.")
        return
        
    try:
        # Check role
        role_res = requests.get(f"{API_URL}/admin/check-role/{username}", timeout=5)
        if role_res.status_code == 200:
            role = role_res.json().get("role", "user")
        else:
            role = "user"
    except Exception as e:
        role = "user"

    is_admin = role == "admin"
    
    if is_admin:
        show_admin_manager_view(username)
    else:
        show_user_request_view(username)

def show_user_request_view(username: str):
    st.markdown("### Request Admin Access")
    st.info("You currently have standard user privileges. You can submit a request below to gain admin access.")
    
    # Check for pending requests first
    has_pending = False
    reqs = []
    try:
        res = requests.get(f"{API_URL}/admin/requests/{username}", timeout=5)
        if res.status_code == 200:
            reqs = res.json()
            if any(r.get('status') == 'pending' for r in reqs):
                has_pending = True
    except Exception:
        pass
        
    if has_pending:
        st.info("Request already sent")
        st.button("Request for Admin", disabled=True)
    else:
        reason = st.text_area("Reason for requesting admin access:")
        if st.button("Request for Admin"):
            if not reason.strip():
                st.warning("Please provide a valid reason.")
            else:
                try:
                    res = requests.post(
                        f"{API_URL}/admin/request",
                        json={"username": username, "reason": reason},
                        timeout=5
                    )
                    if res.status_code == 200:
                        st.success("✅ Request submitted successfully!")
                        st.rerun()
                    elif res.status_code == 400:
                        st.error(f"❌ {res.json().get('detail', 'Bad Request')}")
                    else:
                        st.error("❌ Failed to submit request.")
                except Exception as e:
                    st.error("❌ Service error. Please try again later.")
                    
    st.divider()
    st.markdown("### My Requests")
    
    if reqs:
        for r in reqs:
            status = r['status'].lower()
            if status == "pending":
                badge = "🟡 Pending"
            elif status == "approved":
                badge = "🟢 Approved"
            else:
                badge = "🔴 Rejected"
            
            st.markdown(f"""
            **Request ID**: {r['id']} | **Date**: {r['created_at']}  
            **Reason**: {r['reason']}  
            **Status**: {badge}
            """)
            st.markdown("---")
    else:
        st.write("No requests found.")


def show_admin_manager_view(manager_username: str):
    st.markdown("### Manage Admin Requests")
    st.info("As an admin, you can approve or reject admin access requests from other users.")
    
    status_filter = st.radio(
        "Filter by Status:",
        ["All", "Pending", "Approved", "Rejected"],
        horizontal=True
    )
    filter_val = status_filter.lower()
    
    try:
        url = f"{API_URL}/admin/requests?manager_username={manager_username}"
        if filter_val != "all":
            url += f"&status={filter_val}"
            
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            reqs = res.json()
            
            pending_reqs = [r for r in reqs if r["status"] == "pending"]
            history_reqs = [r for r in reqs if r["status"] != "pending"]
            
            if filter_val in ["all", "pending"]:
                st.subheader("Pending Requests")
                if not pending_reqs:
                    st.write("No pending requests.")
                else:
                    for r in pending_reqs:
                        with st.expander(f"Request #{r['id']} from {r['username']} (Date: {r['created_at']})", expanded=True):
                            st.write(f"**Reason:** {r['reason']}")
                            col1, col2 = st.columns([1, 1])
                            with col1:
                                if st.button(f"✅ Approve #{r['id']}"):
                                    process_request(r['id'], "approved", manager_username)
                            with col2:
                                if st.button(f"❌ Reject #{r['id']}"):
                                    process_request(r['id'], "rejected", manager_username)
            
            if filter_val in ["all", "approved", "rejected"]:
                st.divider()
                st.subheader("Request History")
                if not history_reqs:
                    st.write("No history.")
                else:
                    df = pd.DataFrame(history_reqs)
                    df = df[['id', 'username', 'reason', 'status', 'created_at']]
                    
                    # Apply emojis to status
                    def map_status_emoji(val):
                        val = str(val).lower()
                        if val == 'pending': return '🟡 Pending'
                        if val == 'approved': return '🟢 Approved'
                        if val == 'rejected': return '🔴 Rejected'
                        return val
                    
                    df['status'] = df['status'].apply(map_status_emoji)
                    
                    # Apply color styling
                    def color_status(val):
                        if '🟢' in val: color = '#16a34a'
                        elif '🔴' in val: color = '#dc2626'
                        else: color = 'black'
                        return f'color: {color}'
                        
                    st.dataframe(df.style.map(color_status, subset=['status']), use_container_width=True)
                
        else:
            st.error("Failed to load requests.")
    except Exception as e:
        st.error(f"Service error while loading requests. {e}")
        
def process_request(req_id: int, status: str, manager_username: str):
    try:
        res = requests.put(
            f"{API_URL}/admin/requests/{req_id}",
            json={"status": status, "manager_username": manager_username},
            timeout=5
        )
        if res.status_code == 200:
            st.success(f"Request {status} successfully.")
            st.rerun()
        else:
            st.error(f"Failed to update request: {res.json().get('detail')}")
    except Exception:
        st.error("Service error while updating request.")
