"""
======================
PURPOSE: Read today's drift records and produce two outputs:
         1. A console report printed in the terminal
         2. An HTML dashboard file saved as dashboard.html

The HTML file can be opened directly in any browser.
No web server or internet connection needed.
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from models.student import Student
from models.activity import DriftRecord, StudentBaseline


ALERT_THRESHOLD = 0.35   
WATCH_THRESHOLD = 0.20    


DASHBOARD_FILE = "dashboard.html"


# ── Helper ──────────────────────────────────────────────────────────────

def get_todays_drift_records(db: Session) -> list:
    """
    Fetches all drift records saved today.
    Returns a list of (student, drift_record) tuples sorted by drift score
    highest first — most urgent students appear at the top.
    """
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    records = (
        db.query(DriftRecord)
        .filter(DriftRecord.date == today)
        .order_by(DriftRecord.drift_score.desc())   
        .all()
    )

    students = {s.id: s for s in db.query(Student).all()}

    pairs = []
    for record in records:
        student = students.get(record.student_id)
        if student:
            pairs.append((student, record))

    return pairs


def get_intervention_tip(record: DriftRecord) -> str:
    
    signals = {
        "score":      record.score_drift,
        "session":    record.session_drift,
        "submission": record.submission_drift,
    }
    worst = max(signals, key=signals.get)

    tips = {
        "score": (
            "Quiz scores have dropped significantly. "
            "Consider a 1-on-1 check-in to identify concept gaps. "
            "Share revision resources for recent topics."
        ),
        "session": (
            "Study time has dropped sharply. "
            "Send an encouraging message asking if everything is okay. "
            "This often signals personal or motivational issues outside academics."
        ),
        "submission": (
            "Assignments are being missed. "
            "Check if deadlines are clear and workload is manageable. "
            "Offer an extension if needed — re-engagement matters more than penalties."
        ),
    }
    return tips[worst]


# ── Console report ──────────────────────────────────────────────────────

def print_alert_report(db: Session) -> None:
    """
    Prints a formatted alert report in the terminal.
    Shows alerted students first, then watch-list students.
    """
    pairs = get_todays_drift_records(db)

    alerted = [(s, r) for s, r in pairs if r.drift_score >= ALERT_THRESHOLD]
    watched = [(s, r) for s, r in pairs if WATCH_THRESHOLD <= r.drift_score < ALERT_THRESHOLD]
    healthy = [(s, r) for s, r in pairs if r.drift_score < WATCH_THRESHOLD]

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    print(f"\n{'=' * 60}")
    print(f"  BEHAVIOR DRIFT ALERT REPORT")
    print(f"  Generated: {now}")
    print(f"{'=' * 60}")

    # ── Alert section ────────────────────────────────────────────────
    print(f"\n  *** NEEDS IMMEDIATE ATTENTION ({len(alerted)} students) ***\n")

    if alerted:
        for student, record in alerted:
            print(f"  Student  : {student.name}")
            print(f"  Course   : {student.course}")
            print(f"  Drift    : {record.drift_score:.3f}  "
                  f"[score:{record.score_drift:.2f} "
                  f"session:{record.session_drift:.2f} "
                  f"submit:{record.submission_drift:.2f}]")
            print(f"  Signals  : {record.notes}")
            print(f"  Tip      : {get_intervention_tip(record)}")
            print(f"  {'-' * 55}")
    else:
        print(f"  No students currently above alert threshold.\n")

    # ── Watch section ────────────────────────────────────────────────
    print(f"\n  WATCH LIST ({len(watched)} students — monitor closely)\n")

    if watched:
        for student, record in watched:
            print(f"  {student.name:<22}  drift: {record.drift_score:.3f}  — {record.notes}")
    else:
        print(f"  No students on watch list.\n")

    # ── Healthy section ──────────────────────────────────────────────
    print(f"\n  HEALTHY ({len(healthy)} students — no action needed)")
    names = [s.name for s, r in healthy]
    print(f"  {', '.join(names)}\n")
    print(f"{'=' * 60}\n")


# ── HTML dashboard ──────────────────────────────────────────────────────

def generate_dashboard(db: Session) -> None:
    """
    Generates a complete HTML dashboard and saves it as dashboard.html.
    Open this file in any browser — no server needed.

    The HTML uses plain CSS (no libraries) so it works offline.
    """
    pairs    = get_todays_drift_records(db)
    alerted  = [(s, r) for s, r in pairs if r.drift_score >= ALERT_THRESHOLD]
    watched  = [(s, r) for s, r in pairs if WATCH_THRESHOLD <= r.drift_score < ALERT_THRESHOLD]
    healthy  = [(s, r) for s, r in pairs if r.drift_score < WATCH_THRESHOLD]
    now      = datetime.utcnow().strftime("%d %B %Y, %H:%M UTC")

    # ── Build student card HTML ──────────────────────────────────────

    def drift_bar(value: float, color: str) -> str:
        """Returns an HTML progress bar showing drift signal strength."""
        pct = round(value * 100)
        return (
            f'<div style="background:#eee;border-radius:4px;height:10px;margin:3px 0;">'
            f'<div style="width:{pct}%;background:{color};'
            f'height:10px;border-radius:4px;"></div></div>'
        )

    def student_card(student: Student, record: DriftRecord, card_color: str) -> str:
        """Builds one student card as an HTML string."""
        tip = get_intervention_tip(record)

        score_bar   = drift_bar(record.score_drift,      "#e74c3c")
        session_bar = drift_bar(record.session_drift,    "#e67e22")
        submit_bar  = drift_bar(record.submission_drift, "#9b59b6")

        return f"""
        <div style="background:white;border:1px solid {card_color};
                    border-left:5px solid {card_color};border-radius:8px;
                    padding:18px;margin-bottom:14px;">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <div>
              <strong style="font-size:16px;">{student.name}</strong>
              <span style="color:#666;font-size:13px;margin-left:10px;">{student.course}</span>
            </div>
            <div style="font-size:22px;font-weight:bold;color:{card_color};">
              {record.drift_score:.2f}
            </div>
          </div>

          <div style="margin:12px 0;font-size:13px;color:#444;">
            <strong>Signals:</strong> {record.notes or 'within normal range'}
          </div>

          <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin:10px 0;">
            <div>
              <div style="font-size:12px;color:#666;">Quiz score drift</div>
              {score_bar}
              <div style="font-size:12px;text-align:right;">{record.score_drift:.2f}</div>
            </div>
            <div>
              <div style="font-size:12px;color:#666;">Session drift</div>
              {session_bar}
              <div style="font-size:12px;text-align:right;">{record.session_drift:.2f}</div>
            </div>
            <div>
              <div style="font-size:12px;color:#666;">Submission drift</div>
              {submit_bar}
              <div style="font-size:12px;text-align:right;">{record.submission_drift:.2f}</div>
            </div>
          </div>

          <div style="background:#f8f9fa;border-radius:6px;padding:10px;
                      font-size:13px;color:#333;margin-top:8px;">
            <strong>Recommended action:</strong> {tip}
          </div>
        </div>
        """

    # ── Build alert cards ────────────────────────────────────────────
    alert_cards = ""
    if alerted:
        for s, r in alerted:
            alert_cards += student_card(s, r, "#e74c3c")
    else:
        alert_cards = '<p style="color:#27ae60;">No students currently above alert threshold.</p>'

    # ── Build watch cards ────────────────────────────────────────────
    watch_cards = ""
    if watched:
        for s, r in watched:
            watch_cards += student_card(s, r, "#e67e22")
    else:
        watch_cards = '<p style="color:#27ae60;">No students on watch list.</p>'

    # ── Build healthy list ───────────────────────────────────────────
    healthy_pills = ""
    for s, r in healthy:
        healthy_pills += (
            f'<span style="display:inline-block;background:#eafaf1;'
            f'color:#1e8449;border:1px solid #a9dfbf;border-radius:20px;'
            f'padding:4px 12px;margin:4px;font-size:13px;">'
            f'{s.name}</span>'
        )

    # ── Summary numbers ──────────────────────────────────────────────
    total    = len(pairs)
    n_alert  = len(alerted)
    n_watch  = len(watched)
    n_health = len(healthy)

    # ── Full HTML page ───────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Behavior Drift Dashboard</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #f4f6f9;
      color: #222;
      padding: 24px;
    }}
    .container {{ max-width: 960px; margin: 0 auto; }}
    h1 {{ font-size: 24px; font-weight: 600; margin-bottom: 4px; }}
    h2 {{ font-size: 17px; font-weight: 600; margin: 28px 0 14px; }}
    .subtitle {{ color: #666; font-size: 14px; margin-bottom: 24px; }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 14px;
      margin-bottom: 32px;
    }}
    .summary-card {{
      background: white;
      border-radius: 10px;
      padding: 18px;
      text-align: center;
      border-top: 4px solid #ddd;
    }}
    .summary-card .number {{ font-size: 36px; font-weight: 700; }}
    .summary-card .label  {{ font-size: 13px; color: #666; margin-top: 4px; }}
    .section {{
      background: white;
      border-radius: 10px;
      padding: 20px;
      margin-bottom: 20px;
    }}
    .section-header {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 16px;
      padding-bottom: 10px;
      border-bottom: 1px solid #eee;
    }}
    .badge {{
      display: inline-block;
      border-radius: 20px;
      padding: 3px 10px;
      font-size: 12px;
      font-weight: 600;
    }}
    footer {{
      text-align: center;
      font-size: 12px;
      color: #aaa;
      margin-top: 32px;
    }}
  </style>
</head>
<body>
<div class="container">

  <h1>Behavior Drift Detection Dashboard</h1>
  <p class="subtitle">Generated on {now} &nbsp;|&nbsp; Monitoring {total} students</p>

  <!-- Summary cards -->
  <div class="summary-grid">
    <div class="summary-card" style="border-top-color:#e74c3c;">
      <div class="number" style="color:#e74c3c;">{n_alert}</div>
      <div class="label">Need attention</div>
    </div>
    <div class="summary-card" style="border-top-color:#e67e22;">
      <div class="number" style="color:#e67e22;">{n_watch}</div>
      <div class="label">On watch list</div>
    </div>
    <div class="summary-card" style="border-top-color:#27ae60;">
      <div class="number" style="color:#27ae60;">{n_health}</div>
      <div class="label">Healthy</div>
    </div>
    <div class="summary-card" style="border-top-color:#3498db;">
      <div class="number" style="color:#3498db;">{total}</div>
      <div class="label">Total students</div>
    </div>
  </div>

  <!-- Alert section -->
  <div class="section">
    <div class="section-header">
      <h2 style="margin:0;">Needs Immediate Attention</h2>
      <span class="badge" style="background:#fdecea;color:#e74c3c;">
        drift &gt; {ALERT_THRESHOLD}
      </span>
    </div>
    {alert_cards}
  </div>

  <!-- Watch section -->
  <div class="section">
    <div class="section-header">
      <h2 style="margin:0;">Watch List</h2>
      <span class="badge" style="background:#fef5e7;color:#e67e22;">
        drift {WATCH_THRESHOLD} – {ALERT_THRESHOLD}
      </span>
    </div>
    {watch_cards}
  </div>

  <!-- Healthy section -->
  <div class="section">
    <h2>Healthy Students</h2>
    <div style="margin-top:10px;">{healthy_pills}</div>
  </div>

  <footer>
    Behavior Drift Detection System &nbsp;|&nbsp;
    Scores range 0.00 (no drift) to 1.00 (maximum drift) &nbsp;|&nbsp;
    Alert threshold: {ALERT_THRESHOLD}
  </footer>

</div>
</body>
</html>"""

    # Write the file to disk
    with open(DASHBOARD_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  Dashboard saved → open '{DASHBOARD_FILE}' in your browser.")


# ── Main function ────────────────────────────────────────────────────────

def run_alert_engine(db: Session) -> None:
    """
    Runs both outputs: console report + HTML dashboard.
    Called from main.py.
    """
    print_alert_report(db)
    generate_dashboard(db)