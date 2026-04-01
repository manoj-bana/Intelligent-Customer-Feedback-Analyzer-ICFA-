import streamlit as st
import pandas as pd
import requests

API_URL = "http://127.0.0.1:8000"

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

        uploaded_file = st.file_uploader(
            "Select File (CSV, XLSX)",
            type=["csv", "xlsx", "xls"]
        )

        if uploaded_file is not None:
            if st.button("🚀 Upload & Process", use_container_width=True, type="primary"):
                _handle_csv_upload(uploaded_file, task_type)
        else:
            st.button("🚀 Upload & Process", use_container_width=True, type="primary", disabled=True)


def _handle_csv_upload(uploaded_file, task_type: str):
    """
    Handles direct CSV/XLSX upload via the existing /upload endpoint.
    """
    with st.spinner("Uploading dataset for background processing…"):
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
