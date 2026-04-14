import os
import joblib
import pandas as pd
import matplotlib.pyplot as plt
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    roc_auc_score,
    confusion_matrix
)

DATA_PATH = "data/churn_data.csv"
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
    Enhanced training pipeline: Uses XGBoost with imbalance handling and captures feature importance.
    """
    print("🚀 Initializing Churn Prediction Training (XGBoost Optimized)...")
    if not os.path.exists(DATA_PATH):
        print(f"Error: {DATA_PATH} not found. Please ensure the dataset is in the data/ directory.")
        return
        
    df = pd.read_csv(DATA_PATH)

    # 1. Cleaning & Type Correction
    df = df.drop(columns=["customerID"], errors="ignore")
    df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce")
    df["Churn"] = df["Churn"].map({"Yes": 1, "No": 0})
    df = df.dropna(subset=["Churn", "TotalCharges"])

    # 2. Feature Selection
    available_features = [f for f in FEATURES if f in df.columns]
    X = df[available_features].copy()
    y = df["Churn"]

    # 3. Encoding & Imputation
    X = pd.get_dummies(X, drop_first=True)
    X = X.fillna(X.median(numeric_only=True))

    # 4. Stratified Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # 5. Handle Class Imbalance
    # Calculate scale factor (count of negative / count of positive)
    counts = y_train.value_counts()
    scale_factor = round(counts[0] / counts[1], 2)
    print(f"Detected class imbalance. Apply scale_pos_weight: {scale_factor}")

    # 6. Initialize & Train XGBoost
    model = XGBClassifier(
        n_estimators=300,
        learning_rate=0.05,
        max_depth=6,
        scale_pos_weight=scale_factor,
        random_state=42,
        use_label_encoder=False,
        eval_metric='logloss'
    )

    model.fit(X_train, y_train)

    # 7. Comprehensive Evaluation
    y_pred = model.predict(X_test)
    y_probs = model.predict_proba(X_test)[:, 1]
    
    print("\n" + "=" * 50)
    print("📈 ADVANCED MODEL EVALUATION SUMMARY")
    print("=" * 50)
    print(f"Accuracy:  {accuracy_score(y_test, y_pred):.4f}")
    print(f"ROC-AUC:   {roc_auc_score(y_test, y_probs):.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=["Stay", "Churn"]))
    
    # 8. Feature Importance Ranking & Save Plot
    print("\n📍 Top Churn Drivers:")
    importances = pd.Series(model.feature_importances_, index=X.columns).sort_values(ascending=False)
    for feat, imp in importances.items():
        print(f"  {feat}: {imp:.4f}")

    # Visualizing
    plt.figure(figsize=(10, 6))
    importances.sort_values().plot(kind='barh', color='skyblue')
    plt.title("XGBoost Feature Importance")
    plt.xlabel("Importance Score")
    os.makedirs("ml/plots", exist_ok=True)
    plt.savefig("ml/plots/feature_importance.png")
    print("\n📊 Feature importance chart saved to ml/plots/feature_importance.png")

    # 9. Persistence
    os.makedirs("ml", exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"✅ Trained model successfully saved to {MODEL_PATH}")

if __name__ == "__main__":
    train()
