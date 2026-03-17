# Forgot Password Feature TODO

**Status: In Progress**

1. [✅] Update User model - Add security_answers field
2. [✅] Create/run DB migration
3. [✅] Update backend/auth.py - Endpoints for security questions
4. [✅] Update frontend/register.py - Add security answer inputs
5. [✅] Update frontend/login.py - Add Forgot Password UI/flow
6. [✅] Test register and forgot pw (after deps/backend start)
7. [ ] Update existing users (admin etc.)

**Run after each backend change:**
- cd Intelligent-Customer-Feedback-Analyzer-ICFA-/backend
- uvicorn main:app --reload --port 8000

**Frontend:**
- streamlit run frontend/app.py
