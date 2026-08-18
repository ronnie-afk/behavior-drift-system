# Behavior Drift Detection System for Student Learning Patterns

A full-stack ML-powered web application that detects behavioral drift
in student learning patterns using z-score anomaly detection and
Random Forest classification.

## What it does
- Monitors student login frequency, study time, quiz scores, and submissions daily
- Calculates personalized baselines for each student using a 30-day rolling window
- Detects drift using z-score anomaly detection
- Alerts teachers via dashboard, email, and Telegram
- Predicts future at-risk students using Random Forest ML
- Student self-service portal for personal progress tracking

## Tech Stack
Python 3.12 | FastAPI | SQLAlchemy | SQLite | scikit-learn |
pandas | APScheduler | ReportLab | Telegram API | Chart.js

## Dataset
Validated on the Open University Learning Analytics Dataset (OULAD)
- 500 students imported
- 406 students with sufficient data
- 8 students detected as watch-level (2.0%)
- 100% recall on synthetic ground truth (5/5 drifting students found)

## Setup

### 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/behavior-drift-system.git
cd behavior-drift-system

### 2. Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux

### 3. Install dependencies
pip install -r requirements.txt

### 4. Set up database and data
python main.py

### 5. Create teacher accounts
python utils/teacher_setup.py

### 6. Start the server
uvicorn api.server:app --reload

### 7. Open browser
http://127.0.0.1:8000

## Login Credentials
| Username | Password | Access |
|----------|----------|--------|
| admin | admin2024 | All students |
| teacher1 | pass1234 | Data Science |
| teacher2 | pass1234 | Machine Learning |
| teacher3 | pass1234 | Web Development |

## Project Structure
behavior_drift_system/
├── main.py # Entry point
├── requirements.txt # Dependencies
├── api/server.py # FastAPI web server
├── database/setup.py # Database connection
├── models/ # Database models
└── utils/ # Business logic
├── baseline_calculator.py
├── drift_detector.py
├── ml_predictor.py
├── alert_engine.py
└── ...

## Research References
- Kuzilek et al. (2017) — OULAD Dataset — Nature Scientific Data
- Jimenez Martinez et al. (2024) — Early Detection of At-Risk Students

## Author
BTech Computer Science Final Year Project