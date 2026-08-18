"""
PURPOSE: Send a Telegram message to the teacher every morning
         listing students who are on alert.

SETUP (one time, takes 2 minutes):
  1. Open Telegram and search for @BotFather
  2. Send /newbot and follow the prompts
  3. Copy the token BotFather gives you → paste into BOT_TOKEN below
  4. Search for @userinfobot in Telegram, send it any message
  5. It replies with your Chat ID → paste into CHAT_ID below
  6. Set TELEGRAM_ENABLED = True

HOW IT WORKS:
  Telegram has a free HTTP API. We send a POST request to their
  server with our bot token, target chat ID, and the message text.
  No installation beyond 'requests' is needed.
"""

import requests
from datetime import datetime

# ── Configuration ────────────────────────────────────────────────────────
BOT_TOKEN        = "8455132154:AAGk0scvZDDELvVM-3CbJLoZS8Q"    
CHAT_ID          = "7093552774"      
TELEGRAM_ENABLED = True                    #


def send_telegram_message(text: str) -> bool:
    if not TELEGRAM_ENABLED:
        print("  [Telegram] Disabled — fill in BOT_TOKEN and CHAT_ID to activate.")
        return False

    url  = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id":    CHAT_ID,
        "text":       text,
        "parse_mode": "HTML",
    }

    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            print("  [Telegram] Message sent successfully.")
            return True
        else:
            print(f"  [Telegram] Failed: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"  [Telegram] Network error: {e}")
        return False


def send_daily_alert(alerted: list, watched: list) -> None:
    
    today = datetime.utcnow().strftime("%d %B %Y")

    if not alerted and not watched:
        message = (
            f"<b>Drift Report — {today}</b>\n\n"
            f"All students are healthy today. No action needed."
        )
        send_telegram_message(message)
        return

    lines = [f"<b>Drift Alert Report — {today}</b>\n"]

    if alerted:
        lines.append(f"<b>NEEDS ATTENTION ({len(alerted)} students):</b>")
        for student, record in alerted:
            lines.append(
                f"  • {student.name} ({student.course})"
                f" — drift: <b>{record.drift_score:.2f}</b>"
                f" | {record.notes or 'signals detected'}"
            )

    if watched:
        lines.append(f"\n<b>WATCH LIST ({len(watched)} students):</b>")
        for student, record in watched:
            lines.append(
                f"  • {student.name} ({student.course})"
                f" — drift: {record.drift_score:.2f}"
            )

    lines.append("\nLog in to the dashboard for full details.")
    send_telegram_message("\n".join(lines))