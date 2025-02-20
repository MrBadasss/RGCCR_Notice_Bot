import os
import smtplib
import requests
from bs4 import BeautifulSoup
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Email Configuration
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
EMAIL_SENDER_NAME = "RGCCR Notice Bot"

NOTICE_URL = "https://rgccr.edu.bd/notice-board"  # Change if needed
CACHE_FILE = "data/previous_notices.txt"

def fetch_notices():
    """Fetches the latest notices from the website."""
    try:
        response = requests.get(NOTICE_URL, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        notices = soup.select(".notice-item")  # Modify according to actual structure

        extracted_notices = []
        for notice in notices:
            title = notice.select_one(".title").text.strip()
            date = notice.select_one(".date").text.strip()
            link = notice.a["href"] if notice.a else "No link"
            extracted_notices.append(f"{date} - {title} - {link}")

        return extracted_notices
    except Exception as e:
        log_error(f"Failed to fetch notices: {e}")
        return []

def read_cached_notices():
    """Reads the cached notices from the file."""
    if not os.path.exists(CACHE_FILE):
        return []
    with open(CACHE_FILE, "r", encoding="utf-8") as file:
        return file.read().splitlines()

def write_cache(notices):
    """Writes the latest notices to the cache file."""
    with open(CACHE_FILE, "w", encoding="utf-8") as file:
        file.write("\n".join(notices))

def send_email(subject, body):
    """Sends an email notification."""
    try:
        msg = MIMEMultipart()
        msg["From"] = f"{EMAIL_SENDER_NAME} <{EMAIL_SENDER}>"  # FIXED: Added sender name
        msg["To"] = EMAIL_RECEIVER
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)

        print("✅ Email sent successfully!")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

def log_error(error_message):
    """Logs an error and sends an email."""
    print(f"❌ Error: {error_message}")
    send_email("RGCCR Notice Check Error", f"An error occurred:\n{error_message}")

def main():
    """Main script execution."""
    print("🔄 Checking for new notices...")
    new_notices = fetch_notices()
    cached_notices = read_cached_notices()

    if not new_notices:
        log_error("No notices found on the website.")
        return

    if new_notices != cached_notices:
        print("✅ New notices found!")
        write_cache(new_notices)

        notice_list = "\n".join(new_notices)
        send_email("📢 RGCCR Notice Update", f"New notices detected:\n\n{notice_list}")
    else:
        print("✅ No new notices detected.")

if __name__ == "__main__":
    main()
