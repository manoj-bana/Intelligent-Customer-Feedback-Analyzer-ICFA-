import pytest
import pandas as pd
from backend.utils.churn_model import validate_schema, preprocess

def test_validate_schema_success():
    df = pd.DataFrame({
        "tenure": [1, 2, 3],
        "MonthlyCharges": [10.0, 20.0, 30.0],
        "TotalCharges": [10.0, 20.0, 30.0]
    })
    result = validate_schema(df)
    assert result["valid"] is True

def test_validate_schema_missing_column():
    df = pd.DataFrame({
        "MonthlyCharges": [10.0],
        "TotalCharges": [10.0]
    })
    result = validate_schema(df)
    assert result["valid"] is False
    assert "Missing required columns: tenure" in result["error"]

def test_preprocess_basic():
    df = pd.DataFrame({
        "tenure": [1, 2],
        "MonthlyCharges": [10.0, 20.0],
        "TotalCharges": ["10.0", "20.0"],
        "Contract": ["Month-to-month", "One year"]
    })
    processed = preprocess(df)
    assert processed["tenure"].iloc[0] == 1
    assert processed["TotalCharges"].iloc[0] == 10.0
    # dummy_encoding with drop_first=True will have Contract_One year if Month-to-month is first 
    # and alphabetically comes first? No, actually Month-to-month is first.
    # In pd.get_dummies(drop_first=True), the very first category alphabetically is dropped.
    # "Month-to-month" vs "One year": M < O. So Month-to-month is dropped.
    assert "Contract_One year" in processed.columns

def test_preprocess_case_insensitive_rename():
    df = pd.DataFrame({
        "TENURE": [1],
        "Monthly_Charges": [10.0],
        "Total_Charges": ["10.0"]
    })
    # The current preprocess logic looks for 'tenure', 'MonthlyCharges', 'TotalCharges'
    # and has a case-insensitive rename mapper.
    processed = preprocess(df)
    # Total_Charges might not be exactly TotalCharges, but the mapper should handle it if it contains the substring.
    assert "tenure" in processed.columns
# Based on the code: partial = [c for c in df.columns if feat.lower() in c.lower()]
