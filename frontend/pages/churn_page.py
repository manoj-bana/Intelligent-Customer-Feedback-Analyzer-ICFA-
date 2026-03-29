import streamlit as st
import requests
import pandas as pd

API_URL = "http://127.0.0.1:8000"


def show():
    st.title("📉 Churn Prediction")
    st.markdown(
        "Upload a CSV with columns: "
        "`tenure`, `MonthlyCharges`, `TotalCharges`, "
        "`Contract`, `PaymentMethod`, `InternetService`"
    )
    st.info("💡 Use the Telco Customer Churn dataset from Kaggle to test this")
    st.divider()

    uploaded_file = st.file_uploader("📂 Upload CSV file", type=["csv"])

    if uploaded_file:
        df_preview = pd.read_csv(uploaded_file)
        uploaded_file.seek(0)
        st.markdown("**Preview:**")
        st.dataframe(df_preview.head(), use_container_width=True)
        st.divider()

        if st.button("📉 Predict Churn", use_container_width=True):
            try:
                with st.spinner("Uploading and starting job..."):
                    import time
                    response = requests.post(
                        f"{API_URL}/churn/predict",
                        files={"file": (uploaded_file.name, uploaded_file.getvalue(), "text/csv")},
                        timeout=120
                    )
                if response.status_code == 200:
                    resp_json = response.json()
                    job_id = resp_json.get("job_id")
                    if job_id:
                        progress_container = st.empty()
                        with st.spinner("Job started..."):
                            while True:
                                res_status = requests.get(f"{API_URL}/churn/result/{job_id}", timeout=60).json()
                                if res_status.get("status") == "completed":
                                    progress_container.empty()
                                    show_churn_results(res_status.get("data"))
                                    break
                                elif res_status.get("status") == "failed":
                                    progress_container.empty()
                                    st.error(f"Processing failed: {res_status.get('error')}")
                                    break
                                else:
                                    msg = res_status.get("message", "Processing in background...")
                                    progress_container.info(f"⏳ {msg}")
                                time.sleep(0.3)
                    else:
                        show_churn_results(resp_json)
                else:
                    st.error(f"API Error: {response.text}")
            except requests.exceptions.ConnectionError:
                st.warning("⚠️ Backend not running. Showing mock results for UI demo.")
                show_churn_results(mock_churn())


def show_churn_results(data):
    if "error" in data:
        st.error(data["error"])
        return

    st.success("✅ Prediction complete!")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Customers", data["total_customers"])
    col2.metric("Will Churn",      data["predicted_churn"])
    col3.metric("Churn Rate",      f"{data['churn_rate']}%")
    st.divider()

    st.subheader("Customer-wise Predictions")
    df = pd.DataFrame(data["predictions"])

    def color_churn(row):
        if row["churn_prediction"] == "Yes":
            return ["background-color: #ff2c00"] * len(row)
        return ["background-color: #00de03"] * len(row)

    st.dataframe(df.style.apply(color_churn, axis=1), use_container_width=True)


def mock_churn():
    return {
        "total_customers": 5,
        "predicted_churn": 2,
        "churn_rate": 40.0,
        "predictions": [
            {"customer_index": 1, "churn_prediction": "Yes", "churn_probability": 0.82, "risk_level": "High"},
            {"customer_index": 2, "churn_prediction": "No",  "churn_probability": 0.12, "risk_level": "Low"},
            {"customer_index": 3, "churn_prediction": "Yes", "churn_probability": 0.76, "risk_level": "High"},
            {"customer_index": 4, "churn_prediction": "No",  "churn_probability": 0.09, "risk_level": "Low"},
            {"customer_index": 5, "churn_prediction": "No",  "churn_probability": 0.33, "risk_level": "Medium"},
        ]
    }

