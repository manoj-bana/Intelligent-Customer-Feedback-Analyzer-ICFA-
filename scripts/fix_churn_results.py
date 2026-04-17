"""Fix churn results for previously processed uploads.

Usage:
  python scripts/fix_churn_results.py        # dry-run, lists affected datasets
  python scripts/fix_churn_results.py --apply  # actually reprocess and save results
"""
import json
import os
import sys
from datetime import datetime

# Ensure project root is on PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.db import SessionLocal
from backend.database.models import Dataset
from backend.services.churn_predictor import predict_churn


def find_affected(db):
    # Find churn datasets that were marked completed but have predicted_churn == 0 while total_customers > 0
    candidates = db.query(Dataset).filter(Dataset.task_type == 'Churn Prediction').all()
    affected = []
    for ds in candidates:
        if not ds.result_data:
            continue
        try:
            payload = json.loads(ds.result_data)
        except Exception:
            continue
        total = payload.get('total_customers') or payload.get('total') or 0
        pred = payload.get('predicted_churn', 0)
        # Heuristic: if there are customers but predicted churn is 0, it's suspicious
        if total and pred == 0:
            affected.append((ds, payload))
    return affected


def reprocess_dataset(db, ds):
    path = ds.file_path
    if not path or not os.path.exists(path):
        return False, f"file missing: {path}"
    import pandas as pd
    try:
        df = pd.read_csv(path)
    except Exception as e:
        return False, f"could not read csv: {e}"
    res = predict_churn(df)
    if isinstance(res, dict) and res.get('error'):
        # failed to predict
        ds.review_status = 'failed'
        ds.error_message = res.get('error')
        db.commit()
        return False, f"predict failed: {res.get('error')}"
    # success: save results
    ds.result_data = json.dumps(res)
    ds.review_status = 'completed'
    ds.last_analyzed = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    db.commit()
    return True, f"updated: {res.get('predicted_churn')} churners"


def main():
    apply = '--apply' in sys.argv
    db = SessionLocal()
    try:
        affected = find_affected(db)
        print(f"Found {len(affected)} churn datasets that look suspicious")
        for ds, payload in affected:
            print(f"- id={ds.id} case_id={ds.case_id} file={ds.file_path} total={payload.get('total_customers') or payload.get('total')}")
            if apply:
                ok, msg = reprocess_dataset(db, ds)
                print(f"  -> {msg}")
        if not affected:
            print('No suspicious churn datasets found.')
    finally:
        db.close()

if __name__ == '__main__':
    main()
