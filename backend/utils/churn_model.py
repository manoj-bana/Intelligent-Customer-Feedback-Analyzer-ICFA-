import pandas as pd
import os
import joblib

# Global cache for lazy loading heavy ML resources
_model = None
MODEL_PATH = "ml/churn_model.pkl"
REQUIRED_FEATURES = ["tenure", "MonthlyCharges", "TotalCharges"]
OPTIONAL_FEATURES = ["Contract", "PaymentMethod", "InternetService"]
ALL_FEATURES = REQUIRED_FEATURES + OPTIONAL_FEATURES

def load_churn_model():
    """
    Lazy loader for the pre-trained churn prediction model.
    """
    global _model
    if _model is None:
        if os.path.exists(MODEL_PATH):
            try:
                _model = joblib.load(MODEL_PATH)
            except Exception:
                return None
    return _model

def validate_schema(df: pd.DataFrame) -> dict:
    """
    Validates that the input DataFrame contains required feature columns.
    """
    uploaded_cols_lower = {c.lower(): c for c in df.columns}
    missing_required = []
    hints = []
    
    for feat in REQUIRED_FEATURES:
        if feat not in df.columns:
            if feat.lower() in uploaded_cols_lower:
                hints.append(f"Rename '{uploaded_cols_lower[feat.lower()]}' → '{feat}'")
            else:
                partial = [c for c in df.columns if feat.lower() in c.lower()]
                if partial:
                    hints.append(f"Rename '{partial[0]}' → '{feat}'")
                else:
                    missing_required.append(feat)
                    
    if missing_required:
        error_msg = (
            f"Missing required columns: {', '.join(missing_required)}. "
            f"Your file has: [{', '.join(list(df.columns[:8]))}...]. "
            "Expected: tenure, MonthlyCharges, TotalCharges, etc."
        )
        return {"valid": False, "error": error_msg, "hints": hints}
        
    return {"valid": True, "hints": hints}

def preprocess(df: pd.DataFrame, model=None) -> pd.DataFrame:
    """
    Preprocess raw input data for the churn model, including encoding and feature alignment.
    """
    df = df.copy()
    col_map = {c.lower(): c_orig for c_orig, c in [(c, c.lower()) for c in df.columns]}
    
    rename_dict = {
        col_map[feat.lower()]: feat 
        for feat in ALL_FEATURES 
        if feat not in df.columns and feat.lower() in col_map
    }
    
    if rename_dict:
        df = df.rename(columns=rename_dict)
        
    available = [col for col in ALL_FEATURES if col in df.columns]
    if not available:
        return pd.DataFrame()
        
    df = df[available]
    
    if "TotalCharges" in df.columns:
        df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce")
        
    cat_cols = [c for c in df.select_dtypes(include=['object', 'string']).columns if c in df.columns]
    if cat_cols:
        df = pd.get_dummies(df, columns=cat_cols, drop_first=True)
        
    df = df.fillna(df.median(numeric_only=True))
    
    if model is not None and hasattr(model, "feature_names_in_"):
        expected_cols = list(model.feature_names_in_)
        for col in expected_cols:
            if col not in df.columns:
                df[col] = 0
        df = df[expected_cols]
        
    return df

def predict_churn(df: pd.DataFrame, config=None) -> dict:
    """
    Predicts customer churn probability for a given DataFrame.
    Supports organization-specific risk thresholds.
    """
    # 1. Load config values
    high_thresh = config.high_risk_threshold if config and hasattr(config, "high_risk_threshold") else 0.70
    med_thresh = config.medium_risk_threshold if config and hasattr(config, "medium_risk_threshold") else 0.40
    low_thresh = config.low_risk_threshold if config and hasattr(config, "low_risk_threshold") else 0.10

    model = load_churn_model()
    if model is None:
        return {"error": "Model file not found or could not be loaded."}
    
    validation = validate_schema(df)
    if not validation["valid"]:
        return {
            "error": validation["error"], 
            "hints": validation.get("hints", [])
        }
    
    processed = preprocess(df, model=model)
    if processed.empty:
        return {"error": "No matching feature columns found."}
    
    # Calculate probabilities and binary predictions
    probs = model.predict_proba(processed)[:, 1]
    predictions = (probs >= 0.5).astype(int)
    
    # Try to find a customer ID column to preserve
    id_col = next((c for c in df.columns if any(k in c.lower() for k in ["customerid", "customer_id", "userid", "user_id", "id"])), None)
    
    results = []
    for i, (p, prob) in enumerate(zip(predictions, probs)):
        prob_val = float(prob)
        # Determine risk level based on thresholds
        if prob_val > high_thresh: risk = "High"
        elif prob_val > med_thresh: risk = "Medium"
        elif prob_val > low_thresh: risk = "Low"
        else: risk = "Safe"

        results.append({
            "customer_id": str(df.iloc[i][id_col]) if id_col else str(i + 1),
            "customer_index": i + 1,
            "churn_prediction": "Yes" if p == 1 else "No",
            "churn_probability": round(prob_val, 3),
            "risk_level": risk
        })
        
    churn_count = int(sum(predictions))
    total_count = len(results)
    
    return {
        "total_customers": total_count,
        "predicted_churn": churn_count,
        "churn_rate": round(churn_count / total_count * 100, 2) if total_count > 0 else 0,
        "predictions": results,
        "warnings": validation.get("hints", [])
    }
