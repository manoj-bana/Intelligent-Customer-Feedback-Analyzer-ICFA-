import streamlit as st
import pandas as pd
import requests

import os
from dotenv import load_dotenv

load_dotenv()
API_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

def get_headers():
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}

def inject_ingestion_styles():
    st.markdown("""
        <style>
        .task-card {
            background: #1f2937;
            border: 1px solid #374151;
            border-radius: 12px;
            padding: 1.5rem;
            cursor: pointer;
            transition: all 0.3s ease;
            margin-bottom: 1rem;
            position: relative;
        }
        .task-card:hover {
            border-color: #0d9488;
            background: #111827;
        }
        .task-card.active {
            border-color: #0d9488;
            background: rgba(13, 148, 136, 0.1);
        }
        .task-card.active::after {
            content: '●';
            color: #0d9488;
            position: absolute;
            top: 1rem;
            right: 1rem;
            font-size: 0.8rem;
        }
        .task-icon {
            font-size: 1.5rem;
            margin-bottom: 0.5rem;
            color: #2dd4bf;
        }
        .task-title {
            font-weight: 700;
            font-size: 1.1rem;
            color: #f3f4f6;
            margin-bottom: 0.2rem;
        }
        .task-desc {
            font-size: 0.85rem;
            color: #9ca3af;
            line-height: 1.4;
        }
        .upload-zone {
            background: rgba(31, 41, 55, 0.5);
            border: 2px dashed #374151;
            border-radius: 16px;
            padding: 4rem 2rem;
            text-align: center;
            transition: border-color 0.3s ease;
        }
        .upload-zone:hover {
            border-color: #0d9488;
        }
        </style>
    """, unsafe_allow_html=True)

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
    Renders the modern ICFA Pro Document Ingestion page.
    """
    inject_ingestion_styles()
    
    # Header Section
    st.title("Document Ingestion")
    st.markdown("Upload your customer feedback datasets for AI-powered analysis.")
    st.write("")

    # Initialize task state from query params or session
    if "ingest_task" not in st.session_state:
        q_task = st.query_params.get("task", "Sentiment Analysis")
        st.session_state.ingest_task = q_task

    # Main Layout: Selection on Left, Uploader on Right
    col_nav, col_main = st.columns([1, 1.8], gap="large")

    with col_nav:
        st.markdown("<p style='font-size:0.8rem; font-weight:700; color:#9ca3af; letter-spacing:1px;'>1. SELECT TASK TYPE</p>", unsafe_allow_html=True)
        
        # Sentiment Analysis Card
        is_sent = (st.session_state.ingest_task == "Sentiment Analysis")
        if st.button("📊 Sentiment Analysis\nAnalyze emotional tone and keywords.", key="btn_task_sent", use_container_width=True, type="primary" if is_sent else "secondary"):
            st.session_state.ingest_task = "Sentiment Analysis"
            st.query_params["task"] = "Sentiment Analysis"
            st.rerun()

        # Churn Prediction Card
        is_churn = (st.session_state.ingest_task == "Churn Prediction")
        if st.button("🎯 Churn Prediction\nPredict customer churn probability.", key="btn_task_churn", use_container_width=True, type="primary" if is_churn else "secondary"):
            st.session_state.ingest_task = "Churn Prediction"
            st.query_params["task"] = "Churn Prediction"
            st.rerun()

        st.divider()
        with st.container(border=True):
            st.markdown("<p style='font-size:0.8rem; font-weight:700; color:#9ca3af;'>REQUIREMENTS</p>", unsafe_allow_html=True)
            if st.session_state.ingest_task == "Sentiment Analysis":
                st.markdown("""
                - CSV/Excel format
                - Max file size: 50MB
                - Must contain sentiment text
                """)
            else:
                st.markdown("""
                - CSV/Excel format
                - Max file size: 50MB
                - tenure, MonthlyCharges required
                """)

    with col_main:
        st.markdown(f"<p style='font-size:0.8rem; font-weight:700; color:#9ca3af; letter-spacing:1px;'>2. SELECT FILE ({st.session_state.ingest_task})</p>", unsafe_allow_html=True)
        
        uploaded_file = st.file_uploader(
            "Drag and drop file here",
            type=["csv", "xlsx", "xls"],
            label_visibility="collapsed"
        )

        if uploaded_file is not None:
            # Quick preview / validation summary
            st.info(f"Selected: **{uploaded_file.name}**")

            # Build a unique key for the current user + file + task combination
            username = st.session_state.get("username", "guest")
            current_upload_key = f"{username}::{uploaded_file.name}::{st.session_state.ingest_task}"
            last_upload_key = st.session_state.get("last_upload_key", "")

            if st.button("📦 Process Dataset", use_container_width=True, type="primary"):
                if current_upload_key == last_upload_key:
                    st.warning(
                        f"⚠️ **Duplicate Upload Detected:** `{uploaded_file.name}` has already been "
                        f"submitted for **{st.session_state.ingest_task}**. "
                        "Please select a different file or switch the task type."
                    )
                else:
                    is_valid, error_msg = validate_dataset(uploaded_file, st.session_state.ingest_task)
                    if not is_valid:
                        st.error(error_msg)
                    else:
                        _handle_csv_upload(uploaded_file, st.session_state.ingest_task)
        else:
            # Placeholder/Empty State
            st.markdown("""
                <div style='border: 2px dashed #374151; border-radius: 16px; padding: 5rem 2rem; text-align: center; opacity: 0.6;'>
                    <div style='font-size: 3rem; margin-bottom: 1rem;'>📤</div>
                    <p style='color: #9ca3af;'>Browse your computer to upload a dataset<br/><small>or drag and drop here</small></p>
                </div>
            """, unsafe_allow_html=True)
            st.button("📦 Process Dataset", use_container_width=True, type="primary", disabled=True)

    # Optional: Data Preparation Guide at bottom
    with st.expander("📖 Need Help with Data Formatting?", expanded=False):
        st.markdown("Ensure your datasets are formatted correctly for the chosen analysis pipeline.")
        tab1, tab2 = st.tabs(["💬 Sentiment Analysis", "📉 Churn Prediction"])
        # (Template logic remains similar, suppressed for brevity)
        with tab1:
            st.markdown("**Requirements:** Feedback text column (e.g., 'review', 'comment').")
        with tab2:
            st.markdown("**Required Columns:** `tenure`, `MonthlyCharges`, `TotalCharges`.")

    # Image extraction moved to bottom as a subtler option
    st.divider()
    with st.expander("📸 Beta: Extract Table from Image (OCR)", expanded=False):
        st.write("Upload a screenshot or photo of a data table.")
        uploaded_image = st.file_uploader("Select Image", type=["jpg", "jpeg", "png"], key="img_uploader")
        if uploaded_image and st.button("📸 Extract & Process", use_container_width=True):
            _handle_image_upload(uploaded_image, st.session_state.ingest_task)


def _handle_csv_upload(uploaded_file, task_type: str):
    """
    Handles direct CSV/XLSX upload via the existing /upload endpoint.
    """
    # Ensure the file pointer is at the beginning (prevents empty uploads)
    uploaded_file.seek(0)
    
    with st.spinner("Uploading dataset for background processing..."):
        try:
            username = st.session_state.get("username", "")
            if not username:
                st.error("Authentication Error: Missing active session.")
                return

            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "text/csv")}
            data = {"username": str(username), "task_type": task_type}

            response = requests.post(
                f"{API_URL}/ingest/upload",
                files=files,
                data=data,
                headers=get_headers(),
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
                
                # Mark this user + file + task combo as processed
                st.session_state["last_upload_key"] = f"{username}::{uploaded_file.name}::{task_type}"
                st.session_state["file_processed"] = True
            elif response.status_code == 409:
                st.warning(
                    f"⚠️ **Already In Queue:** `{uploaded_file.name}` is already being processed "
                    "for this task type. Check your Home dashboard for its status."
                )
            else:
                st.error(f"Ingestion failed: {response.text}")

        except requests.exceptions.ConnectionError:
            st.error("⚠️ Connection Error: Unable to reach the backend server.")
        except Exception as e:
            st.error(f"Unexpected error: {str(e)}")


def _handle_image_upload(uploaded_file, task_type: str):
    """
    Handles image upload via the existing /upload-image endpoint.
    """
    with st.spinner("Extracting table from image… this may take a moment."):
        try:
            username = st.session_state.get("username", "")
            if not username:
                st.error("Authentication Error: Missing active session.")
                return

            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
            data = {"username": str(username), "task_type": task_type}

            response = requests.post(
                f"{API_URL}/ingest/upload-image",
                files=files,
                data=data,
                headers=get_headers(),
                timeout=60
            )

            if response.status_code == 200:
                case_id = response.json().get("case_id")
                
                # Clear our data cache instantly so the dashboard updates without delay
                try:
                    from frontend.pages.dashboard import get_cases
                    get_cases.clear()
                except Exception:
                    # Fallback to clearing all cache if local clear fails
                    st.cache_data.clear()
                
                st.success(f"✅ Extraction and Upload successful! Tracking ID: **{case_id}**")
                st.info(
                    "The extracted data is now in the **Pending Review** queue and will be "
                    "analyzed in the background. Check your Home dashboard for status updates."
                )
            elif response.status_code == 422:
                st.error(f"Extraction failed: {response.json().get('detail', 'Could not extract a valid table from the image.')}")
            else:
                st.error(f"Upload failed: {response.text}")

        except requests.exceptions.ConnectionError:
            st.error("⚠️ Connection Error: Unable to reach the backend server.")
        except Exception as e:
            st.error(f"Unexpected error: {str(e)}")
