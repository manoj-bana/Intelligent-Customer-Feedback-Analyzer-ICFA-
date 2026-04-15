import pandas as pd
import os
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, roc_auc_score

# Configuration
DATA_PATH = "data/churn.csv"
MODEL_OUTPUT_PATH = "ml/churn_model.pkl"
CATEGORICAL_COLS = ['Contract', 'PaymentMethod', 'InternetService'] # Reference for default telco
TARGET_COL = 'Churn'

def train():
    print("🚀 Starting Model Training...")
    
    if not os.path.exists(DATA_PATH):
        print(f"❌ Error: Training data not found at {DATA_PATH}")
        return

    # 1. Load Data
    df = pd.read_csv(DATA_PATH)
    print(f"✅ Loaded {len(df)} rows.")

    # 2. Basic Preprocessing
    df = df.copy()
    
    # Handle TotalCharges if it has spaces
    if 'TotalCharges' in df.columns:
        df['TotalCharges'] = pd.to_numeric(df['TotalCharges'], errors='coerce')
        df['TotalCharges'] = df['TotalCharges'].fillna(df['TotalCharges'].median())

    # Map target to binary
    if TARGET_COL in df.columns:
        df[TARGET_COL] = df[TARGET_COL].map({'Yes': 1, 'No': 0})
    
    # Auto-detect categorical columns if not explicitly provided (Pandas 3+ compatible)
    cat_cols = df.select_dtypes(include=['object', 'string']).columns.tolist()
    if 'customerID' in cat_cols: cat_cols.remove('customerID') # Common in telco
    
    print(f"Preprocessing categorical columns: {cat_cols}")
    df_encoded = pd.get_dummies(df, columns=cat_cols, drop_first=True)
    
    # 3. Feature Selection
    X = df_encoded.drop([TARGET_COL, 'customerID'] if 'customerID' in df_encoded.columns else [TARGET_COL], axis=1)
    y = df_encoded[TARGET_COL]
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # 4. Training
    print("🛠️ Training Random Forest...")
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    # 5. Evaluation
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    
    auc = roc_auc_score(y_test, y_prob)
    print(f"🔥 Model Performance:")
    print(f"   ROC-AUC: {auc:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))

    # 6. Save Model
    os.makedirs(os.path.dirname(MODEL_OUTPUT_PATH), exist_ok=True)
    joblib.dump(model, MODEL_OUTPUT_PATH)
    print(f"💾 Model saved to {MODEL_OUTPUT_PATH}")

if __name__ == "__main__":
    train()
