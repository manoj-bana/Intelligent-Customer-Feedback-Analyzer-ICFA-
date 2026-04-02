# ICFA Admin Data Access Enhancement - TODO Steps

Current Progress: 7/10 ✅

## Approved Plan Implementation Breakdown

### Phase 1: Backend Security & Auth (Steps 1-4)
- [✅] **Step 1:** Read backend/auth.py content (already done, will edit).
- [✅] **Step 2:** Add JWT oauth2_scheme & get_current_user dependency to backend/auth.py.
- [✅] **Step 3:** Edit backend/routes/ingest.py: 
  - Add current_user dep to /results/{case_id}.
  - Secure: if not admin and dataset.user_id != current_user.id → 403.
  - Add new GET /ingest/cases: role-aware (admin=all, user=own).
- [✅] **Step 4:** Edit backend/routes/admin.py: add current_user dep to /admin/cases for consistency.

### Phase 2: Frontend Updates (Steps 5-7)
- [✅] **Step 5:** Read frontend/pages/feedback_page.py & churn_page.py (already done).
- [✅] **Step 6:** Edit feedback_page.py: use role-aware cases_url (/ingest/cases or /admin/cases).
- [✅] **Step 7:** Edit churn_page.py: same role-aware fetch.

### Phase 3: Verification (Steps 8-10)
- [ ] **Step 8:** Update this TODO.md: mark completed steps.
- [ ] **Step 9:** Test: execute commands to run backend/frontend, verify admin/user data scopes.
- [ ] **Step 10:** attempt_completion.


### Phase 2: Frontend Updates (Steps 5-7)
- [ ] **Step 5:** Read frontend/pages/feedback_page.py & churn_page.py (already done).
- [ ] **Step 6:** Edit feedback_page.py: use role-aware cases_url (/ingest/cases or /admin/cases).
- [ ] **Step 7:** Edit churn_page.py: same role-aware fetch.
- [ ] **Step 3:** Edit backend/routes/ingest.py: 
  - Add current_user dep to /results/{case_id}.
  - Secure: if not admin and dataset.user_id != current_user.id → 403.
  - Add new GET /ingest/cases: role-aware (admin=all, user=own).
- [ ] **Step 4:** Edit backend/routes/admin.py: add current_user dep to /admin/cases for consistency.

### Phase 2: Frontend Updates (Steps 5-7)
- [ ] **Step 5:** Read frontend/pages/feedback_page.py & churn_page.py (already done).
- [ ] **Step 6:** Edit feedback_page.py: use role-aware cases_url (/ingest/cases or /admin/cases).
- [ ] **Step 7:** Edit churn_page.py: same role-aware fetch.

### Phase 3: Verification (Steps 8-10)
- [ ] **Step 8:** Update this TODO.md: mark completed steps.
- [ ] **Step 9:** Test: execute commands to run backend/frontend, verify admin/user data scopes.
- [ ] **Step 10:** attempt_completion.

**Next:** Proceed to Step 1-2 in parallel (auth.py edit requires read confirm, but known).

**Legend:** [ ] Todo  | ✅ Done  | ❌ Blocked

