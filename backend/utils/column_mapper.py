import pandas as pd
from typing import Tuple, Dict, Any

def map_schema(df: pd.DataFrame, custom_map: Dict[str, str] = None) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Standardizes a DataFrame into the ICFA Standard Schema.
    
    Priority:
    1. Custom Admin Map (Explicit names)
    2. Exact Heuristics (Case-insensitive)
    3. Partial Heuristics (Contains keyword)
    """
    df = df.copy()
    initial_cols = list(df.columns)
    final_mapping = {}
    
    standard_cols = {
        "id": ["id", "customerid", "user_id", "uid", "index", "customer_id"],
        "feedback_text": ["feedback_text", "review", "feedback", "comment", "text", "body", "message"],
        "target": ["churn", "label", "target", "class", "churn_label"],
        "num_feature_0": ["tenure", "months", "period", "duration", "tenuremonths"],
        "num_feature_1": ["monthlycharges", "monthly_charges", "charge", "amount", "cost", "monthly_charge"],
        "cat_feature_0": ["contract", "contract_type", "type"],
        "cat_feature_1": ["internetservice", "internet_service", "service", "connection", "internet"]
    }

    # 1. Custom Mappings from Admin Settings
    if custom_map:
        for std, user in custom_map.items():
            if user in df.columns:
                df = df.rename(columns={user: std})
                final_mapping[std] = user

    # 2. Strict Match (Exact word)
    for std, candidates in standard_cols.items():
        if std not in df.columns:
            for cand in candidates:
                match = next((c for c in df.columns if c.lower().strip() == cand.lower()), None)
                if match:
                    df = df.rename(columns={match: std})
                    final_mapping[std] = match
                    break

    # 3. Fuzzy Match (Partial word)
    # Mapping in order of importance to prevent "stealing" columns
    important_order = ["feedback_text", "id", "num_feature_0", "num_feature_1", "target"]
    for std in important_order:
        if std not in df.columns:
            candidates = standard_cols[std]
            for cand in candidates:
                # Find column containing the candidate word that hasn't been mapped yet
                match = next((c for c in df.columns if cand in c.lower() and c not in final_mapping.values() and c not in standard_cols.keys()), None)
                if match:
                    df = df.rename(columns={match: std})
                    final_mapping[std] = match
                    break
                    
    # 4. Final Cleanup
    required = ["id", "feedback_text", "num_feature_0", "num_feature_1"]
    for col in required:
        if col not in df.columns:
            df[col] = None 
            
    return df, {"mapped_columns": final_mapping, "original_cols": initial_cols}
