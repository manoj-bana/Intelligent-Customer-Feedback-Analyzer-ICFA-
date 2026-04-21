# ICFA: Intelligent Customer Feedback Analyzer 📊

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat&logo=Streamlit&logoColor=white)](https://streamlit.io/)
[![SQLite](https://img.shields.io/badge/SQLite-07405E?style=flat&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)

**ICFA** is a high-performance, full-stack application designed to transform raw customer feedback into actionable business intelligence. By leveraging Natural Language Processing (NLP) and supervised Machine Learning, it provides tiered insights into customer sentiment and predicts potential churn at scale.

---

## 🔍 Overview

Managing thousands of customer reviews manually is a bottleneck for modern businesses. ICFA solves this by providing:
1. **Automated Sentiment Scoring**: Real-time analysis of feedback polarity.
2. **Predictive Retention**: Identifying at-risk customers through behavioral churn modeling.
3. **Data-Driven Dashboards**: Visualizing KPIs like churn rates and sentiment distribution.

---

## ✨ Features

- **🔐 Enterprise Security**: Secure JWT authentication, password hashing with bcrypt, and security-question-based recovery.
- **☁️ Case-Based Ingestion**: Upload large CSV files for background processing; no UI blocking.
- **💬 Sentiment Intelligence**: Combined VADER sentiment analysis and TF-IDF keyword extraction.
- **📉 Churn Forecasting**: Predictive modeling (Random Forest) for customer subscription risk profiling.
- **📊 Interactive Dashboard**: Real-time monitoring of "My Cases", success rates, and detailed reporting views.
- **🛠️ Self-Healing Pipeline**: Tools to retry stalled or failed processing tasks.

---

## 🛠️ Tech Stack

- **Backend**: [FastAPI](https://fastapi.tiangolo.com/) (Asynchronous, Type-hinted)
- **Frontend**: [Streamlit](https://streamlit.io/) (Data-centric UI)
- **Database**: [SQLAlchemy](https://www.sqlalchemy.org/) with SQLite
- **NLP**: [NLTK](https://www.nltk.org/) (VADER), Scikit-Learn (TF-IDF)
- **ML**: [Scikit-Learn](https://scikit-learn.org/) (Predictive Inference)
- **Processing**: [Pandas](https://pandas.pydata.org/) (Chunk-based data handling)

---

## 🚀 Installation

### 1. Prerequisite: Virtual Environment
We recommend using a clean virtual environment to avoid dependency conflicts.
```bash
# Create and activate environment
python -m venv venv
source venv/Scripts/activate  # On Windows, use `venv\Scripts\activate`
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. NLP Data Setup (Required)
Download the necessary NLTK corpora for sentiment analysis and lemmatization:
```bash
python scripts/download_nltk.py
```

### 4. Database Initialization
Ensure the database schema and security features are ready:
```bash
python tools/migrate_hashes.py
```

---

## 💻 Usage

### **Running the Application**

ICFA requires two services to run simultaneously. Open two terminal windows:

**Terminal 1: FastAPI Backend**
```bash
# Launch the ASGI server
uvicorn backend.main:app --reload
```

**Terminal 2: Streamlit Frontend**
```bash
# Launch the web interface
streamlit run frontend/app.py
```

### **Workflow**
1. **Register/Login**: Create a secure account with a security question.
2. **Upload**: Navigate to `Document Ingestion`, upload your CSV, and select the task type (Sentiment or Churn).
3. **Analyze**: View the `Home` dashboard to monitor processing status.
4. **Report**: Once completed, explore detailed charts in the `Reports` section.

---

## 📂 Folder Structure

```text
├── backend/            # FastAPI core, authentication, and routing
│   ├── database/       # SQLAlchemy models and connection logic
│   ├── routes/         # API endpoints (Auth, Ingest)
│   └── utils/          # NLP and ML inference utilities
├── frontend/           # Streamlit application and page modules
│   └── pages/          # Individual dashboard views
├── ml/                 # Pre-trained models and training scripts
├── tests/              # Pytest suite for API and ML logic
├── uploads/            # Temporary storage for data and results
└── requirements.txt    # Project dependencies
```

---

## 📈 Future Improvements

- **Scale**: Integrate **Celery + Redis** for distributed, heavy-duty processing of multimillion-row datasets.
- **Security**: Implement full **OAuth2/OpenID Connect** flows.
- **Storage**: Migrate local storage to **Amazon S3** and database to **PostgreSQL**.
- **UX**: Add real-time WebSocket notifications for task completion.

---

## ⚖️ License
This project is licensed under the [MIT License](LICENSE).
