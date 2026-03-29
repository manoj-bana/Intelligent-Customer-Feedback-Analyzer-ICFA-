import requests
import streamlit as st
import pandas as pd

API_URL = "http://127.0.0.1:8000"

def show():
    """
    Main entry point for the Churn Prediction report page. 
    Handles dataset selection and prediction results visualization.
    """
    username = st.session_state.get("username", "")
    if not username:
        st.error("Authentication Error: Please login to access reports.")
>>>>>>> bd5c89ca96a5b8bb623b80c2b284d392f6a492ae
        return
=======
    username = st.session_state.get("username", "")
    if not username:
        st.error("Authentication Error: Please login to access reports.")
        return
=======
    st.title("📉 Churn Prediction")
    st.markdown("Select an ingested dataset to view the churn prediction report.")
    st.divider()

    username = st.session_state.get("username", "")
    if not username:
        st.error("Authentication Error: Please login to access reports.")
        return
=======
    username = st.session_state.get("username", "")
    if not username:
        st.error("Authentication Error: Please login to access reports.")
>>>>>>> bd5c89ca96a5b8bb623b80c2b284d392f6a492ae
        return

    # Fetch user's cases safely
    try:
        res = requests.get(f"{API_URL}/ingest/cases/{username}", timeout=10)
        cases_data = res.json().get("cases", []) if res.status_code == 200 else []
    except Exception:
        cases_data = []

    # Get completed churn datasets
    churn_cases = [
        c for c in cases_data 
        if c.get("task_type") == "Churn Prediction" and c.get("review_status") == "Completed"
    ]

    if not churn_cases:
        st.info(
            "No completed Churn Prediction datasets found. "
            "Go to 'Document Ingestion' to upload one."
        )
        return

    # Map labels to case IDs
    case_mapping = {
        f"{c['filename']} (ID: {c['case_id']})": c['case_id'] for c in churn_cases
    }
    
    selected_case_label = st.selectbox(
        "Select Dataset", 
        list(case_mapping.keys()), 
        key="select_churn_dataset"
    )
    
    if st.button("📊 View Report", use_container_width=True, key="btn_view_churn"):
        case_id = case_mapping[selected_case_label]
        with st.spinner("Fetching predictive results..."):
            try:
                res = requests.get(f"{API_URL}/ingest/results/{case_id}", timeout=30)
                if res.status_code == 200:
                    st.session_state.churn_results = res.json()
                else:
                    st.error(f"Error fetching results: {res.text}")
            except Exception as e:
                st.error(f"Connection error: {e}")

    if "churn_results" in st.session_state:
        show_churn_results(st.session_state.churn_results)

def show_churn_results(data):
    """
    Renders metrics and a detailed prediction table for the selected churn dataset.
    """
    if "error" in data:
        st.error(f"Processing Error: {data['error']}")
        return

    st.success("✅ Prediction Analysis Complete!")
    
    # --- Overall Metrics ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Customers", data["total_customers"])
    c2.metric("Predicted Churn", data["predicted_churn"], delta_color="inverse")
    c3.metric("Projected Churn Rate", f"{data['churn_rate']}%", delta_color="inverse")
    st.divider()

    # --- Detailed Data Grid ---
    st.subheader("Individual Customer Risk Profile")
    df = pd.DataFrame(data["predictions"])

    def style_churn_risk(row):
        """
        Styles table rows based on churn prediction for high-visibility risk flagging.
        """
        if row["churn_prediction"] == "Yes":
            # Soft red for risk
            return ["background-color: rgba(255, 44, 0, 0.15)"] * len(row)
        # Soft green for retention
        return ["background-color: rgba(0, 222, 3, 0.10)"] * len(row)

    st.dataframe(
        df.style.apply(style_churn_risk, axis=1), 
        use_container_width=True,
        hide_index=True
    )
