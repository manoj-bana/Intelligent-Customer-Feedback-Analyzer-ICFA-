import streamlit as st
import requests
import pandas as pd
from streamlit_autorefresh import st_autorefresh

from frontend.errors import ERROR_MESSAGES
import re

API_URL = "http://127.0.0.1:8000"

def get_notifications(username):
    """
    Fetches persistent system notifications from the backend.
    """
    try:
        res = requests.get(f"{API_URL}/ingest/notifications/{username}", timeout=3)
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
    """
    Renders a modern analytics KPI card using premium gradients and styling.
    """
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
    Main entry point for the ICFA Master Dashboard.
    Handles navigation and the High-Performance Notification Engine.
    """
    inject_premium_css()
    username = st.session_state.get("username", "User")
    
    # Silent 5s heartbeat for zero-cache live status updates
    # st_autorefresh(interval=5000, key="master_dash_sync")

    # Fetch notifications early for sidebar badges
    all_notifs = get_notifications(username)
    unread_notifs = [n for n in all_notifs if n["is_read"] == 0]
    query_page = st.query_params.get("page", "🏠 Home")
    role = st.session_state.get("role", "user")

    # --- Sidebar UI Navigation Hub ---
    def nav_link(label, page_name, current_page, is_indented=False):
        is_active = (current_page == page_name)
        prefix = "&nbsp;&nbsp;" if is_indented else ""
        btn_label = f"{prefix}{label}"
        
        # Use a more compact styling for links
        cols = st.sidebar.columns([12, 1])
        with cols[0]:
            if st.button(btn_label, use_container_width=True, type="primary" if is_active else "secondary", key=f"nav_{page_name}"):
                st.query_params["page"] = page_name
                st.rerun()

    # --- Sidebar UI ---
    st.sidebar.markdown(f"<div style='text-align: center; padding-bottom: 10px;'><h3>👤 {username}</h3><p style='font-size:0.8rem; color:gray; margin-top:-15px;'>{role.capitalize()} • Online</p></div>", unsafe_allow_html=True)
    nav_link("⚙️ Manage Profile", "👤 Manage Profile", query_page)
    st.sidebar.divider()

    # Collapsible Navigate Section
    with st.sidebar.expander("📌 Navigate", expanded=(query_page in ["🏠 Home", "📄 Upload Feedback", "📊 Upload Churn Data"])):
        nav_link("🏠 Home", "🏠 Home", query_page)
        nav_link("📄 Feedbacks", "📄 Upload Feedback", query_page)
        nav_link("📊 Churn", "📊 Upload Churn Data", query_page)

    # Collapsible Analytics Section
    with st.sidebar.expander("📊 Analytics", expanded=(query_page in ["💬 Sentiment Dashboard", "📉 Churn Insights", "🔑 Keyword Analysis", "📈 Trends (NEW)"])):
        nav_link("💬 Sentiment", "💬 Sentiment Dashboard", query_page)
        nav_link("📉 Churn", "📉 Churn Insights", query_page)
        nav_link("🔑 Keywords", "🔑 Keyword Analysis", query_page)
        nav_link("📈 Trends", "📈 Trends (NEW)", query_page)

    # Collapsible Management Section
    with st.sidebar.expander("📂 Management", expanded=(query_page in ["📁 Upload History (NEW)", "📋 My Reports"])):
        nav_link("📁 History", "📁 Upload History (NEW)", query_page)
        nav_link("📋 Reports", "📋 My Reports", query_page)

    # Collapsible System Options (Admin Only)
    if role == "admin":
        with st.sidebar.expander("👑 Admin Control", expanded=(query_page in ["👑 Admin Panel", "👥 Manage Users"])):
            nav_link("👑 Panel", "👑 Admin Panel", query_page)
            nav_link("👥 Users", "👥 Manage Users", query_page)

    # Settings at Bottom
    st.sidebar.markdown("<div style='height: 10vh;'></div>", unsafe_allow_html=True)
    st.sidebar.divider()
    dark_mode = st.sidebar.toggle("🌙 Dark Mode")
    if dark_mode: st.session_state.theme = "dark"
    else: st.session_state.theme = "light"
    
    if st.sidebar.button("🚪 Logout", type="primary", use_container_width=True):
        st.session_state.logged_in = False
        st.query_params.clear()
        st.rerun()

    # Reuse CSS patterns from login/register for consistency
    st.markdown("""
        <style>
        /* Hide Streamlit Password Eye Icon Fix */
        [data-testid="stTextInput"] [data-testid="styled-input-container"] button { display: none !important; }
        .checklist-item { font-size: 0.85rem; margin-bottom: 2px; }
        .check-valid { color: #059669; }
        .check-invalid { color: #dc2626; }
        .inline-msg { font-size: 0.8rem; margin-top: -15px; margin-bottom: 10px; }
        
        /* Make sidebar buttons hyper-compact to prevent scrolling */
        [data-testid="stSidebar"] button {
            padding: 0.25rem 0.5rem !important;
            min-height: 2rem !important;
            margin-bottom: -5px !important;
        }
        [data-testid="stSidebar"] button[kind="secondary"] {
            border: none !important;
            background: transparent !important;
            box-shadow: none !important;
        }
        /* Reduce vertical space for headers/dividers */
        [data-testid="stSidebar"] hr {
            margin: 0.5em 0px !important;
        }
        [data-testid="stSidebar"] h4 {
            padding-top: 0.2rem !important;
            padding-bottom: 0rem !important;
        }
        /* Shrink container paddings */
        [data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {
            padding: 0.5rem !important;
        }
        """ + (
        """
        /* Sidebar Dark Mode Injection */
        [data-testid="stSidebar"] {
            background-color: #111827 !important;
            color: white !important;
        }
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] div,
        [data-testid="stSidebar"] h3, 
        [data-testid="stSidebar"] h4,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] p {
            color: #f3f4f6 !important;
        }
        [data-testid="stSidebar"] button[kind="secondary"] {
            color: #d1d5db !important;
        }
        [data-testid="stSidebar"] [data-testid="stExpander"] {
            background-color: #1f2937 !important;
            border-color: #374151 !important;
        }
        """ if st.session_state.get("theme") == "dark" else "") + """
        </style>
    """, unsafe_allow_html=True)

    @st.fragment(run_every=4)
    def render_notification_center(username_val):
        all_notifs_local = get_notifications(username_val)
        unread_notifs_local = [n for n in all_notifs_local if n["is_read"] == 0]

        # Toast alerts for fresh high-priority notifications
        if "last_notif_ids" not in st.session_state: st.session_state.last_notif_ids = set()
        for n in unread_notifs_local:
            if n["id"] not in st.session_state.last_notif_ids:
                st.toast(n["message"], icon="🔔")
                st.session_state.last_notif_ids.add(n["id"])

        notif_label = f"🔔 {len(unread_notifs_local)}" if unread_notifs_local else "🔔"
        with st.popover(notif_label, use_container_width=True):
            st.markdown("### 📥 System Updates")
            if not all_notifs_local: st.info("No activity yet.")
            else:
                for i, n in enumerate(all_notifs_local[:8]):
                    style = "**(New)**" if n["is_read"] == 0 else ""
                    cn, cv = st.columns([4, 1.2])
                    with cn: st.markdown(f"{style} {n['message']}\n<small>{n['created_at']}</small>", unsafe_allow_html=True)
                    with cv:
                        if n["is_read"] == 0:
                            if st.button("✓", key=f"rd_{n['id']}_{i}"):
                                try: requests.post(f"{API_URL}/ingest/notifications/read/{n['id']}", timeout=2); st.rerun(scope="fragment")
                                except: pass
                st.divider()
                st.caption("Latest events shown.")

    # Header with Notification Center
    h_col1, h_col2 = st.columns([10, 2])
    with h_col2:
        render_notification_center(username)

    is_profile_page = (query_page == "👤 Manage Profile")
    if is_profile_page: show_profile_management()
    # Ingest routes (Groups all new upload navigation shortcuts to ingestion page)
    elif query_page in ["☁️ Document Ingestion", "📄 Upload Feedback", "📊 Upload Churn Data", "📁 Upload History (NEW)"]:
        from frontend.pages import ingestion
        ingestion.show()
    # Analytics & Reports routes (Groups all analytical pages to reports hub)
    elif query_page in ["📊 Reports", "📋 My Reports", "💬 Sentiment Dashboard", "📉 Churn Insights", "🔑 Keyword Analysis", "📈 Trends (NEW)"]:
        show_reports_tab()
    # Notification & Admin routes
    elif query_page == "🔔 Notifications":
        st.title("🔔 Notifications Center")
        st.info("Check back soon for advanced real-time alerts. Use the bell icon at the top right for now.")
    elif query_page in ["👑 Admin Panel", "👥 Manage Users"]:
        st.title(query_page)
        st.warning("Admin UI module not fully implemented yet. Please manage users directly via the backend database.")
    # Default
    else: show_home()

def show_home():
    """
    Main home dashboard view. Displays fresh metrics and styled cases list.
    """
    username = st.session_state.get("username", "User")
    st.title("📊 ICFA Analytics Master")
    st.markdown(f"**Welcome back,** {username} 👋")

    # Call the isolated auto-refreshing fragment
    render_live_home_metrics(username)

@st.fragment(run_every=5)
def render_live_home_metrics(username):
    # Fetch live data internally so the numbers ACTUALLY update across polling!
    cases_data = get_cases(username)
    total_datasets = len(cases_data)
    pending = len([c for c in cases_data if str(c.get("review_status")).lower() == "pending"])
    processing = len([c for c in cases_data if str(c.get("review_status")).lower() == "processing"])
    completed = len([c for c in cases_data if str(c.get("review_status")).lower() == "completed"])
    
    success_rate = round((completed / total_datasets * 100)) if total_datasets > 0 else 100

    # KPI Row
    k1, k2, k3, k4 = st.columns(4)
    with k1: render_kpi_card("Total Datasets", total_datasets, "📊", "grad-total", f"↑ {success_rate}% Success")
    with k2: render_kpi_card("Awaiting Queue", pending, "⏳", "grad-pending", f"{pending} in queue")
    with k3: render_kpi_card("Processing", processing, "🔄", "grad-processing", "Live analysis...")
    with k4: render_kpi_card("Completed", completed, "✅", "grad-completed", "Ready for review")
    
    st.markdown("---")
    
    # Insights Section moved from Sidebar for better readability
    with st.container(border=True):
        c_i1, c_i2 = st.columns([1, 4])
        with c_i1:
            st.markdown("<h2 style='margin:0;'>💡</h2>", unsafe_allow_html=True)
        with c_i2:
            st.subheader("Intelligence Snapshot")
            st.markdown("⭐ **Satisfaction High:** Most analyzed customer feedback remains positive.")
            st.markdown("⚠️ **Operational Alert:** Recent reports suggest minor delays in logistics/shipping.")

    st.markdown("---")
    render_cases_fragment(cases_data)

def show_profile_management():
    st.title("👤 Account Management")
    st.markdown("Update your account security settings below.")
    st.divider()
    username = st.session_state.get("username", "")
    
    with st.container(border=True):
        st.subheader("Security Settings")
        old_p = st.text_input("Current Password", type="password", key="p_old")
        is_old_valid = False
        if old_p:
            try:
                res = requests.post(f"{API_URL}/auth/login", json={"username": username, "password": old_p}, timeout=5)
                if res.status_code == 200:
                    st.markdown('<p class="inline-msg check-valid">✓ Current password verified</p>', unsafe_allow_html=True)
                    is_old_valid = True
                else: st.markdown('<p class="inline-msg check-invalid">❌ Incorrect current password</p>', unsafe_allow_html=True)
            except: pass

        new_p = st.text_input("New Password", type="password", key="p_new")
        rules = [(len(new_p) >= 8, "8+ chars"), (bool(re.search(r'[A-Z]', new_p)), "Uppercase"), (bool(re.search(r'[a-z]', new_p)), "Lowercase"), (bool(re.search(r'\d', new_p)), "Number"), (bool(re.search(r'[@$!%*?&]', new_p)), "Special")]
        if new_p:
            if new_p == old_p and is_old_valid: st.markdown('<p class="inline-msg check-invalid">❌ Cannot reuse old password</p>', unsafe_allow_html=True)
            for v, l in rules:
                st.markdown(f'<div class="checklist-item {"check-valid" if v else "check-invalid"}">{"✅" if v else "❌"} {l}</div>', unsafe_allow_html=True)

        conf_p = st.text_input("Confirm New Password", type="password", key="p_conf")
        if conf_p:
            if new_p == conf_p: st.markdown('<p class="inline-msg check-valid">✓ Match confirmed</p>', unsafe_allow_html=True)
            else: st.markdown('<p class="inline-msg check-invalid">⚠️ Passwords do not match</p>', unsafe_allow_html=True)

        if st.button("🛡️ Update Password", use_container_width=True, type="primary"):
            if not is_old_valid: st.error("Current password verification failed.")
            elif new_p != conf_p: st.error("Passwords do not match.")
            elif not all(r[0] for r in rules): st.error("Password requirements not met.")
            else:
                try:
                    res = requests.post(f"{API_URL}/auth/change-password", json={"username": username, "old_password": old_p, "new_password": new_p}, timeout=10)
                    if res.status_code == 200: st.success("✅ Password updated successfully!"); st.toast("Credentials updated!")
                    else: st.error(f"❌ {res.json().get('detail', 'Update failed')}")
                except: st.error("❌ Service error. Please try later.")




def show_reports_tab():
    """
    Central router for all analysis reports (Sentiment, Churn, etc.)
    Uses professional tabs for a unified analytical experience.
    """
    st.title("📊 Analytics Reports Hub")
    st.markdown("Deep-dive into your processed datasets and predictive insights.")
    
    tab_sent, tab_churn = st.tabs(["💬 Sentiment Analysis", "📉 Churn Prediction"])
    
    with tab_sent:
        from frontend.pages import feedback_page
        feedback_page.show()
        
    with tab_churn:
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

    pass

@st.fragment
def render_cases_fragment(cases_data):
    """
    Renders the cases list in a professionally styled container.
    """
    st.subheader("📋 Dataset Lifecycle Tracker")
    
    if not cases_data:
        st.info("No cases found. Navigate to `Document Ingestion` to upload your first dataset!")
        return

    # Standardized callback-based clear
    def clear_dashboard_search():
        st.session_state.dash_search_in = ""

    # Dual-column Search and Clear Interface (Pre-instantiation order)
    s_col1, s_col2 = st.columns([10, 2])
    
    with s_col2:
        st.write("<div style='height:31px'></div>", unsafe_allow_html=True)
        st.button("✖️ Clear", use_container_width=True, key="clear_search_btn", on_click=clear_dashboard_search)

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
            
        date_str = c.get("created_date", "N/A")
        try:
            import datetime
            dt = datetime.datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            dt_utc = dt.replace(tzinfo=datetime.timezone.utc)
            dt_local = dt_utc.astimezone()
            date_str = dt_local.strftime('%d %b, %I:%M %p')
        except Exception:
            pass
            
        c4.caption(date_str)
        
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
        
        col_act1, col_act2, col_act3 = st.columns([1.5, 2.5, 2.5])
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
                st.warning(f"⚠️ Delete **{selected_case['filename']}**?")
                cy, cn = st.columns(2)
                with cy:
                    if st.button("✅ Yes", key=f"btn_dy_{selected_case_id}", width='stretch'):
                        try:
                            del_res = requests.delete(f"{API_URL}/ingest/cases/{selected_case_id}", timeout=5)
                            if del_res.status_code == 200:
                                st.session_state.confirm_delete_id = None
                                st.toast(f"Dataset {selected_case_id} deleted successfully!", icon="🗑️")
                                st.rerun()
                            else:
                                st.error(f"Server error: {del_res.text}")
                        except Exception as e:
                            st.error(f"Connection error: {e}")
                with cn:
                    if st.button("❌ No", key=f"btn_dn_{selected_case_id}", width='stretch'):
                        st.session_state.confirm_delete_id = None
                        st.rerun()
            else:
                if st.button("🗑️ Delete Selected", key=f"btn_del_{selected_case_id}", width='stretch'):
                    st.session_state.confirm_delete_id = selected_case_id
                    st.rerun()

        with col_act3:
            # Delete All Confirmation Logic
            if st.session_state.get('confirm_delete_all'):
                st.error("🚨 Delete ALL datasets?")
                ay, an = st.columns(2)
                with ay:
                    if st.button("💥 YES, ALL", key="btn_del_all_confirm", width='stretch'):
                        try:
                            username = st.session_state.get("username", "")
                            del_all_res = requests.delete(f"{API_URL}/ingest/cases/all/{username}", timeout=10)
                            if del_all_res.status_code == 200:
                                st.session_state.confirm_delete_all = False
                                st.toast("All datasets deleted!", icon="🚨")
                                st.rerun()
                            else:
                                st.error(f"Server error: {del_all_res.text}")
                        except Exception as e:
                            st.error(f"Connection error: {e}")
                with an:
                    if st.button("🛑 Stop", key="btn_del_all_cancel", width='stretch'):
                        st.session_state.confirm_delete_all = False
                        st.rerun()
            else:
                if st.button("🚨 Delete All Once", key="btn_delete_all_trigger", width='stretch', type="secondary"):
                    st.session_state.confirm_delete_all = True
                    st.rerun()
