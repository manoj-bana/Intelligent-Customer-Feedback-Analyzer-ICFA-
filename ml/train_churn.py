"""
Churn Prediction Model Training Script.
Handles data preprocessing, feature engineering, and training of a 
RandomForest model for customer retention analysis.
"""
import os
import joblib
import pandas as pd
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
    """
    Main training pipeline: Load data, preprocess, train, evaluate, and save model.
    """
    print("Loading churn dataset...")
    if not os.path.exists(DATA_PATH):
        print(f"Error: {DATA_PATH} not found.")
        return
        
    df = pd.read_csv(DATA_PATH)

    df = df.drop(columns=["customerID"], errors="ignore")
    df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce")
    df["Churn"] = df["Churn"].map({"Yes": 1, "No": 0})
    df = df.dropna(subset=["Churn", "TotalCharges"])

    available_features = [f for f in FEATURES if f in df.columns]
    print(f"Features selected for training: {available_features}")

    X = df[available_features].copy()
    y = df["Churn"]

    # One-hot encode categorical variables
    X = pd.get_dummies(X, drop_first=True)

    # Impute missing numeric values using median
    X = X.fillna(X.median(numeric_only=True))

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    print(f"Training set size: {len(X_train)} | Test set size: {len(X_test)}")

    # Initialize professional Random Forest with balanced hyperparameters
    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=12,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
    )

    model.fit(X_train, y_train)

    # Performance Evaluation
    y_pred = model.predict(X_test)
    print("\n" + "=" * 50)
    print("MODEL EVALUATION SUMMARY")
    print("=" * 50)
    print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=["Stay", "Churn"]))
    
    print("\nFeature Importance Ranking:")
    importances = sorted(
        zip(X.columns, model.feature_importances_), 
        key=lambda x: -x[1]
    )
    for feat, imp in importances:
        print(f"  {feat}: {imp:.4f}")

    # Persistence
    os.makedirs("ml", exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"\nModel successfully saved to {MODEL_PATH}")

if __name__ == "__main__":
    train()