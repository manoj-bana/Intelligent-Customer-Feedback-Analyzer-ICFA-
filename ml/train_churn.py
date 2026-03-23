import os
import pandas as pd
import joblib

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix
)

DATA_PATH = "ml/sample_data/churn_data.csv"
MODEL_PATH = "ml/churn_model.pkl"

FEATURES = [
    "tenure",
    "MonthlyCharges",
    "TotalCharges",
    "Contract",
    "PaymentMethod",
    "InternetService",
]


def train():
    print("Loading data...")
    df = pd.read_csv(DATA_PATH)

    df = df.drop(columns=["customerID"], errors="ignore")
    df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce")
    df["Churn"] = df["Churn"].map({"Yes": 1, "No": 0})
    df = df.dropna(subset=["Churn", "TotalCharges"])

    features = [f for f in FEATURES if f in df.columns]
    print(f"Using features: {features}")

    X = df[features].copy()
    y = df["Churn"]

    X = pd.get_dummies(X, drop_first=True)

    # Handle missing numeric values
    X = X.fillna(X.median(numeric_only=True))

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    print(f"Training on {len(X_train)} rows, testing on {len(X_test)} rows")

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=12,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
    )

    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)

    print("\n" + "=" * 50)
    print("MODEL EVALUATION")
    print("=" * 50)
    print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=["Stay", "Churn"]))
    print("\nConfusion Matrix:")
    print(confusion_matrix(y_test, y_pred))

    print("\nFeature Importances:")
    for feat, imp in sorted(
        zip(X.columns, model.feature_importances_), key=lambda x: -x[1]
    ):
        print(f"  {feat}: {imp:.4f}")

    os.makedirs("ml", exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"\n✅ Model saved to {MODEL_PATH}")


# ✅ REQUIRED ENTRY POINT
if __name__ == "__main__":
    train()