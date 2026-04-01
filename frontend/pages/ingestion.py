import streamlit as st
import requests
import pandas as pd

API_URL = "http://127.0.0.1:8000"

def validate_dataset(uploaded_file, task_type):
    """
    Validates that the uploaded file matches the expected schema for the selected task.
    Returns (is_valid, error_message).
    """
    try:
        # Read a small chunk of the file to get column names
        if uploaded_file.name.lower().endswith(('.xls', '.xlsx')):
            df = pd.read_excel(uploaded_file, nrows=5)
        else:
            df = pd.read_csv(uploaded_file, nrows=5)
    except Exception as e:
        return False, "Invalid file format. Please upload a file with the required structure and columns."
    finally:
        # Reset file pointer for the actual upload
        uploaded_file.seek(0)

    columns = [str(c).lower().strip() for c in df.columns]

    # Heuristics for dataset types
    sentiment_keywords = ["review", "feedback", "comment", "text"]
    has_sentiment_col = any(any(k in col for k in sentiment_keywords) for col in columns)

    churn_keywords = ["tenure", "monthly", "totalcharges", "contract", "churn", "internet", "billing"]
    churn_score = sum(any(k in col for k in churn_keywords) for col in columns)
    has_churn_col = churn_score >= 2

    if task_type == "Sentiment Analysis":
        if has_churn_col and not has_sentiment_col:
            return False, "Invalid file: This appears to be a Churn Prediction dataset. Please upload a valid Sentiment Analysis file."
        elif not has_sentiment_col:
            return False, "Invalid file format. Please upload a file with the required structure and columns. (Missing text/review column)"
            
    elif task_type == "Churn Prediction":
        if has_sentiment_col and not has_churn_col:
            return False, "Invalid file: This appears to be a Sentiment Analysis dataset. Please upload a valid Churn Prediction file."
        elif not has_churn_col:
            return False, "Invalid file format. Please upload a file with the required structure and columns. (Missing required features like tenure, MonthlyCharges, etc.)"

    return True, ""

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
        
        if st.button("🚀 Upload & Process", use_container_width=True, type="primary"):
            if not uploaded_file:
                st.error("Please upload a file first.")
            else:
                is_valid, error_msg = validate_dataset(uploaded_file, task_type)
                if not is_valid:
                    st.error(error_msg)
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
