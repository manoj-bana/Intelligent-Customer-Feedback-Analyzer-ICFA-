import streamlit as st
import pandas as pd
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
    Renders the Document Ingestion page.
    """
    st.title("☁️ Document Ingestion")
    st.markdown("Upload new customer datasets to be automatically processed in the background.")
    st.divider()

    # Data Preparation Guide
    with st.expander("📖 Data Preparation Guide & Templates", expanded=False):
        st.write("Ensure your datasets are formatted correctly for the chosen analysis pipeline.")
        tab1, tab2 = st.tabs(["💬 Sentiment Analysis", "📉 Churn Prediction"])

        with tab1:
            st.markdown("""
            **Requirements:**
            - At least one column containing feedback text.
            - *Recommended names:* `review`, `feedback`, `comment`, or `text`.
            - *Optional:* `user_id` for per-user analysis, `date` for trend charts.
            """)
            sample_sent = pd.DataFrame({
                "Feedback": [
                    "Excellent product, very happy!",
                    "Support was a bit slow today.",
                    "I've used this for 2 years and it's great."
                ],
                "User": ["ID_101", "ID_102", "ID_103"],
                "Date": ["2024-03-25", "2024-03-26", "2024-03-27"]
            })
            st.dataframe(sample_sent, hide_index=True, use_container_width=True)
            st.download_button(
                label="📥 Download Sentiment Template (CSV)",
                data=sample_sent.to_csv(index=False).encode("utf-8"),
                file_name="icfa_sentiment_template.csv",
                mime="text/csv",
                use_container_width=True
            )

        with tab2:
            st.markdown("""
            **Required Columns:** `tenure`, `MonthlyCharges`, `TotalCharges`.
            - *Optional:* `Contract`, `PaymentMethod`, `InternetService`.
            - *Note:* Header names are case-sensitive for CSV.
            """)
            sample_churn = pd.DataFrame({
                "tenure": [12, 1, 48],
                "MonthlyCharges": [29.85, 56.95, 103.20],
                "TotalCharges": [358.2, 56.95, 4953.6],
                "Contract": ["Month-to-month", "One year", "Two year"]
            })
            st.dataframe(sample_churn, hide_index=True, use_container_width=True)
            st.download_button(
                label="📥 Download Churn Template (CSV)",
                data=sample_churn.to_csv(index=False).encode("utf-8"),
                file_name="icfa_churn_template.csv",
                mime="text/csv",
                use_container_width=True
            )

    st.write("")

    with st.container(border=True):
        st.subheader("New Dataset Upload")

        task_type = st.selectbox(
            "Select Processing Pipeline",
            ["Sentiment Analysis", "Churn Prediction"],
            key="csv_task_type"
        )
        # Simplified upload button logic

        uploaded_file = st.file_uploader(
            "Select File (CSV, XLSX)",
            type=["csv", "xlsx", "xls"]
        )

        if uploaded_file is not None:
            if st.button("🚀 Upload & Process", use_container_width=True, type="primary"):
                # Integrate validation for better safety
                is_valid, error_msg = validate_dataset(uploaded_file, task_type)
                if not is_valid:
                    st.error(error_msg)
                else:
                    _handle_csv_upload(uploaded_file, task_type)
        else:
            st.button("🚀 Upload & Process", use_container_width=True, type="primary", disabled=True)


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
                
                # Reset file uploader by clearing its state if possible
                # Or simply inform the user to select another file
                st.session_state["file_processed"] = True
            else:
                st.error(f"Ingestion failed: {response.text}")

        except requests.exceptions.ConnectionError:
            st.error("⚠️ Connection Error: Unable to reach the backend server.")
        except Exception as e:
            st.error(f"Unexpected error: {str(e)}")
