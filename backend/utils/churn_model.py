import pandas as pd
import joblib
import os
from sklearn.preprocessing import LabelEncoder

MODEL_PATH = "ml/churn_model.pkl"

FEATURES = [
    "tenure", "MonthlyCharges", "TotalCharges",
    "Contract", "PaymentMethod", "InternetService"
]


def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    available = [col for col in FEATURES if col in df.columns]
    if not available:
        return pd.DataFrame()
    df = df[available]
    if "TotalCharges" in df.columns:
        df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce")
    
    # FIXED: Use pd.get_dummies to match training exactly
    df = pd.get_dummies(df, columns=['Contract', 'PaymentMethod', 'InternetService'], drop_first=True)
    df = df.fillna(df.median(numeric_only=True))
    return df


def predict_churn(df: pd.DataFrame) -> dict:
    if not os.path.exists(MODEL_PATH):
        return {"error": "Model not found. Run ml/train_churn.py first."}

    model = joblib.load(MODEL_PATH)
    processed = preprocess(df)

    if processed.empty:
        return {
            "error": (
                "No matching feature columns found in uploaded CSV. "
                "Need: tenure, MonthlyCharges, TotalCharges, "
                "Contract, PaymentMethod, InternetService"
            )
        }

    # FIX: Ensure all features expected by the model are present and in the correct order
    if hasattr(model, "feature_names_in_"):
        for col in model.feature_names_in_:
            if col not in processed.columns:
                processed[col] = 0
        processed = processed[list(model.feature_names_in_)]

    probs = model.predict_proba(processed)[:, 1]
    predictions = (probs >= 0.5).astype(int)

    results = [
        {
            "customer_index": i + 1,
            "churn_prediction": "Yes" if p == 1 else "No",
            "churn_probability": round(float(prob), 3),
            "risk_level": "High" if prob > 0.7 else "Medium" if prob > 0.4 else "Low"
        }
        for i, (p, prob) in enumerate(zip(predictions, probs))
    ]

    churn_count = int(sum(predictions))
    return {
        "total_customers": len(results),
        "predicted_churn": churn_count,
        "churn_rate": round(churn_count / len(results) * 100, 2),
        "predictions": results[:100]
    }
