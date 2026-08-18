from database.setup import create_tables, SessionLocal
from utils.data_generator import create_students, create_activities
from utils.baseline_calculator import calculate_all_baselines
from utils.drift_detector import run_drift_detection


def setup():
    
    print("\n[Phase 1] Creating tables...")
    create_tables()

    print("[Phase 2] Generating student data...")
    db = SessionLocal()
    try:
        students = create_students(db)
        create_activities(db, students)
    finally:
        db.close()

    print("[Phase 3] Calculating baselines...")
    db = SessionLocal()
    try:
        calculate_all_baselines(db)
    finally:
        db.close()

    print("[Phase 4] Running drift detection...")
    db = SessionLocal()
    try:
        run_drift_detection(db)
    finally:
        db.close()

    print("\nSetup complete!")
    print("Now start the web server with:")
    print("    uvicorn api.server:app --reload")
    print("Then open:  http://127.0.0.1:8000\n")


if __name__ == "__main__":
    setup()