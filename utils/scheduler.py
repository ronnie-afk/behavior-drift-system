

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
from database.setup import SessionLocal
from utils.baseline_calculator import calculate_all_baselines
from utils.drift_detector import run_drift_detection
from utils.telegram_bot import send_daily_alert
from models.activity import DriftRecord
from models.student import Student

scheduler = BackgroundScheduler()

ALERT_THRESHOLD = 0.35
WATCH_THRESHOLD = 0.20


def run_daily_detection():
    """Runs every morning at 7 AM — detects drift and sends Telegram alert."""
    print(f"\n[Scheduler] Running daily detection at {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    db = SessionLocal()
    try:
        calculate_all_baselines(db)
        run_drift_detection(db)

        # Load today's results to send via Telegram
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        students = {s.id: s for s in db.query(Student).all()}
        records  = (
            db.query(DriftRecord)
            .filter(DriftRecord.date == today)
            .order_by(DriftRecord.drift_score.desc())
            .all()
        )

        alerted, watched = [], []
        for r in records:
            s = students.get(r.student_id)
            if not s:
                continue
            if r.drift_score >= ALERT_THRESHOLD:
                alerted.append((s, r))
            elif r.drift_score >= WATCH_THRESHOLD:
                watched.append((s, r))

        send_daily_alert(alerted, watched)
        print("[Scheduler] Detection complete.")

    except Exception as e:
        print(f"[Scheduler] ERROR: {e}")
    finally:
        db.close()


def start_scheduler():
    scheduler.add_job(
        func             = run_daily_detection,
        trigger          = CronTrigger(hour=7, minute=0),
        id               = "daily_drift_detection",
        name             = "Daily drift detection",
        replace_existing = True,
    )
    scheduler.start()
    print("[Scheduler] Started — daily detection at 07:00 AM.")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        print("[Scheduler] Stopped.")