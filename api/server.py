"""
api/server.py — FINAL complete version with ALL upgrades:
  Easy:     email alerts, drift chart, search/filter, teacher notes
  Medium:   multi-teacher login, PDF report, course analytics, Telegram
  Advanced: ML prediction, student portal

HOW TO RUN LOCALLY:
    python utils/teacher_setup.py    ← once
    python utils/student_setup.py    ← once
    python main.py                   ← once
    uvicorn api.server:app --reload

Teacher login: http://127.0.0.1:8000
Student login: http://127.0.0.1:8000/student-login
"""

from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from database.setup import SessionLocal
from models.student import Student
from models.activity import DailyActivity, DriftRecord, StudentBaseline
from models.notes import TeacherNote
from models.student_user import StudentUser
from utils.baseline_calculator import calculate_all_baselines
from utils.drift_detector import run_drift_detection
from utils.auth import (
    check_credentials, create_session,
    get_current_user, require_login, active_sessions
)
from utils.data_importer import import_from_bytes
from utils.scheduler import start_scheduler, stop_scheduler
from utils.emailer import send_alert_email
from utils.pdf_report import generate_pdf
from utils.telegram_bot import send_daily_alert
from utils.ml_predictor import predict_at_risk_students

app = FastAPI(title="Behavior Drift Detection System")

ALERT_THRESHOLD = 0.35
WATCH_THRESHOLD = 0.20

# Separate session store for students (keeps teacher and student sessions apart)
student_sessions: dict[str, int] = {}   # token → student_id


# ── Lifecycle ─────────────────────────────────────────────────────────────
@app.on_event("startup")
def on_startup():
    start_scheduler()

@app.on_event("shutdown")
def on_shutdown():
    stop_scheduler()


# ── Database helper ───────────────────────────────────────────────────────
def get_db() -> Session:
    return SessionLocal()


# ══════════════════════════════════════════════════════════════════════════
# HTML HELPERS
# ══════════════════════════════════════════════════════════════════════════

def bar(value: float, color: str) -> str:
    pct = round(value * 100)
    return (
        f'<div style="background:#f0f0f0;border-radius:4px;height:8px;margin:3px 0;">'
        f'<div style="width:{pct}%;background:{color};height:8px;border-radius:4px;"></div>'
        f'</div>'
    )


def tip(record: DriftRecord) -> str:
    worst = max(
        {"score": record.score_drift,
         "session": record.session_drift,
         "submission": record.submission_drift},
        key=lambda k: {"score": record.score_drift,
                       "session": record.session_drift,
                       "submission": record.submission_drift}[k]
    )
    tips = {
        "score":      "Quiz scores dropped — consider a 1-on-1 check-in and share revision materials.",
        "session":    "Study time dropped sharply — send an encouraging message.",
        "submission": "Assignments being missed — check deadlines and offer an extension if needed.",
    }
    return tips[worst]


def student_card(s: Student, r: DriftRecord, border: str, status: str = "") -> str:
    return f"""
    <div class="student-card"
         data-name="{s.name.lower()}"
         data-course="{s.course.lower()}"
         data-status="{status}"
         style="background:white;border:1px solid {border};border-left:5px solid {border};
                border-radius:8px;padding:18px;margin-bottom:14px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
        <div>
          <a href="/student/{s.id}" style="font-size:16px;font-weight:600;
             color:#222;text-decoration:none;">{s.name}</a>
          <span style="color:#888;font-size:13px;margin-left:8px;">{s.course}</span>
        </div>
        <div style="font-size:24px;font-weight:700;color:{border};">{r.drift_score:.2f}</div>
      </div>
      <div style="font-size:13px;color:#555;margin-bottom:10px;">
        <strong>Signals:</strong> {r.notes or 'within normal range'}
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:12px;">
        <div>
          <div style="font-size:12px;color:#777;">Quiz score</div>
          {bar(r.score_drift, '#e74c3c')}
          <div style="font-size:12px;text-align:right;">{r.score_drift:.2f}</div>
        </div>
        <div>
          <div style="font-size:12px;color:#777;">Session time</div>
          {bar(r.session_drift, '#e67e22')}
          <div style="font-size:12px;text-align:right;">{r.session_drift:.2f}</div>
        </div>
        <div>
          <div style="font-size:12px;color:#777;">Submissions</div>
          {bar(r.submission_drift, '#9b59b6')}
          <div style="font-size:12px;text-align:right;">{r.submission_drift:.2f}</div>
        </div>
      </div>
      <div style="background:#f8f9fa;border-radius:6px;padding:10px;font-size:13px;">
        <strong>Recommended action:</strong> {tip(r)}
      </div>
    </div>"""


def base_page(title: str, body: str, username: str = "", full_name: str = "") -> str:
    display_name = full_name or username
    logout_btn = (
        f'<span style="color:#bdc3c7;font-size:13px;">{display_name}</span>'
        f'&nbsp;<a href="/logout" style="color:#95a5a6;font-size:12px;">(logout)</a>'
        if username else ""
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{title}</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
          background:#f4f6f9;color:#222;}}
    nav{{background:#2c3e50;padding:14px 24px;display:flex;
         align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;}}
    nav a{{color:white;text-decoration:none;font-size:15px;font-weight:500;}}
    nav .links{{display:flex;align-items:center;gap:20px;flex-wrap:wrap;}}
    nav .links a{{color:#bdc3c7;font-size:13px;}}
    nav .links a:hover{{color:white;}}
    .container{{max-width:960px;margin:0 auto;padding:28px 20px;}}
    h1{{font-size:22px;font-weight:600;margin-bottom:6px;}}
    h2{{font-size:16px;font-weight:600;margin:26px 0 12px;}}
    .subtitle{{color:#888;font-size:13px;margin-bottom:24px;}}
    .grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:28px;}}
    .card{{background:white;border-radius:10px;padding:18px;text-align:center;
           border-top:4px solid #ddd;}}
    .card .n{{font-size:34px;font-weight:700;}}
    .card .l{{font-size:13px;color:#888;margin-top:4px;}}
    .section{{background:white;border-radius:10px;padding:20px;margin-bottom:20px;}}
    .section-head{{display:flex;align-items:center;gap:10px;margin-bottom:14px;
                   padding-bottom:10px;border-bottom:1px solid #eee;}}
    .badge{{border-radius:20px;padding:3px 10px;font-size:12px;font-weight:600;}}
    .pill{{display:inline-block;border-radius:20px;padding:4px 12px;margin:3px;
           font-size:13px;background:#eafaf1;color:#1e8449;border:1px solid #a9dfbf;}}
    .btn{{border:none;border-radius:6px;padding:10px 20px;font-size:14px;
          cursor:pointer;color:white;}}
    input[type=text],input[type=password]{{width:100%;padding:10px 12px;
      border:1px solid #ddd;border-radius:6px;font-size:14px;margin-bottom:12px;}}
    select{{padding:9px 12px;border:1px solid #ddd;border-radius:6px;
            font-size:14px;background:white;}}
    footer{{text-align:center;font-size:12px;color:#aaa;margin-top:32px;padding:20px;}}
  </style>
</head>
<body>
<nav>
  <a href="/">Drift Detection System</a>
  <div class="links">
    <a href="/">Dashboard</a>
    <a href="/analytics">Analytics</a>
    <a href="/predictions">ML Predictions</a>
    <a href="/upload">Upload</a>
    <a href="/report/pdf">PDF</a>
    <a href="/api/drift">API</a>
    {logout_btn}
  </div>
</nav>
<div class="container">
{body}
</div>
<footer>Behavior Drift Detection System &nbsp;|&nbsp;
Alert: {ALERT_THRESHOLD} &nbsp;|&nbsp; Watch: {WATCH_THRESHOLD} &nbsp;|&nbsp;
<a href="/student-login" style="color:#aaa;">Student portal</a>
</footer>
</body></html>"""


def student_base_page(title: str, body: str, student_name: str = "") -> str:
    """Separate page shell for the student portal — simpler nav."""
    logout_btn = (
        f'<span style="color:#bdc3c7;font-size:13px;">{student_name}</span>'
        f'&nbsp;<a href="/student-logout" style="color:#95a5a6;font-size:12px;">(logout)</a>'
        if student_name else ""
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{title} — Student Portal</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
          background:#f4f6f9;color:#222;}}
    nav{{background:#1a5276;padding:14px 24px;display:flex;
         align-items:center;justify-content:space-between;}}
    nav a{{color:white;text-decoration:none;font-size:15px;font-weight:500;}}
    .container{{max-width:860px;margin:0 auto;padding:28px 20px;}}
    h1{{font-size:22px;font-weight:600;margin-bottom:6px;}}
    h2{{font-size:16px;font-weight:600;margin:26px 0 12px;}}
    .subtitle{{color:#888;font-size:13px;margin-bottom:24px;}}
    .grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:28px;}}
    .card{{background:white;border-radius:10px;padding:18px;text-align:center;
           border-top:4px solid #ddd;}}
    .card .n{{font-size:28px;font-weight:700;}}
    .card .l{{font-size:13px;color:#888;margin-top:4px;}}
    .section{{background:white;border-radius:10px;padding:20px;margin-bottom:20px;}}
    .btn{{border:none;border-radius:6px;padding:10px 20px;font-size:14px;
          cursor:pointer;color:white;}}
    input[type=text],input[type=password]{{width:100%;padding:10px 12px;
      border:1px solid #ddd;border-radius:6px;font-size:14px;margin-bottom:12px;}}
    footer{{text-align:center;font-size:12px;color:#aaa;margin-top:32px;padding:20px;}}
  </style>
</head>
<body>
<nav>
  <a href="/my-dashboard">My Learning Dashboard</a>
  <div>{logout_btn}</div>
</nav>
<div class="container">
{body}
</div>
<footer>Student Learning Portal</footer>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════
# DATA LOADERS
# ══════════════════════════════════════════════════════════════════════════

def load_dashboard_data(db: Session, course_filter: str = "all") -> dict:
    today    = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    student_query = db.query(Student)
    if course_filter != "all":
        student_query = student_query.filter(Student.course == course_filter)
    students = {s.id: s for s in student_query.all()}

    records = (
        db.query(DriftRecord)
        .filter(DriftRecord.date == today)
        .order_by(DriftRecord.drift_score.desc())
        .all()
    )

    alerted, watched, healthy = [], [], []
    for r in records:
        s = students.get(r.student_id)
        if not s:
            continue
        if r.drift_score >= ALERT_THRESHOLD:
            alerted.append((s, r))
        elif r.drift_score >= WATCH_THRESHOLD:
            watched.append((s, r))
        else:
            healthy.append((s, r))

    if alerted:
        send_alert_email(alerted)

    return {
        "alerted":   alerted,
        "watched":   watched,
        "healthy":   healthy,
        "generated": datetime.utcnow().strftime("%d %B %Y, %H:%M UTC"),
        "total":     len(alerted) + len(watched) + len(healthy),
    }


def get_course_filter(user) -> str:
    if isinstance(user, dict):
        return user.get("course", "all")
    return "all"

def get_username(user) -> str:
    if isinstance(user, dict):
        return user.get("username", str(user))
    return str(user)

def get_full_name(user) -> str:
    if isinstance(user, dict):
        return user.get("full_name", user.get("username", ""))
    return str(user)


# ══════════════════════════════════════════════════════════════════════════
# ROUTES — TEACHER AUTH
# ══════════════════════════════════════════════════════════════════════════

@app.get("/login", response_class=HTMLResponse)
def login_page(error: str = ""):
    error_html = (
        f'<p style="color:#e74c3c;margin-bottom:12px;font-size:14px;">{error}</p>'
        if error else ""
    )
    body = f"""
    <div style="max-width:380px;margin:80px auto;">
      <div style="background:white;border-radius:12px;padding:36px;
                  box-shadow:0 2px 12px rgba(0,0,0,0.08);">
        <h1 style="margin-bottom:6px;">Teacher Login</h1>
        <p style="color:#888;font-size:13px;margin-bottom:24px;">
          Behavior Drift Detection System
        </p>
        {error_html}
        <form action="/login" method="post">
          <label style="font-size:13px;color:#555;display:block;margin-bottom:4px;">
            Username</label>
          <input type="text" name="username" placeholder="admin" autofocus>
          <label style="font-size:13px;color:#555;display:block;margin-bottom:4px;">
            Password</label>
          <input type="password" name="password" placeholder="••••••••">
          <button class="btn" type="submit"
            style="background:#2980b9;width:100%;margin-top:8px;">Log in</button>
        </form>
        <p style="font-size:12px;color:#aaa;margin-top:16px;text-align:center;">
          Default: admin / admin2024
        </p>
        <p style="font-size:12px;color:#aaa;margin-top:6px;text-align:center;">
          <a href="/student-login" style="color:#3498db;">Student portal →</a>
        </p>
      </div>
    </div>"""
    return HTMLResponse(base_page("Login", body))


@app.post("/login")
def login_submit(username: str = Form(...), password: str = Form(...)):
    teacher = check_credentials(username, password)
    if teacher:
        token    = create_session(teacher)
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(key="session", value=token, httponly=True)
        return response
    return RedirectResponse(
        url="/login?error=Invalid+username+or+password", status_code=302
    )


@app.get("/logout")
def logout(request: Request):
    token = request.cookies.get("session")
    if token and token in active_sessions:
        del active_sessions[token]
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("session")
    return response


# ══════════════════════════════════════════════════════════════════════════
# ROUTES — STUDENT PORTAL AUTH
# ══════════════════════════════════════════════════════════════════════════

@app.get("/student-login", response_class=HTMLResponse)
def student_login_page(error: str = ""):
    """
    Separate login page for students.
    Students log in here to see only their own data.
    """
    error_html = (
        f'<p style="color:#e74c3c;margin-bottom:12px;font-size:14px;">{error}</p>'
        if error else ""
    )
    body = f"""
    <div style="max-width:380px;margin:80px auto;">
      <div style="background:white;border-radius:12px;padding:36px;
                  box-shadow:0 2px 12px rgba(0,0,0,0.08);">
        <h1 style="margin-bottom:6px;">Student Portal</h1>
        <p style="color:#888;font-size:13px;margin-bottom:24px;">
          View your own learning activity and progress
        </p>
        {error_html}
        <form action="/student-login" method="post">
          <label style="font-size:13px;color:#555;display:block;margin-bottom:4px;">
            Username</label>
          <input type="text" name="username"
                 placeholder="your first name e.g. arjun" autofocus>
          <label style="font-size:13px;color:#555;display:block;margin-bottom:4px;">
            Password</label>
          <input type="password" name="password" placeholder="••••••••">
          <button class="btn" type="submit"
            style="background:#1a5276;width:100%;margin-top:8px;">Log in</button>
        </form>
        <p style="font-size:12px;color:#aaa;margin-top:16px;text-align:center;">
          Default password: student123
        </p>
        <p style="font-size:12px;color:#aaa;margin-top:6px;text-align:center;">
          <a href="/login" style="color:#3498db;">Teacher login →</a>
        </p>
      </div>
    </div>"""
    # Student portal uses its own base page (different nav colour)
    return HTMLResponse(student_base_page("Login", body))


@app.post("/student-login")
def student_login_submit(username: str = Form(...), password: str = Form(...)):
    """
    Checks student credentials against the student_users table.
    Sets a separate cookie called 'student_session'.
    """
    import secrets as secrets_module
    db = get_db()
    try:
        account = db.query(StudentUser).filter(
            StudentUser.username == username
        ).first()
        if account and account.check_password(password):
            token = secrets_module.token_urlsafe(32)
            student_sessions[token] = account.student_id
            response = RedirectResponse(url="/my-dashboard", status_code=302)
            response.set_cookie(key="student_session", value=token, httponly=True)
            return response
    finally:
        db.close()

    return RedirectResponse(
        url="/student-login?error=Invalid+username+or+password",
        status_code=302
    )


@app.get("/student-logout")
def student_logout(request: Request):
    token = request.cookies.get("student_session")
    if token and token in student_sessions:
        del student_sessions[token]
    response = RedirectResponse(url="/student-login", status_code=302)
    response.delete_cookie("student_session")
    return response


def get_current_student_id(request: Request) -> int | None:
    """Returns the logged-in student's ID, or None if not logged in."""
    token = request.cookies.get("student_session")
    if not token:
        return None
    return student_sessions.get(token)


# ══════════════════════════════════════════════════════════════════════════
# ROUTES — STUDENT PORTAL PAGES
# ══════════════════════════════════════════════════════════════════════════

@app.get("/my-dashboard", response_class=HTMLResponse)
def student_dashboard(request: Request):
    """
    The student's personal dashboard.
    Shows only their own data — drift score, activity, study tips.
    They cannot see any other student's data.
    """
    student_id = get_current_student_id(request)
    if not student_id:
        return RedirectResponse(url="/student-login", status_code=302)

    db = get_db()
    try:
        student  = db.query(Student).filter(Student.id == student_id).first()
        baseline = db.query(StudentBaseline).filter(
            StudentBaseline.student_id == student_id
        ).first()

        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        drift = db.query(DriftRecord).filter(
            DriftRecord.student_id == student_id,
            DriftRecord.date == today
        ).first()

        # Last 14 days of activity
        cutoff = datetime.utcnow() - timedelta(days=14)
        activities = (
            db.query(DailyActivity)
            .filter(DailyActivity.student_id == student_id,
                    DailyActivity.date >= cutoff)
            .order_by(DailyActivity.date.desc())
            .all()
        )

        # Last 30 days of drift for chart
        chart_cutoff = datetime.utcnow() - timedelta(days=30)
        drift_history = (
            db.query(DriftRecord)
            .filter(DriftRecord.student_id == student_id,
                    DriftRecord.date >= chart_cutoff)
            .order_by(DriftRecord.date)
            .all()
        )

    finally:
        db.close()

    # ── Drift status message — student-friendly language ─────────────
    if drift:
        score = drift.drift_score
        if score >= ALERT_THRESHOLD:
            status_color = "#e74c3c"
            status_icon  = "Your teacher may reach out to help you soon."
            status_text  = "Your learning pattern has changed significantly this week."
        elif score >= WATCH_THRESHOLD:
            status_color = "#e67e22"
            status_icon  = "Things are slightly off track — small changes can help."
            status_text  = "Your activity is a little below your usual level."
        else:
            status_color = "#27ae60"
            status_icon  = "Keep it up!"
            status_text  = "You are on track this week."

        status_html = f"""
        <div style="background:{status_color};color:white;border-radius:10px;
                    padding:20px;margin-bottom:20px;">
          <div style="font-size:18px;font-weight:600;margin-bottom:6px;">
            {status_text}
          </div>
          <div style="font-size:14px;opacity:0.9;">{status_icon}</div>
        </div>"""
    else:
        status_html = '<p style="color:#aaa;">No activity data for today yet.</p>'

    # ── Baseline summary ─────────────────────────────────────────────
    bl_html = ""
    if baseline:
        bl_html = f"""
        <div class="grid">
          <div class="card" style="border-top-color:#3498db;">
            <div class="n" style="color:#3498db;">{baseline.avg_quiz_score:.0f}</div>
            <div class="l">Your avg quiz score</div>
          </div>
          <div class="card" style="border-top-color:#27ae60;">
            <div class="n" style="color:#27ae60;">{baseline.avg_session_minutes:.0f}m</div>
            <div class="l">Your avg study time</div>
          </div>
          <div class="card" style="border-top-color:#9b59b6;">
            <div class="n" style="color:#9b59b6;">{baseline.submission_rate*100:.0f}%</div>
            <div class="l">Your submission rate</div>
          </div>
        </div>"""

    # ── Chart ────────────────────────────────────────────────────────
    chart_labels = [d.date.strftime('%d %b') for d in drift_history]
    chart_scores = [round(d.drift_score, 3)   for d in drift_history]
    labels_js    = str(chart_labels).replace("'", '"')
    scores_js    = str(chart_scores)

    chart_html = f"""
    <canvas id="myChart" style="max-height:200px;"></canvas>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <script>
      new Chart(document.getElementById('myChart').getContext('2d'), {{
        type: 'line',
        data: {{
          labels: {labels_js},
          datasets: [{{
            data: {scores_js},
            borderColor: '#3498db',
            backgroundColor: 'rgba(52,152,219,0.08)',
            borderWidth: 2, pointRadius: 3, fill: true, tension: 0.3
          }}]
        }},
        options: {{
          responsive: true,
          plugins: {{ legend: {{ display: false }} }},
          scales: {{
            y: {{ min: 0, max: 1, ticks: {{ stepSize: 0.25 }} }},
            x: {{ grid: {{ display: false }} }}
          }}
        }}
      }});
    </script>
    <p style="font-size:12px;color:#aaa;margin-top:8px;">
      Lower is better — 0 means perfectly on track, 1 means significant drift
    </p>"""

    # ── Activity table ───────────────────────────────────────────────
    rows = ""
    for a in activities:
        score_str = f"{a.quiz_score:.0f}" if a.quiz_score is not None else "—"
        sub_str   = "Yes" if a.submitted else "No"
        sub_color = "#27ae60" if a.submitted else "#e74c3c"
        rows += f"""
        <tr style="border-bottom:1px solid #f5f5f5;">
          <td style="padding:8px 6px;">{a.date.strftime('%d %b')}</td>
          <td style="padding:8px 6px;text-align:center;">{a.session_minutes:.0f} min</td>
          <td style="padding:8px 6px;text-align:center;">{score_str}</td>
          <td style="padding:8px 6px;text-align:center;
              color:{sub_color};font-weight:600;">{sub_str}</td>
        </tr>"""

    # ── Study tips ───────────────────────────────────────────────────
    tips_html = """
    <ul style="font-size:14px;color:#444;line-height:2;padding-left:20px;">
      <li>Log in every day even for just 15 minutes — consistency matters more than length.</li>
      <li>Submit assignments even if incomplete — partial credit is better than zero.</li>
      <li>Take quizzes even when not fully prepared — it helps identify gaps early.</li>
      <li>If you are struggling, contact your teacher — they can see your progress.</li>
    </ul>"""

    body = f"""
    <h1>Hello, {student.name.split()[0]}!</h1>
    <p class="subtitle">{student.course} &nbsp;|&nbsp; Your personal learning dashboard</p>

    {status_html}

    <div class="section">
      <h2>Your averages (last 30 days)</h2>
      {bl_html}
    </div>

    <div class="section">
      <h2>Your activity trend</h2>
      {chart_html}
    </div>

    <div class="section">
      <h2>Recent activity (last 14 days)</h2>
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <thead>
          <tr style="background:#f8f9fa;font-weight:600;">
            <th style="padding:10px 6px;text-align:left;">Date</th>
            <th style="padding:10px 6px;">Study time</th>
            <th style="padding:10px 6px;">Quiz score</th>
            <th style="padding:10px 6px;">Submitted</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>

    <div class="section">
      <h2>Study tips</h2>
      {tips_html}
    </div>"""

    return HTMLResponse(student_base_page(
        student.name, body, student_name=student.name.split()[0]
    ))


# ══════════════════════════════════════════════════════════════════════════
# ROUTES — ML PREDICTIONS
# ══════════════════════════════════════════════════════════════════════════

@app.get("/predictions", response_class=HTMLResponse)
def predictions_page(request: Request):
    """
    Shows ML predictions — which currently healthy students are
    likely to drift in the next 7 days.
    """
    user = require_login(request)
    if isinstance(user, RedirectResponse):
        return user

    db = get_db()
    try:
        at_risk = predict_at_risk_students(db)
    finally:
        db.close()

    if not at_risk:
        cards_html = """
        <div style="background:#eafaf1;border-radius:8px;padding:20px;color:#1e8449;">
          <strong>No students predicted to drift soon.</strong><br>
          <span style="font-size:13px;">Either all healthy students look stable,
          or not enough historical data exists yet to make predictions.</span>
        </div>"""
    else:
        cards_html = ""
        for item in at_risk:
            s     = item["student"]
            prob  = item["probability"]
            risk  = item["risk_level"]
            signal= item["top_signal"]

            color = ("#e74c3c" if risk == "high" else
                     "#e67e22" if risk == "medium" else "#f39c12")
            bg    = ("#fdecea" if risk == "high" else
                     "#fef5e7" if risk == "medium" else "#fefde7")

            cards_html += f"""
            <div style="background:white;border:1px solid {color};
                        border-left:5px solid {color};border-radius:8px;
                        padding:18px;margin-bottom:14px;">
              <div style="display:flex;justify-content:space-between;
                          align-items:center;margin-bottom:10px;">
                <div>
                  <a href="/student/{s.id}"
                     style="font-size:16px;font-weight:600;color:#222;
                            text-decoration:none;">{s.name}</a>
                  <span style="color:#888;font-size:13px;margin-left:8px;">
                    {s.course}</span>
                </div>
                <div style="text-align:right;">
                  <div style="font-size:22px;font-weight:700;color:{color};">
                    {int(prob * 100)}%</div>
                  <div style="font-size:11px;color:#aaa;">drift probability</div>
                </div>
              </div>
              <div style="background:{bg};border-radius:6px;padding:10px;
                          font-size:13px;margin-bottom:10px;">
                <strong>Main signal:</strong> {signal}
              </div>
              <div style="background:#f8f9fa;border-radius:6px;padding:10px;
                          font-size:13px;">
                <strong>Suggested action:</strong>
                Send a proactive check-in message now, before performance drops further.
                Early intervention is far more effective than waiting for an alert.
              </div>
            </div>"""

    body = f"""
    <h1>ML Drift Predictions</h1>
    <p class="subtitle">
      Students currently healthy but predicted to drift in the next 7 days.
      Model trained on historical drift patterns.
    </p>

    <div class="section">
      <div style="background:#eaf2fb;border-radius:8px;padding:14px;
                  margin-bottom:20px;font-size:13px;color:#1a5276;">
        <strong>How this works:</strong> A Random Forest model was trained on
        your historical drift records. It learned which early signals
        (dropping study time, quiz score trends, login patterns) predict
        future drift. These predictions let you intervene <em>before</em>
        a student reaches the alert threshold.
      </div>
      {cards_html}
    </div>"""

    return HTMLResponse(base_page("ML Predictions", body,
                                  username=get_username(user),
                                  full_name=get_full_name(user)))


# ══════════════════════════════════════════════════════════════════════════
# ROUTES — TEACHER DASHBOARD + ALL EXISTING ROUTES
# ══════════════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    user = require_login(request)
    if isinstance(user, RedirectResponse):
        return user

    course_filter = get_course_filter(user)
    username      = get_username(user)
    full_name     = get_full_name(user)

    db = get_db()
    try:
        data = load_dashboard_data(db, course_filter)
    finally:
        db.close()

    alerted = data["alerted"]
    watched = data["watched"]
    healthy = data["healthy"]

    course_label = (
        f" &nbsp;—&nbsp; {course_filter}" if course_filter != "all" else ""
    )

    alert_html = (
        "".join(student_card(s, r, "#e74c3c", "alert") for s, r in alerted)
        if alerted else
        '<p style="color:#27ae60;padding:8px 0;">No students above alert threshold.</p>'
    )
    watch_html = (
        "".join(student_card(s, r, "#e67e22", "watch") for s, r in watched)
        if watched else
        '<p style="color:#888;padding:8px 0;">No students on watch list.</p>'
    )
    healthy_html = "".join(
        f'<span class="pill">{s.name}</span>' for s, r in healthy
    )

    filter_bar = """
    <div class="section" style="padding:14px 20px;">
      <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;">
        <input type="text" id="searchInput"
               placeholder="Search by student name..."
               onkeyup="filterStudents()"
               style="flex:1;min-width:180px;margin-bottom:0;">
        <select id="courseFilter" onchange="filterStudents()">
          <option value="">All courses</option>
          <option value="data science">Data Science</option>
          <option value="machine learning">Machine Learning</option>
          <option value="web development">Web Development</option>
        </select>
        <select id="statusFilter" onchange="filterStudents()">
          <option value="">All statuses</option>
          <option value="alert">Alert</option>
          <option value="watch">Watch</option>
        </select>
      </div>
    </div>
    <script>
    function filterStudents() {
      const search = document.getElementById('searchInput').value.toLowerCase();
      const course = document.getElementById('courseFilter').value.toLowerCase();
      const status = document.getElementById('statusFilter').value.toLowerCase();
      document.querySelectorAll('.student-card').forEach(card => {
        const nameMatch   = (card.dataset.name   || '').includes(search);
        const courseMatch = !course || (card.dataset.course || '').includes(course);
        const statusMatch = !status || (card.dataset.status || '') === status;
        card.style.display = (nameMatch && courseMatch && statusMatch) ? '' : 'none';
      });
    }
    </script>"""

    body = f"""
    <h1>Behavior Drift Detection Dashboard{course_label}</h1>
    <p class="subtitle">Generated: {data['generated']} &nbsp;|&nbsp;
    {data['total']} students monitored</p>

    <div class="grid">
      <div class="card" style="border-top-color:#e74c3c;">
        <div class="n" style="color:#e74c3c;">{len(alerted)}</div>
        <div class="l">Need attention</div>
      </div>
      <div class="card" style="border-top-color:#e67e22;">
        <div class="n" style="color:#e67e22;">{len(watched)}</div>
        <div class="l">On watch list</div>
      </div>
      <div class="card" style="border-top-color:#27ae60;">
        <div class="n" style="color:#27ae60;">{len(healthy)}</div>
        <div class="l">Healthy</div>
      </div>
      <div class="card" style="border-top-color:#3498db;">
        <div class="n" style="color:#3498db;">{data['total']}</div>
        <div class="l">Total students</div>
      </div>
    </div>

    {filter_bar}

    <div class="section">
      <div class="section-head">
        <h2 style="margin:0;">Needs Immediate Attention</h2>
        <span class="badge" style="background:#fdecea;color:#e74c3c;">
          drift &gt; {ALERT_THRESHOLD}</span>
      </div>
      {alert_html}
    </div>

    <div class="section">
      <div class="section-head">
        <h2 style="margin:0;">Watch List</h2>
        <span class="badge" style="background:#fef5e7;color:#e67e22;">
          drift {WATCH_THRESHOLD} – {ALERT_THRESHOLD}</span>
      </div>
      {watch_html}
    </div>

    <div class="section">
      <h2>Healthy Students</h2>
      <div style="margin-top:10px;">{healthy_html}</div>
    </div>

    <div class="section">
      <h2>Actions</h2>
      <div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:8px;">
        <form action="/run" method="post">
          <button class="btn" style="background:#2980b9;" type="submit">
            Run detection now</button>
        </form>
        <a href="/predictions">
          <button class="btn" style="background:#8e44ad;" type="button">
            ML predictions</button>
        </a>
        <a href="/analytics">
          <button class="btn" style="background:#16a085;" type="button">
            Course analytics</button>
        </a>
        <a href="/report/pdf">
          <button class="btn" style="background:#c0392b;" type="button">
            Download PDF</button>
        </a>
        <a href="/upload">
          <button class="btn" style="background:#27ae60;" type="button">
            Upload data</button>
        </a>
      </div>
    </div>"""

    return HTMLResponse(base_page("Dashboard", body,
                                  username=username, full_name=full_name))


@app.get("/student/{student_id}", response_class=HTMLResponse)
def student_detail(student_id: int, request: Request):
    user = require_login(request)
    if isinstance(user, RedirectResponse):
        return user

    db = get_db()
    try:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return HTMLResponse("<h2>Student not found.</h2>", status_code=404)
        baseline = db.query(StudentBaseline).filter(
            StudentBaseline.student_id == student_id).first()
        cutoff = datetime.utcnow() - timedelta(days=14)
        activities = (
            db.query(DailyActivity)
            .filter(DailyActivity.student_id == student_id,
                    DailyActivity.date >= cutoff)
            .order_by(DailyActivity.date.desc()).all()
        )
        chart_cutoff = datetime.utcnow() - timedelta(days=30)
        drift_history = (
            db.query(DriftRecord)
            .filter(DriftRecord.student_id == student_id,
                    DriftRecord.date >= chart_cutoff)
            .order_by(DriftRecord.date).all()
        )
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        drift = db.query(DriftRecord).filter(
            DriftRecord.student_id == student_id,
            DriftRecord.date == today).first()
        notes = (
            db.query(TeacherNote)
            .filter(TeacherNote.student_id == student_id)
            .order_by(TeacherNote.created_at.desc()).all()
        )
    finally:
        db.close()

    bl_html = "<p style='color:#aaa;'>No baseline yet.</p>"
    if baseline:
        bl_html = f"""
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:14px 0;">
          <div class="card" style="border-top-color:#3498db;">
            <div class="n" style="font-size:24px;color:#3498db;">
              {baseline.avg_quiz_score:.1f}</div>
            <div class="l">Avg quiz score</div>
          </div>
          <div class="card" style="border-top-color:#3498db;">
            <div class="n" style="font-size:24px;color:#3498db;">
              {baseline.avg_session_minutes:.0f}m</div>
            <div class="l">Avg session time</div>
          </div>
          <div class="card" style="border-top-color:#3498db;">
            <div class="n" style="font-size:24px;color:#3498db;">
              {baseline.submission_rate * 100:.0f}%</div>
            <div class="l">Submission rate</div>
          </div>
        </div>"""

    drift_html = "<p style='color:#aaa;'>No drift record for today yet.</p>"
    if drift:
        color = ("#e74c3c" if drift.drift_score >= ALERT_THRESHOLD else
                 "#e67e22" if drift.drift_score >= WATCH_THRESHOLD else "#27ae60")
        drift_html = f"""
        <div style="display:inline-block;background:{color};color:white;
                    border-radius:8px;padding:10px 18px;font-size:20px;
                    font-weight:700;margin-bottom:14px;">
          Today's drift score: {drift.drift_score:.3f}
        </div>
        <p style="font-size:14px;color:#555;margin-top:8px;">
          <strong>Signals:</strong> {drift.notes or 'none'}</p>"""

    chart_labels = [d.date.strftime('%d %b') for d in drift_history]
    chart_scores = [round(d.drift_score, 3)   for d in drift_history]
    labels_js    = str(chart_labels).replace("'", '"')
    scores_js    = str(chart_scores)

    chart_html = f"""
    <canvas id="driftChart" style="max-height:220px;"></canvas>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <script>
      new Chart(document.getElementById('driftChart').getContext('2d'), {{
        type: 'line',
        data: {{
          labels: {labels_js},
          datasets: [{{
            data: {scores_js},
            borderColor: '#e74c3c',
            backgroundColor: 'rgba(231,76,60,0.08)',
            borderWidth: 2, pointRadius: 3, fill: true, tension: 0.3
          }}]
        }},
        options: {{
          responsive: true,
          plugins: {{ legend: {{ display: false }} }},
          scales: {{
            y: {{ min: 0, max: 1, ticks: {{ stepSize: 0.25 }},
                  grid: {{ color: '#f0f0f0' }} }},
            x: {{ grid: {{ display: false }} }}
          }}
        }}
      }});
    </script>
    <div style="font-size:12px;color:#888;margin-top:8px;">
      Alert threshold: {ALERT_THRESHOLD}</div>"""

    rows = ""
    for a in activities:
        score_str = f"{a.quiz_score:.1f}" if a.quiz_score is not None else "—"
        sub_color = "#27ae60" if a.submitted else "#e74c3c"
        rows += f"""
        <tr style="border-bottom:1px solid #f5f5f5;">
          <td style="padding:8px 6px;">{a.date.strftime('%d %b')}</td>
          <td style="padding:8px 6px;text-align:center;">{a.login_count}</td>
          <td style="padding:8px 6px;text-align:center;">{a.session_minutes:.0f}m</td>
          <td style="padding:8px 6px;text-align:center;">{score_str}</td>
          <td style="padding:8px 6px;text-align:center;
              color:{sub_color};font-weight:600;">
            {"Yes" if a.submitted else "No"}</td>
        </tr>"""

    existing_notes = ""
    if notes:
        for n in notes:
            existing_notes += f"""
            <div style="background:#f8f9fa;border-radius:6px;padding:12px;
                        margin-bottom:8px;border-left:3px solid #3498db;">
              <div style="font-size:13px;color:#333;">{n.note}</div>
              <div style="font-size:11px;color:#aaa;margin-top:4px;">
                {n.created_at.strftime('%d %b %Y, %H:%M')}</div>
            </div>"""
    else:
        existing_notes = '<p style="color:#aaa;font-size:13px;">No notes yet.</p>'

    body = f"""
    <div style="margin-bottom:10px;">
      <a href="/" style="color:#3498db;font-size:13px;">← Back</a></div>
    <h1>{student.name}</h1>
    <p class="subtitle">{student.course}</p>
    <div class="section"><h2>Today's drift</h2>{drift_html}</div>
    <div class="section"><h2>Drift trend — last 30 days</h2>{chart_html}</div>
    <div class="section"><h2>Baseline</h2>{bl_html}</div>
    <div class="section">
      <h2>Recent activity</h2>
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <thead><tr style="background:#f8f9fa;font-weight:600;">
          <th style="padding:10px 6px;text-align:left;">Date</th>
          <th style="padding:10px 6px;">Logins</th>
          <th style="padding:10px 6px;">Session</th>
          <th style="padding:10px 6px;">Score</th>
          <th style="padding:10px 6px;">Submitted</th>
        </tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    <div class="section">
      <h2>Teacher notes</h2>
      {existing_notes}
      <form action="/student/{student_id}/note" method="post" style="margin-top:10px;">
        <textarea name="note" rows="3" placeholder="Write a note..."
          style="width:100%;padding:10px;border:1px solid #ddd;border-radius:6px;
                 font-size:14px;font-family:inherit;resize:vertical;"></textarea>
        <button class="btn" style="background:#3498db;margin-top:8px;">
          Save note</button>
      </form>
    </div>"""

    return HTMLResponse(base_page(student.name, body,
                                  username=get_username(user),
                                  full_name=get_full_name(user)))


@app.post("/student/{student_id}/note")
def save_note(student_id: int, request: Request, note: str = Form(...)):
    user = require_login(request)
    if isinstance(user, RedirectResponse):
        return user
    if note.strip():
        db = get_db()
        try:
            db.add(TeacherNote(student_id=student_id, note=note.strip(),
                               created_at=datetime.utcnow()))
            db.commit()
        finally:
            db.close()
    return RedirectResponse(url=f"/student/{student_id}", status_code=303)


@app.get("/report/pdf")
def download_pdf(request: Request):
    user = require_login(request)
    if isinstance(user, RedirectResponse):
        return user
    course_filter = get_course_filter(user)
    db = get_db()
    try:
        data = load_dashboard_data(db, course_filter)
    finally:
        db.close()
    pdf_bytes = generate_pdf(data["alerted"], data["watched"], data["healthy"])
    filename  = f"drift_report_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/analytics", response_class=HTMLResponse)
def analytics(request: Request):
    user = require_login(request)
    if isinstance(user, RedirectResponse):
        return user
    course_filter = get_course_filter(user)
    db = get_db()
    try:
        data = load_dashboard_data(db, course_filter)
    finally:
        db.close()

    all_pairs = data["alerted"] + data["watched"] + data["healthy"]
    courses: dict = {}
    for s, r in all_pairs:
        c = s.course
        if c not in courses:
            courses[c] = {"alert": 0, "watch": 0, "healthy": 0,
                          "scores": [], "students": []}
        if r.drift_score >= ALERT_THRESHOLD:
            courses[c]["alert"] += 1
        elif r.drift_score >= WATCH_THRESHOLD:
            courses[c]["watch"] += 1
        else:
            courses[c]["healthy"] += 1
        courses[c]["scores"].append(r.drift_score)
        courses[c]["students"].append((s, r))

    course_cards = ""
    for name, stats in sorted(courses.items()):
        total     = stats["alert"] + stats["watch"] + stats["healthy"]
        avg_drift = sum(stats["scores"]) / len(stats["scores"]) if stats["scores"] else 0
        border    = ("#e74c3c" if stats["alert"] > 0 else
                     "#e67e22" if stats["watch"] > 0 else "#27ae60")
        student_rows = ""
        for s, r in sorted(stats["students"],
                            key=lambda x: x[1].drift_score, reverse=True):
            color = ("#e74c3c" if r.drift_score >= ALERT_THRESHOLD else
                     "#e67e22" if r.drift_score >= WATCH_THRESHOLD else "#27ae60")
            student_rows += f"""
            <tr style="border-bottom:1px solid #f5f5f5;">
              <td style="padding:7px 6px;">
                <a href="/student/{s.id}" style="color:#222;text-decoration:none;">
                  {s.name}</a></td>
              <td style="padding:7px 6px;text-align:center;
                         color:{color};font-weight:600;">{r.drift_score:.2f}</td>
              <td style="padding:7px 6px;font-size:12px;color:#888;">
                {r.notes or 'ok'}</td>
            </tr>"""
        course_cards += f"""
        <div style="background:white;border:1px solid {border};
                    border-left:5px solid {border};border-radius:8px;
                    padding:20px;margin-bottom:18px;">
          <div style="display:flex;justify-content:space-between;
                      align-items:center;margin-bottom:14px;">
            <h2 style="margin:0;">{name}</h2>
            <span style="font-size:13px;color:#888;">{total} students</span>
          </div>
          <div style="display:grid;grid-template-columns:repeat(4,1fr);
                      gap:10px;margin-bottom:16px;">
            <div style="text-align:center;background:#fdecea;border-radius:8px;padding:10px;">
              <div style="font-size:22px;font-weight:700;color:#e74c3c;">
                {stats['alert']}</div>
              <div style="font-size:12px;color:#888;">Alert</div>
            </div>
            <div style="text-align:center;background:#fef5e7;border-radius:8px;padding:10px;">
              <div style="font-size:22px;font-weight:700;color:#e67e22;">
                {stats['watch']}</div>
              <div style="font-size:12px;color:#888;">Watch</div>
            </div>
            <div style="text-align:center;background:#eafaf1;border-radius:8px;padding:10px;">
              <div style="font-size:22px;font-weight:700;color:#27ae60;">
                {stats['healthy']}</div>
              <div style="font-size:12px;color:#888;">Healthy</div>
            </div>
            <div style="text-align:center;background:#eaf2fb;border-radius:8px;padding:10px;">
              <div style="font-size:22px;font-weight:700;color:#2980b9;">
                {avg_drift:.2f}</div>
              <div style="font-size:12px;color:#888;">Avg drift</div>
            </div>
          </div>
          <table style="width:100%;border-collapse:collapse;font-size:13px;">
            <thead><tr style="background:#f8f9fa;">
              <th style="padding:7px 6px;text-align:left;">Student</th>
              <th style="padding:7px 6px;text-align:center;">Drift</th>
              <th style="padding:7px 6px;text-align:left;">Signals</th>
            </tr></thead>
            <tbody>{student_rows}</tbody>
          </table>
        </div>"""

    body = f"""
    <h1>Course Analytics</h1>
    <p class="subtitle">Drift breakdown by course — {data['generated']}</p>
    {course_cards}"""
    return HTMLResponse(base_page("Analytics", body,
                                  username=get_username(user),
                                  full_name=get_full_name(user)))


@app.get("/upload", response_class=HTMLResponse)
def upload_page(request: Request, msg: str = "", error: str = ""):
    user = require_login(request)
    if isinstance(user, RedirectResponse):
        return user
    feedback = ""
    if msg:
        feedback = (f'<div style="background:#eafaf1;border:1px solid #a9dfbf;'
                    f'border-radius:8px;padding:14px;margin-bottom:16px;'
                    f'font-size:14px;color:#1e8449;">{msg}</div>')
    if error:
        feedback = (f'<div style="background:#fdecea;border:1px solid #f5c6cb;'
                    f'border-radius:8px;padding:14px;margin-bottom:16px;'
                    f'font-size:14px;color:#c0392b;">{error}</div>')
    body = f"""
    <h1>Upload Student Data</h1>
    <p class="subtitle">Upload a CSV or Excel file.</p>
    {feedback}
    <div class="section">
      <h2>Upload file</h2>
      <form action="/upload" method="post" enctype="multipart/form-data">
        <input type="file" name="file" accept=".csv,.xlsx,.xls"
               style="display:block;margin-bottom:16px;font-size:14px;">
        <button class="btn" style="background:#27ae60;" type="submit">
          Upload and import</button>
      </form>
    </div>"""
    return HTMLResponse(base_page("Upload", body,
                                  username=get_username(user),
                                  full_name=get_full_name(user)))


@app.post("/upload")
async def upload_submit(request: Request, file: UploadFile = File(...)):
    user = require_login(request)
    if isinstance(user, RedirectResponse):
        return user
    file_bytes = await file.read()
    db = get_db()
    try:
        result = import_from_bytes(file_bytes, file.filename, db)
    finally:
        db.close()
    if not result.get("success"):
        return RedirectResponse(
            url=f"/upload?error=Import+failed:+{result.get('error','')}",
            status_code=302)
    msg = (f"Success! Students: {result['students_created']} | "
           f"Rows: {result['rows_imported']} | Skipped: {result['rows_skipped']}")
    return RedirectResponse(url=f"/upload?msg={msg.replace(' ', '+')}", status_code=302)


@app.post("/run")
def run_detection(request: Request):
    user = require_login(request)
    if isinstance(user, RedirectResponse):
        return user
    db = get_db()
    try:
        calculate_all_baselines(db)
        run_drift_detection(db)
    finally:
        db.close()
    return RedirectResponse(url="/", status_code=303)


@app.get("/api/drift", response_class=JSONResponse)
def api_drift(request: Request):
    user = require_login(request)
    if isinstance(user, RedirectResponse):
        return user
    course_filter = get_course_filter(user)
    db = get_db()
    try:
        data = load_dashboard_data(db, course_filter)
    finally:
        db.close()
    result = []
    for category, pairs in [("alert", data["alerted"]),
                             ("watch", data["watched"]),
                             ("healthy", data["healthy"])]:
        for s, r in pairs:
            result.append({
                "student_id": s.id, "name": s.name, "course": s.course,
                "status": category, "drift_score": r.drift_score,
                "score_drift": r.score_drift, "session_drift": r.session_drift,
                "submission_drift": r.submission_drift, "notes": r.notes,
            })
    return {"generated": data["generated"], "students": result}