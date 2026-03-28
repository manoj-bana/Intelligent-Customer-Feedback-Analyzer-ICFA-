"""
Tests for churn prediction model: schema validation, preprocessing, predictions.
"""
import pandas as pd
from backend.utils.churn_model import validate_schema, preprocess


# ─── SCHEMA VALIDATION ───

def test_valid_schema():
    df = pd.DataFrame({
        "tenure": [12], "MonthlyCharges": [50.0], "TotalCharges": [600.0],
        "Contract": ["Month-to-month"], "PaymentMethod": ["Credit card"],
        "InternetService": ["Fiber optic"]
    })
    result = validate_schema(df)
    assert result["valid"] is True
    assert result["hints"] == []


def test_missing_required_columns():
    df = pd.DataFrame({"Name": ["John"], "Age": [25], "Salary": [50000]})
    result = validate_schema(df)
    assert result["valid"] is False
    assert "Missing required columns" in result["error"]


def test_case_insensitive_hint():
    df = pd.DataFrame({
        "TENURE": [12], "monthlycharges": [50.0], "totalcharges": [600.0]
    })
    result = validate_schema(df)
    assert result["valid"] is True
    assert len(result["hints"]) > 0


def test_partial_match_hint():
    df = pd.DataFrame({
        "customer_tenure": [12], "MonthlyCharges": [50.0], "TotalCharges": [600.0]
    })
    result = validate_schema(df)
    # 'tenure' is found partially in 'customer_tenure'
    assert result["valid"] is True or len(result.get("hints", [])) > 0


# ─── PREPROCESSING ───

def test_preprocess_returns_dataframe():
    df = pd.DataFrame({
        "tenure": [12, 24], "MonthlyCharges": [50.0, 70.0], "TotalCharges": [600, 1680],
        "Contract": ["Month-to-month", "One year"],
        "PaymentMethod": ["Credit card", "Bank transfer"],
        "InternetService": ["DSL", "Fiber optic"]
    })
    result = preprocess(df)
    assert not result.empty
    assert "tenure" in result.columns


def test_preprocess_empty_when_no_features():
    df = pd.DataFrame({"Name": ["John"], "City": ["NYC"]})
    result = preprocess(df)
    assert result.empty


def test_preprocess_handles_case_insensitive_columns():
    df = pd.DataFrame({
        "TENURE": [12], "monthlycharges": [50.0], "TOTALCHARGES": ["600"]
    })
    result = preprocess(df)
    assert not result.empty


def test_preprocess_converts_totalcharges_to_numeric():
    df = pd.DataFrame({
        "tenure": [12], "MonthlyCharges": [50.0], "TotalCharges": ["600.50"]
    })
    result = preprocess(df)
    assert result["TotalCharges"].dtype in ["float64", "int64"]