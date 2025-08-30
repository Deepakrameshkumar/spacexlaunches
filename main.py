import requests
from datetime import datetime
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.base import JobLookupError
from telegram import Update
from telegram.ext import  CommandHandler,  ContextTypes, ApplicationBuilder
from datetime import timezone
from datetime import timedelta
import os
import json
# Load environment variables
from dotenv import load_dotenv
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
chat_id = int(os.getenv("TELEGRAM_CHAT_ID", "0"))  # Default to 0 if not set


scheduler = BackgroundScheduler()

def fetch_upcoming_launches(limit=10):
    print("Fetching upcoming launches...")
    url = f"https://ll.thespacedevs.com/2.2.0/launch/upcoming/?search=spacex&limit={limit}"
    response = requests.get(url)

    if response.status_code == 429:
        wait_time = int(response.headers.get("Retry-After", 60))
        print(f"Rate limited. Using cached data from 'json_dump.json'. Retry after {wait_time} seconds.")

        if os.path.exists("json_dump.json"):
            with open("json_dump.json", "r") as f:
                data = json.load(f)
        else:
            print("No cached file found. Returning empty list.")
            return []
    elif response.status_code == 200:
        data = response.json()
        with open("json_dump.json", "w") as f:
            json.dump(data, f, indent=2)
    else:
        print(f"Unexpected error: {response.status_code}")
        return []

    if 'results' not in data:
        print("Malformed response: 'results' key missing.")
        return []

    now_utc = datetime.now(timezone.utc)
    launches = [
        l for l in data['results']
        if datetime.strptime(l['net'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) > now_utc
    ]

    launches.sort(key=lambda x: x['net'])
    ist = pytz.timezone('Asia/Kolkata')
    for launch in launches:
        utc_dt = datetime.strptime(launch['net'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        launch['date_ist'] = utc_dt.astimezone(ist)
        vid_url = launch.get('vidURLs', [])
        launch['webcast'] = vid_url[0] if vid_url else 'N/A'

    return launches[:limit]


def fetch_json_data(limit=10):

    if os.path.exists("json_dump.json"):
        with open("json_dump.json", "r") as f:
            data = json.load(f)
    else:
        print("No cached file found. Returning empty list.")
        return []

    if 'results' not in data:
        print("Malformed response: 'results' key missing.")
        return []

    now_utc = datetime.now(timezone.utc)
    launches = [
        l for l in data['results']
        if datetime.strptime(l['net'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) > now_utc
    ]

    launches.sort(key=lambda x: x['net'])
    ist = pytz.timezone('Asia/Kolkata')
    for launch in launches:
        utc_dt = datetime.strptime(launch['net'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        launch['date_ist'] = utc_dt.astimezone(ist)
        vid_url = launch.get('vidURLs', [])
        launch['webcast'] = vid_url[0] if vid_url else 'N/A'

    return launches[:limit]


def describe_relative_date(dt_ist):
    now = datetime.now(pytz.timezone('Asia/Kolkata')).replace(second=0, microsecond=0)
    dt_ist = dt_ist.replace(second=0, microsecond=0)

    delta_days = (dt_ist.date() - now.date()).days
    weekday_name = dt_ist.strftime('%A')  # e.g., 'Thursday'
    time_str = dt_ist.strftime('%I:%M %p').lstrip('0')  # Windows-safe

    if delta_days == 0:
        return f"Today {time_str}"
    elif delta_days == 1:
        return f"Tomorrow {time_str}"
    elif 2 <= delta_days <= 6:
        return f"This {weekday_name} {time_str}"
    elif delta_days > 6:
        return f"Next {weekday_name} {time_str}"
    else:
        return dt_ist.strftime('%d %b %Y %I:%M %p')


def schedule_reminder(launch, telegram_chat_id, bot):
    job_id = f"reminder_{launch['id']}"
    reminder_time = launch['date_ist'] - timedelta(minutes=30)

    # Check if a job with the same ID already exists
    existing_job = scheduler.get_job(job_id)
    if existing_job is not None:
        print(f"Job with ID {job_id} already exists. Skipping or updating...")
        # Optional: Update the existing job if needed (e.g., if the launch time changed)
        scheduler.reschedule_job(job_id, trigger='date', run_date=reminder_time)
        return

    # Schedule a new job if none exists
    scheduler.add_job(
        send_launch_reminder,
        'date',
        run_date=reminder_time,
        args=[launch, telegram_chat_id, bot],
        id=job_id
    )
    print(f"Scheduled reminder for launch {launch['id']} at {reminder_time}")

def send_launch_reminder(launch, chat_id, bot):
    name = launch['name']
    time_str = launch['date_ist'].strftime('%Y-%m-%d %H:%M IST')
    time_str_hr = describe_relative_date(launch['date_ist'])
    webcast = launch.get('webcast', 'N/A')
    message = f"🚀 Upcoming Launch: {name}\n🕒 Time: {time_str}\n🕒 Time: {time_str_hr}\n📺 Watch: {webcast}"
    bot.send_message(chat_id=chat_id, text=message)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    print(f"Captured Chat ID: {chat_id}")
    #save chat_id to a storage
    os.environ['TELEGRAM_CHAT_ID'] = str(chat_id)

    await update.message.reply_text("✅ Chat ID registered. You're all set!")

async def launches_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    launches = fetch_upcoming_launches(limit=10)
    messages = []
    for launch in launches:
        name = launch['name']
        time_str = launch['date_ist'].strftime('%Y-%m-%d %H:%M IST')
        # human readable string 
        time_str_hr = describe_relative_date(launch['date_ist'])
        
        webcast = launch.get('webcast', 'N/A')
        if webcast != 'N/A':
            messages.append(f"🚀 {name}\n🕒 {time_str}\n🕒 {time_str_hr}\n📺 {webcast}")
        else:
            messages.append(f"🚀 {name}\n🕒 {time_str}\n🕒 {time_str_hr}")
    if messages:
        await update.message.reply_text("\n\n".join(messages))
    else:
        await update.message.reply_text("No upcoming launches found.")

def setup_bot():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("launches", launches_command))
    return app

def clear_old_jobs():
    for job in scheduler.get_jobs():
        if job.next_run_time < datetime.now(timezone.utc):
            scheduler.remove_job(job.id)
            print(f"Removed outdated job {job.id}")

if __name__ == "__main__":
    testing = 1
    
    if testing == 1:
        launches = fetch_json_data(limit=10)
    else:
        launches = fetch_upcoming_launches(limit=10)

    telegram_app = setup_bot()
    
    # Optional: Clear outdated jobs
    clear_old_jobs()
    
    for launch in launches:
        schedule_reminder(launch, chat_id, telegram_app.bot)

    scheduler.start()
    
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.run_polling()