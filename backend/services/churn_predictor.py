import pandas as pd
import joblib
import os
from typing import Dict, Any

MODEL_PATH = "ml/churn_model.pkl"
_model = None

def load_model():
    global _model
    if _model is None and os.path.exists(MODEL_PATH):
        try:
            _model = joblib.load(MODEL_PATH)
        except Exception:
            return None
    return _model

def predict_churn(df: pd.DataFrame, config: Any = None) -> Dict[str, Any]:
    """
    Member 4 Responsibility.
    Risk scoring logic based on churn rules and admin configs.
    """
    model = load_model()
    if model is None:
        return {"error": "Model not available."}

    # 1. Config Thresholds (Member 1 config)
    high_thresh = getattr(config, "high_risk_threshold", 0.70)
    med_thresh = getattr(config, "medium_risk_threshold", 0.40)
    churn_threshold = 0.50
    
    # 2. Preprocessing & Feature Alignment
    features = df.copy()
    
    # Map from ICFA Standard Schema if present
    if "num_feature_0" in features.columns:
        features["tenure"] = pd.to_numeric(features["num_feature_0"], errors="coerce").fillna(0)
    if "num_feature_1" in features.columns:
        features["MonthlyCharges"] = pd.to_numeric(features["num_feature_1"], errors="coerce").fillna(0)
    
    # TotalCharges: Use existing if present, otherwise calculate
    if "TotalCharges" not in features.columns:
        if "num_feature_0" in features.columns and "num_feature_1" in features.columns:
             features["TotalCharges"] = features["tenure"] * features["MonthlyCharges"]
        else:
             features["TotalCharges"] = 0
    else:
        features["TotalCharges"] = pd.to_numeric(features["TotalCharges"], errors="coerce").fillna(0)

    # Required numeric features
    numeric_features = ["tenure", "MonthlyCharges", "TotalCharges"]
    
    # Categorical features matching training script
    categorical_features = ["Contract", "PaymentMethod", "InternetService"]
    
    # Collect all available features
    available = [f for f in numeric_features + categorical_features if f in features.columns]
    X_input = features[available]
    
    # One-hot encode to match training process
    X_encoded = pd.get_dummies(X_input)
    
    # Align with model's expected features
    if hasattr(model, "feature_names_in_"):
        expected_cols = list(model.feature_names_in_)
        for col in expected_cols:
            if col not in X_encoded.columns:
                X_encoded[col] = 0
        X_final = X_encoded[expected_cols]
    else:
        # Fallback to numeric-only if model doesn't specify feature names
        X_final = X_encoded
        
    # 3. Predict Probabilities
    try:
        if not X_final.empty:
            probs = model.predict_proba(X_final)[:, 1]
        else:
            probs = [0.0] * len(df)
    except Exception as e:
        print(f"[CHURN SERVICE] Prediction failed: {str(e)}")
        # Provide better fallback or re-raise 
        probs = [0.0] * len(df)
        
    results = []
    churn_count = 0
    for i, p in enumerate(probs):
        prob_val = float(p)
        
        # Predicted labels based on standard 0.5 threshold
        is_churner = prob_val >= churn_threshold
        if is_churner:
            churn_count += 1
            
        # Determine risk level based on thresholds
        if prob_val > high_thresh: 
            risk = "High"
        elif prob_val > med_thresh: 
            risk = "Medium"
        else: 
            risk = "Low"
        
        results.append({
            "id": str(df.iloc[i]["id"]) if "id" in df.columns else (str(df.iloc[i]["customerid"]) if "customerid" in df.columns else str(i)),
            "risk_level": risk,
            "churn_prediction": "Yes" if is_churner else "No",
            "churn_probability": round(prob_val, 3)
        })
        
    total = len(probs)
    return {
        "predictions": results,
        "total_customers": total,
        "predicted_churn": churn_count,
        "churn_rate": round((churn_count / total * 100), 2) if total > 0 else 0
    }
