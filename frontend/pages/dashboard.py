import streamlit as st
import requests
import pandas as pd
from streamlit_autorefresh import st_autorefresh

API_URL = "http://127.0.0.1:8000"

def get_notifications(username):
    """
    Fetches persistent system notifications from the backend.
    """
    try:
        res = requests.get(f"{API_URL}/ingest/notifications/{username}", timeout=5)
        if res.status_code == 200:
            return res.json().get("notifications", [])
    except: pass
    return []

def inject_premium_css():
    """Injects high-end enterprise styling for glassmorphism and extreme layout density."""
    st.markdown("""
        <style>
            /* Eliminate Top Padding & Standardize Spacing */
            .block-container { padding-top: 1.5rem !important; padding-bottom: 0rem !important; }
            [data-testid="stAppViewHeader"] { display: none; } /* Hide redundant top bar if applicable */
            
            [data-testid="stMetricValue"] { font-size: 2.2rem !important; font-weight: 800 !important; }
            .kpi-container { padding: 0.5rem 0; }
            
            /* Professional Section Density */
            div[data-testid="stVerticalBlock"] > div { gap: 0.6rem !important; }
            
            .metric-card {
                padding: 1.2rem; border-radius: 14px; color: white;
                box-shadow: 0 4px 12px rgba(0,0,0,0.08); transition: all 0.2s ease;
                border: 1px solid rgba(255,255,255,0.05);
            }
            .metric-card:hover { transform: translateY(-3px); box-shadow: 0 8px 16px rgba(0,0,0,0.12); }
            
            /* High-Density Tracker Styling */
            .compact-row { font-size: 0.85rem !important; line-height: 1.2 !important; }
            hr { margin: 0.5rem 0 !important; opacity: 0.15 !important; }
            
            /* Gradients preserved */
            .grad-total { background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); }
            .grad-pending { background: linear-gradient(135deg, #92400e 0%, #f59e0b 100%); }
            .grad-processing { background: linear-gradient(135deg, #1e40af 0%, #60a5fa 100%); }
            .grad-completed { background: linear-gradient(135deg, #065f46 0%, #10b981 100%); }
        </style>
    """, unsafe_allow_html=True)

def render_kpi_card(label, value, icon, grad_class, delta=None):
    """Renders a modern analytics KPI card using CSS."""
    st.markdown(f"""
        <div class="metric-card {grad_class}">
            <div style="font-size: 2rem; margin-bottom: 0.5rem;">{icon}</div>
            <div style="font-size: 0.8rem; font-weight: 500; text-transform: uppercase; opacity: 0.8; letter-spacing: 1px;">{label}</div>
            <div style="font-size: 2.2rem; font-weight: 800; margin: 0.2rem 0;">{value}</div>
            {f'<div style="font-size: 0.8rem; font-weight: 600; opacity: 0.9;">{delta}</div>' if delta else '<div style="height:19px"></div>'}
        </div>
    """, unsafe_allow_html=True)

def show():
    """
    Main entry point for the dashboard. Handles navigation and the 
    Persistent Notification Engine with premium UI components.
    """
    inject_premium_css()
    username = st.session_state.get("username", "")
    
    # Silent 5s heartbeat for live status and notifications
    st_autorefresh(interval=5000, limit=None, key="dashboard_notif_refresh")
    
    # --- Professional Notification Engine ---
    # Polling logic: fetch fresh notifications
    all_notifs = get_notifications(username)
    unread_notifs = [n for n in all_notifs if n["is_read"] == 0]
    
    # Toast alerts for fresh high-priority notifications (Only if Unread)
    if "last_notif_ids" not in st.session_state:
        st.session_state.last_notif_ids = set()
        
    for n in unread_notifs:
        if n["id"] not in st.session_state.last_notif_ids:
            st.toast(n["message"], icon="🔔")
            st.session_state.last_notif_ids.add(n["id"])

    # Layout Header (Title + Professional Bell)
    h_col1, h_col2 = st.columns([10, 1.2])
    with h_col1:
        pass # Title handled per-page
        
    with h_col2:
        notif_count = len(unread_notifs)
        # Dynamic label with unread indicator
        label = f"🔔 ({notif_count})" if notif_count > 0 else "🔔"
        
        with st.popover(label, width='stretch'):
            st.markdown("### 📥 Notification Inbox")
            if not all_notifs:
                st.info("No system activity yet.")
            else:
                for i, n in enumerate(all_notifs[:10]): # Show last 10
                    # Professional styling for unread items
                    style = "**(New)**" if n["is_read"] == 0 else ""
                    c_n, c_v = st.columns([4, 1.2])
                    with c_n:
                        st.markdown(f"{style} {n['message']}")
                        st.caption(f"🕒 {n['created_at']}")
                    with c_v:
                        if n["is_read"] == 0:
                            if st.button("Read", key=f"read_{n['id']}_{i}"):
                                try:
                                    requests.post(f"{API_URL}/ingest/notifications/read/{n['id']}", timeout=2)
                                    st.rerun()
                                except: pass
                
                st.divider()
                st.caption("Showing 10 most recent updates.")

    # --- Sidebar UI ---
    st.sidebar.title(f"👤 {username}")
    st.sidebar.markdown("---")
    
    # Handle page persistence in query params
    pages = ["🏠 Home", "☁️ Document Ingestion", "📊 Reports"]
    query_page = st.query_params.get("page", "🏠 Home")
    page_index = 0
    if query_page in pages:
        page_index = pages.index(query_page)

    page = st.sidebar.radio(
        "Navigate",
        pages,
        index=page_index
    )
    
    # Update query params to current page if it changed
    if st.query_params.get("page") != page:
        st.query_params["page"] = page

    if st.sidebar.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.token = ""
        
        # Clear query params to prevent auto-login on refresh
        st.query_params.clear()
        
        st.rerun()

    if page == "🏠 Home":
        show_home()
    elif page == "☁️ Document Ingestion":
        from frontend.pages import ingestion
        ingestion.show()
    elif page == "📊 Reports":
        st.title("📊 Analysis Reports")
        st.markdown("Select a report module:")
        tab1, tab2 = st.tabs(["💬 Sentiment Analysis", "📉 Churn Prediction"])
        with tab1:
            from frontend.pages import feedback_page
            feedback_page.show()
        with tab2:
            from frontend.pages import churn_page
            churn_page.show()

def get_cases(username):
    """
    Fetches the latest analysis cases from the backend. 
    Caching removed to ensure 100% status-notification synchronization.
    """
    try:
        res = requests.get(f"{API_URL}/ingest/cases/{username}", timeout=10)
        if res.status_code == 200:
            return res.json().get("cases", [])
    except Exception:
        pass
    return []

def show_home():
    """
    Main home dashboard view. Displays fresh metrics and styled cases list.
    Standardized width standards preserved.
    """
    username = st.session_state.get("username", "User")
    st.title("📊 ICFA Analytics Master")
    st.markdown(f"**Welcome back,** {username} 👋")

    cases_data = get_cases(username)
    
    # Calculate live metrics locally for maximum speed
    total_datasets = len(cases_data)
    pending = len([c for c in cases_data if str(c.get("review_status")).lower() == "pending"])
    processing = len([c for c in cases_data if str(c.get("review_status")).lower() == "processing"])
    completed = len([c for c in cases_data if str(c.get("review_status")).lower() == "completed"])
    
    success_rate = 100
    if total_datasets > 0:
        success_rate = round((completed / total_datasets * 100))

    # --- Premium KPI Row ---
    k1, k2, k3, k4 = st.columns(4)
    with k1: render_kpi_card("Total Datasets", total_datasets, "📊", "grad-total", f"↑ {success_rate}% Success")
    with k2: render_kpi_card("Awaiting Queue", pending, "⏳", "grad-pending", f"{pending} in queue" if pending > 0 else "System Clear")
    with k3: render_kpi_card("Processing", processing, "🔄", "grad-processing", "Live analysis...")
    with k4: render_kpi_card("Completed", completed, "✅", "grad-completed", "Ready for review")
    
    st.markdown("---")
    
    # Delegate to the high-speed data fragment
    render_cases_fragment(cases_data)

@st.fragment
def render_cases_fragment(cases_data):
    """
    Renders the cases list in a professionally styled container.
    """
    st.subheader("📋 Dataset Lifecycle Tracker")
    
    if not cases_data:
        st.info("No cases found. Navigate to `Document Ingestion` to upload your first dataset!")
        return

    # Dual-column Search and Clear Interface (Pre-instantiation order)
    s_col1, s_col2 = st.columns([10, 2])
    
    with s_col2:
        st.write("<div style='height:31px'></div>", unsafe_allow_html=True)
        if st.button("✖️ Clear", use_container_width=True, key="clear_search_btn"):
             st.session_state.dash_search_in = ""
             st.rerun(scope="fragment")

    with s_col1:
        search = st.text_input("🔍 Search reports...", placeholder="Enter ID, filename, or type...", key="dash_search_in")

    filtered_cases = [
        c for c in cases_data 
        if not search 
        or search.lower() in c['filename'].lower() 
        or search.lower() in c['task_type'].lower()
        or search.lower() in str(c['case_id']).lower()
    ]

    # Higher Density Headers
    h_cols = st.columns([1.5, 3.5, 2, 1.5, 2, 1.5]) 
    h_cols[0].markdown("<small><b>ID</b></small>", unsafe_allow_html=True)
    h_cols[1].markdown("<small><b>Filename</b></small>", unsafe_allow_html=True)
    h_cols[2].markdown("<small><b>Type</b></small>", unsafe_allow_html=True)
    h_cols[3].markdown("<small><b>Status</b></small>", unsafe_allow_html=True)
    h_cols[4].markdown("<small><b>Date</b></small>", unsafe_allow_html=True)
    h_cols[5].markdown("<small><b>Action</b></small>", unsafe_allow_html=True)
    
    # --- Pagination Logic ---
    items_per_page = 5 
    total_items = len(filtered_cases)
    total_pages = (total_items - 1) // items_per_page + 1 if total_items > 0 else 1
    if "current_page" not in st.session_state: st.session_state.current_page = 1
    if st.session_state.current_page > total_pages: st.session_state.current_page = total_pages
    
    # Paged Display
    start_idx = (st.session_state.current_page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    paged_cases = filtered_cases[start_idx:end_idx]
    
    for i, c in enumerate(paged_cases):
        st.markdown('<div class="compact-row">', unsafe_allow_html=True)
        st.divider()
        c_id, c1, c2, c3, c4, c5 = st.columns([1.5, 3.5, 2, 1.5, 2, 1.5])
        c_id.caption(f"`{c['case_id']}`")
        c1.markdown(f"<p style='font-size:0.9rem; margin-bottom:0;'><b>{c['filename']}</b></p>", unsafe_allow_html=True)
        c2.markdown(f"<p style='font-size:0.85rem; opacity:0.8; margin-bottom:0;'>{c['task_type'][:15]}..</p>" if len(c['task_type']) > 15 else f"<p style='font-size:0.85rem; opacity:0.8; margin-bottom:0;'>{c['task_type']}</p>", unsafe_allow_html=True)
        
        status = str(c.get("review_status")).lower()
        if status == "completed":
            c3.success("✅ Done")
        elif status == "processing":
            c3.info("🔄 Active")
        elif status == "pending":
            c3.warning("⏳ Queue")
        elif "fail" in status or "error" in status:
            c3.error("❌ Fail")
        else:
            c3.caption(status.capitalize())
            
        c4.caption(c.get("created_date", "N/A"))
        
        if status == "completed":
            if c5.button("📊 Open", key=f"view_dash_{c['case_id']}_{i}", use_container_width=True):
                st.query_params["page"] = "📊 Reports"
                st.query_params["case_id"] = c["case_id"]
                st.rerun()
        else:
            c5.button("⏳..", key=f"wait_dash_{c['case_id']}_{i}", disabled=True, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # Minimalist Pagination Controls
    st.divider()
    pg1, pg2, pg3 = st.columns([1, 2, 1])
    with pg1:
        if st.button("⬅️ Previous", disabled=st.session_state.current_page <= 1, width='stretch', key="pg_prev_btn"):
            st.session_state.current_page -= 1
            st.rerun(scope="fragment")
    with pg2:
        st.markdown(f"<div style='text-align: center; font-size: 0.9rem; opacity: 0.7;'>Page {st.session_state.current_page} of {total_pages}</div>", unsafe_allow_html=True)
    with pg3:
        if st.button("Next ➡️", disabled=st.session_state.current_page >= total_pages, width='stretch', key="pg_next_btn"):
            st.session_state.current_page += 1
            st.rerun(scope="fragment")
            
    st.markdown("---")

    st.divider()
    
    # --- Dataset Management ---
    if cases_data:
        st.subheader("🗑️ Manage & Delete Datasets")
        st.markdown("Select a dataset below to delete it from the system or retry stalled processing.")
        
        # All cases are now manageable
        case_lookup = {c['case_id']: c for c in cases_data}
        case_mapping = {f"{c['filename']} (ID: {c['case_id']}, Status: {c['review_status']})": c['case_id'] for c in cases_data}
        
        selected_case_label = st.selectbox("Select Dataset to Manage", list(case_mapping.keys()), key="manage_case_selector")
        selected_case_id = case_mapping[selected_case_label]
        selected_case = case_lookup[selected_case_id]
        
        col_act1, col_act2 = st.columns([1, 4])
        with col_act1:
            # Only show Retry button for stalled/error cases
            if "Completed" not in selected_case["review_status"]:
                if st.button("🔄 Retry", width='stretch', key="btn_retry_case"):
                    try:
                        retry_res = requests.post(f"{API_URL}/ingest/cases/{selected_case_id}/retry", timeout=5)
                        if retry_res.status_code == 200:
                            st.success("Task added back to queue!")
                            st.rerun()
                        else:
                            st.error(f"Server error: {retry_res.text}")
                    except Exception as e:
                        st.error(f"Connection error: {e}")
            else:
                if st.button("📊 View Reports", width='stretch', key=f"btn_go_report_{selected_case_id}"):
                    st.query_params["page"] = "📊 Reports"
                    st.rerun()
                
        with col_act2:
            # Check if this specific case ID is currently in the 'confirmation' state
            if st.session_state.get('confirm_delete_id') == selected_case_id:
                st.warning(f"⚠️ Are you sure you want to delete **{selected_case['filename']}**?")
                cy, cn = st.columns(2)
                with cy:
                    if st.button("✅ Yes, Delete", key=f"btn_dy_{selected_case_id}", width='stretch'):
                        try:
                            # Perform deletion request
                            del_res = requests.delete(f"{API_URL}/ingest/cases/{selected_case_id}", timeout=5)
                            if del_res.status_code == 200:
                                # Clear confirmation state
                                st.session_state.confirm_delete_id = None
                                
                                # Clear our data cache instantly so the dashboard updates without delay
                                # Cache clear removed for 0-cache performance sync
                                pass
                                
                                st.toast(f"Dataset {selected_case_id} deleted successfully!", icon="🗑️")
                                st.rerun()
                            else:
                                st.error(f"Server error: {del_res.text}")
                        except Exception as e:
                            st.error(f"Connection error: {e}")
                with cn:
                    if st.button("❌ Cancel", key=f"btn_dn_{selected_case_id}", width='stretch'):
                        st.session_state.confirm_delete_id = None
                        st.rerun()
            else:
                # Initial delete button
                if st.button("🗑️ Delete Dataset", key=f"btn_del_{selected_case_id}", width='stretch'):
                    st.session_state.confirm_delete_id = selected_case_id
                    st.rerun()

