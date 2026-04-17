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
    Risk scoring logic based on churn rules and admin configs.
    """
    model = load_model()
    if model is None:
        return {"error": "Model not available."}

    # 1. Config Thresholds  
    high_thresh = getattr(config, "high_risk_threshold", 0.70)
    med_thresh = getattr(config, "medium_risk_threshold", 0.40)
    churn_threshold = 0.50
    
    # 2. Preprocessing & Feature Alignment
    features = df.copy()

    # Flexible column detection: try to detect common churn dataset column names
    # Normalize column names to help matching (case-insensitive, strip spaces)
    col_map = {c.lower().replace(' ', '').replace('_',''): c for c in features.columns}

    def find_and_assign(target_keys, target_name, cast_numeric=True):
        """Find a column matching any of the target_keys and assign to target_name."""
        for k in target_keys:
            if k in col_map:
                orig = col_map[k]
                if cast_numeric:
                    features[target_name] = pd.to_numeric(features[orig], errors="coerce").fillna(0)
                else:
                    features[target_name] = features[orig]
                return True
        return False

    # Common keys for mapping
    tenure_keys = ["tenure", "months", "tenuremonths", "contractlength"]
    monthly_keys = ["monthlycharges", "monthlycharge", "monthly_charges", "monthlychargeamount", "monthly_charge"]
    total_keys = ["totalcharges", "total_charge", "total_chargeamount", "total"]

    mapped_tenure = find_and_assign(tenure_keys, "tenure", cast_numeric=True)
    mapped_monthly = find_and_assign(monthly_keys, "MonthlyCharges", cast_numeric=True)
    mapped_total = find_and_assign(total_keys, "TotalCharges", cast_numeric=True)

    # Also support the ICFA-standard num_feature_x columns
    if not mapped_tenure and "num_feature_0" in features.columns:
        features["tenure"] = pd.to_numeric(features["num_feature_0"], errors="coerce").fillna(0)
        mapped_tenure = True
    if not mapped_monthly and "num_feature_1" in features.columns:
        features["MonthlyCharges"] = pd.to_numeric(features["num_feature_1"], errors="coerce").fillna(0)
        mapped_monthly = True

    # If TotalCharges not present, try to compute from tenure*MonthlyCharges when possible
    if not mapped_total:
        if mapped_tenure and mapped_monthly:
            features["TotalCharges"] = features["tenure"] * features["MonthlyCharges"]
            mapped_total = True
        else:
            # default to zeros if not computable
            features["TotalCharges"] = 0

    # Required numeric features
    numeric_features = ["tenure", "MonthlyCharges", "TotalCharges"]
    
    # Categorical features matching training script
    categorical_features = ["Contract", "PaymentMethod", "InternetService"]
    
    # Collect all available features
    available = [f for f in numeric_features + categorical_features if f in features.columns]
    if not available:
        # No usable features found — return an informative error
        return {"error": "No usable numeric or categorical features detected for churn prediction. Please ensure your file has tenure, MonthlyCharges, TotalCharges or equivalent columns.", "hints": ["Column names detected: %s" % ", ".join(list(df.columns)[:20])]}

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
