import streamlit as st
import requests
import pandas as pd

API_URL = "http://127.0.0.1:8000"

def show():
    """Renders the User Management dashboard exclusively for admins."""
    st.title("👥 User Management")
    st.markdown("View and control system access for all users.")
    st.divider()

    # Double check role
    if st.session_state.get("role") != "admin":
        st.error("Access Denied: You do not have permission to view this page.")
        return

    admin_username = st.session_state.username

    # Fetch users
    try:
        res = requests.get(f"{API_URL}/admin/users", params={"admin_username": admin_username}, timeout=10)
        if res.status_code == 200:
            users_data = res.json().get("users", [])
        else:
            st.error(f"Failed to fetch users: {res.text}")
            return
    except Exception as e:
        st.error(f"Connection error: {e}")
        return

    if not users_data:
        st.info("No system users found.")
        return

    df_users = pd.DataFrame(users_data)
    
    # Display Global Stats quickly
    st.markdown("### System Overview")
    u_col1, u_col2, u_col3 = st.columns(3)
    with u_col1:
        st.metric("Total Users", len(df_users))
    with u_col2:
        st.metric("Admins", len(df_users[df_users['role'] == 'admin']))
    with u_col3:
        st.metric("Standard Users", len(df_users[df_users['role'] == 'user']))
        
    st.divider()

    st.markdown("### User Directory & Actions")
    st.caption("Select a user from the dropdown to perform administrative actions.")
    
    # Create a nice selectbox map
    user_options = {f"{u['username']} (ID: {u['id']}, Role: {u['role']})": u['id'] for u in users_data}
    selected_label = st.selectbox("Select User to Manage:", list(user_options.keys()))
    selected_id = user_options[selected_label]
    
    # Retrieve active user struct
    target_user = next(u for u in users_data if u['id'] == selected_id)
    
    # Render Action Cards
    st.markdown(f"#### Managing: **{target_user['username']}**")
    act_c1, act_c2, act_c3 = st.columns(3)
    
    with act_c1:
        st.info("**Role Assignment**")
        current_role = target_user['role']
        new_role = "admin" if current_role == "user" else "user"
        button_text = f"Promote to Admin" if current_role == "user" else f"Demote to User"
        if st.button(button_text, width='stretch'):
            # Self-demotion check
            if target_user['username'] == admin_username:
                st.warning("You cannot demote yourself.")
            else:
                try:
                    update_res = requests.put(
                        f"{API_URL}/admin/users/{selected_id}/role",
                        params={"admin_username": admin_username, "new_role": new_role},
                        timeout=5
                    )
                    if update_res.status_code == 200:
                        st.success(f"Role updated to {new_role}!")
                        st.rerun()
                    else:
                        st.error(f"Failed to update role: {update_res.text}")
                except Exception as e:
                    st.error(f"Connection error: {e}")

    with act_c2:
        st.warning("**Password Reset**")
        st.caption("Force reset user to default password.")
        if st.button("Reset Password", width='stretch'):
            try:
                reset_res = requests.post(
                    f"{API_URL}/admin/users/{selected_id}/reset-password",
                    params={"admin_username": admin_username},
                    timeout=5
                )
                if reset_res.status_code == 200:
                    new_password = reset_res.json().get("new_password")
                    st.success(f"Success! Temporary password: `{new_password}`")
                else:
                    st.error(f"Failed to reset: {reset_res.text}")
            except Exception as e:
                st.error(f"Connection error: {e}")

    with act_c3:
        st.error("**Account Deletion**")
        st.caption("Permanently delete user and datasets.")
        
        # Check confirmation state for this specific user
        if st.session_state.get(f"confirm_del_u_{selected_id}"):
            st.error(f"Are you absolutely sure?")
            del_c1, del_c2 = st.columns(2)
            with del_c1:
                if st.button("✅ Yes", key=f"del_yes_{selected_id}", width='stretch'):
                    if target_user['username'] == admin_username:
                        st.warning("You cannot delete yourself.")
                        st.session_state[f"confirm_del_u_{selected_id}"] = False
                        st.rerun()
                    else:
                        try:
                            del_res = requests.delete(
                                f"{API_URL}/admin/users/{selected_id}",
                                params={"admin_username": admin_username},
                                timeout=15
                            )
                            if del_res.status_code == 200:
                                st.success("Account deleted successfully.")
                                st.session_state[f"confirm_del_u_{selected_id}"] = False
                                st.rerun()
                            else:
                                st.error(f"Failed to delete: {del_res.text}")
                        except Exception as e:
                            st.error(f"Connection error: {e}")
            with del_c2:
                if st.button("❌ No", key=f"del_no_{selected_id}", width='stretch'):
                    st.session_state[f"confirm_del_u_{selected_id}"] = False
                    st.rerun()
        else:
            if st.button("Delete Account", width='stretch'):
                st.session_state[f"confirm_del_u_{selected_id}"] = True
                st.rerun()
