"""
utils/emailer.py
=================
PURPOSE: Send an email to the teacher when a student crosses
         the alert threshold.

HOW IT WORKS:
  Uses Python's built-in smtplib library — no installation needed.
  We connect to Gmail's SMTP server and send the email from there.

SETUP REQUIRED (one time only):
  1. Use a Gmail account as the SENDER
  2. Go to: myaccount.google.com → Security → 2-Step Verification → ON
  3. Then go to: myaccount.google.com → Security → App Passwords
  4. Create an app password for "Mail"
  5. Copy that 16-character password into SENDER_APP_PASSWORD below

WHY APP PASSWORD?
  Gmail blocks normal password login from scripts for security.
  An App Password is a special one-time password just for this script.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# ── Configuration — fill these in ──────────────────────────────────────
SENDER_EMAIL       = "your_gmail@gmail.com"     # Gmail you send FROM
SENDER_APP_PASSWORD = "xxxx xxxx xxxx xxxx"     # 16-char App Password
TEACHER_EMAIL      = "teacher@school.edu"        # Email to send alerts TO

# Set this to False to disable emails without deleting the code
EMAIL_ENABLED = False   # Change to True once you fill in credentials above


def send_alert_email(alerted_students: list) -> bool:
    """
    Sends one email listing all students currently on alert.
    alerted_students: list of (Student, DriftRecord) tuples.
    Returns True if sent successfully, False if failed.
    """
    if not EMAIL_ENABLED:
        print("  [Email] Email disabled — set EMAIL_ENABLED = True to activate.")
        return False

    if not alerted_students:
        print("  [Email] No alerts to send.")
        return False

    # ── Build the email content ──────────────────────────────────────
    today = datetime.utcnow().strftime("%d %B %Y")

    # Plain text version (for email clients that don't support HTML)
    text_lines = [f"Drift Alert Report — {today}\n"]
    for student, record in alerted_students:
        text_lines.append(
            f"- {student.name} ({student.course}): "
            f"drift score {record.drift_score:.2f} — {record.notes}"
        )
    text_body = "\n".join(text_lines)

    # HTML version (nicely formatted)
    rows = ""
    for student, record in alerted_students:
        color = "#e74c3c"
        rows += f"""
        <tr>
          <td style="padding:10px;border-bottom:1px solid #eee;">
            <strong>{student.name}</strong><br>
            <span style="color:#888;font-size:12px;">{student.course}</span>
          </td>
          <td style="padding:10px;border-bottom:1px solid #eee;
                     color:{color};font-weight:bold;text-align:center;">
            {record.drift_score:.2f}
          </td>
          <td style="padding:10px;border-bottom:1px solid #eee;
                     font-size:13px;color:#555;">
            {record.notes or 'signals detected'}
          </td>
        </tr>"""

    html_body = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:0 auto;">
      <div style="background:#2c3e50;padding:20px;border-radius:8px 8px 0 0;">
        <h2 style="color:white;margin:0;">Drift Alert — {today}</h2>
        <p style="color:#bdc3c7;margin:4px 0 0;font-size:13px;">
          Behavior Drift Detection System
        </p>
      </div>
      <div style="background:white;padding:20px;border:1px solid #eee;">
        <p style="color:#333;margin-bottom:16px;">
          The following students have crossed the alert threshold
          and may need your attention today:
        </p>
        <table style="width:100%;border-collapse:collapse;">
          <thead>
            <tr style="background:#f8f9fa;">
              <th style="padding:10px;text-align:left;">Student</th>
              <th style="padding:10px;">Drift Score</th>
              <th style="padding:10px;text-align:left;">Signals</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
        <p style="margin-top:20px;font-size:13px;color:#888;">
          Log in to view full details and recommended actions.
        </p>
      </div>
    </div>"""

    # ── Build and send the email ─────────────────────────────────────
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[Drift Alert] {len(alerted_students)} student(s) need attention — {today}"
        msg["From"]    = SENDER_EMAIL
        msg["To"]      = TEACHER_EMAIL

        # Attach both plain text and HTML — email client picks the best one
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        # Connect to Gmail SMTP server and send
        # Port 587 = TLS encryption — always use this, never port 25
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()                                  # Encrypt the connection
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)   # Login with app password
            server.sendmail(SENDER_EMAIL, TEACHER_EMAIL, msg.as_string())

        print(f"  [Email] Alert sent to {TEACHER_EMAIL} — {len(alerted_students)} students.")
        return True

    except Exception as e:
        print(f"  [Email] Failed to send: {e}")
        return False