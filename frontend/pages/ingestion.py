import streamlit as st
import requests

API_URL = "http://127.0.0.1:8000"

def show():
    """
    Renders the Document Ingestion page, allowing users to upload and 
    start background processing for new datasets.
    """
    st.title("☁️ Document Ingestion")
    st.markdown("Upload new customer datasets to be automatically processed in the background.")
    st.divider()
    
    with st.container(border=True):
        st.subheader("New Dataset Upload")
        uploaded_file = st.file_uploader(
            "Select File (CSV, XLSX)", 
            type=["csv", "xlsx", "xls"]
        )
        
        task_type = st.selectbox(
            "Select Processing Pipeline",
            ["Sentiment Analysis", "Churn Prediction"]
        )
        
        if st.button("🚀 Upload & Process", width='stretch', type="primary"):
            if not uploaded_file:
                st.error("Please upload a file first.")
            else:
                handle_upload(uploaded_file, task_type)

def handle_upload(uploaded_file, task_type):
    """
    Internal helper to handle the file upload request to the backend.
    """
    with st.spinner("Uploading dataset for background processing..."):
        try:
            username = st.session_state.get("username", "")
            if not username:
                st.error("Authentication Error: Missing active session.")
                return
                
            files = {
                "file": (uploaded_file.name, uploaded_file.getvalue(), "text/csv")
            }
            data = {
                "username": str(username),
                "task_type": task_type
            }
            
            response = requests.post(
                f"{API_URL}/ingest/upload", 
                files=files, 
                data=data, 
                timeout=30
            )
            
            if response.status_code == 200:
                case_id = response.json().get("case_id")
                
                # Clear our data cache instantly so the dashboard updates without delay
                try:
                    from frontend.pages.dashboard import get_cases
                    # Cache clear removed for 0-cache performance sync
                    pass
                except Exception:
                    # Fallback to clearing all cache if local clear fails
                    st.cache_data.clear()
                
                st.success(f"✅ Upload successful! Tracking ID: **{case_id}**")
                st.info(
                    "The dataset is now in the **Pending Review** queue and will be "
                    "analyzed in the background. Check your Home dashboard for status updates."
                )
            else:
                st.error(f"Ingestion failed: {response.text}")
                
        except requests.exceptions.ConnectionError:
            st.error("⚠️ Connection Error: Unable to reach the backend server.")
        except Exception as e:
            st.error(f"Unexpected error: {str(e)}")
