"""
Entry point for the nudge workflow (.github/workflows/nudge.yml).
Runs every 30 mins. Sends a Telegram message if the daily post target
hasn't been met and it's within the active window (8am-9pm IST).
"""
from datetime import datetime, timezone, timedelta
from scripts.db import get_today_post_count
from scripts.telegram_reminder import send_message

DAILY_TARGET = 2
IST = timezone(timedelta(hours=5, minutes=30))


def run():
    now_ist = datetime.now(IST)
    hour = now_ist.hour

    # Only nudge between 8am and 9pm IST
    if hour < 8 or hour >= 21:
        print(f"Outside nudge window ({hour}:xx IST). Skipping.")
        return

    count = get_today_post_count()
    remaining = DAILY_TARGET - count

    if remaining <= 0:
        print(f"Daily target met ({count}/{DAILY_TARGET}). No nudge needed.")
        return

    send_message(
        f"📹 <b>WYRD VIRAL reminder!</b>\n\n"
        f"You've posted <b>{count}/{DAILY_TARGET}</b> videos today.\n"
        f"<b>{remaining}</b> more to go — send a video to this bot to post it! 🚀"
    )
    print(f"Nudge sent. {count}/{DAILY_TARGET} done today.")


if __name__ == "__main__":
    run()
