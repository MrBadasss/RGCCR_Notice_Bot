import os
import smtplib
import requests
import asyncio
import logging
from bs4 import BeautifulSoup
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
from aiosmtplib import SMTP

# Load environment variables
load_dotenv()

# Email & Telegram Configuration
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVERS = os.getenv("EMAIL_RECEIVERS").split(",")  # Multiple emails
EMAIL_SENDER_NAME = "RGCCR Notice Bot"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_IDS = os.getenv("TELEGRAM_CHAT_IDS").split(",")  # Multiple Telegram Chat IDs

# URLs & Cache
NOTICE_URL = "https://rgccr.gov.bd/notice_categories/notice/"
CACHE_FILE = "data/previous_notices.txt"
LAST_MODIFIED_FILE = "data/last_modified.txt"
LOG_FILE = "data/error.log"
NOTICE_LIMIT = 10  # Keep latest 10 notices for email updates

# Ensure required directories exist
os.makedirs("data", exist_ok=True)

# Setup logging
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def fetch_notices():
    """Fetch notices from the website using Last-Modified header for efficiency."""
    headers = {}

    if os.path.exists(LAST_MODIFIED_FILE):
        with open(LAST_MODIFIED_FILE, "r") as f:
            last_modified = f.read().strip()
            if last_modified:
                headers["If-Modified-Since"] = last_modified

    try:
        response = requests.get(NOTICE_URL, headers=headers, timeout=10)

        if response.status_code == 304:
            print("✅ No changes detected using Last-Modified header.")
            return None, None

        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        if "Last-Modified" in response.headers:
            with open(LAST_MODIFIED_FILE, "w") as f:
                f.write(response.headers["Last-Modified"])

        notice_table = soup.select_one("table.table-striped")
        if not notice_table:
            raise ValueError("❌ Notice table not found!")

        extracted_notices = [
            f"{row.find_all('td')[1].text.strip()} - {row.find_all('td')[0].text.strip()} - {row.find_all('td')[2].find('a')['href'] if row.find_all('td')[2].find('a') else 'No link'}"
            for row in notice_table.select("tbody tr") if len(row.find_all('td')) >= 3
        ]

        return extracted_notices if extracted_notices else [], response.headers.get("Last-Modified")

    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch notices: {e}")
        return [], None


def read_cached_notices():
    """Reads cached notices. Creates file if missing."""
    if not os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "w", encoding="utf-8") as file:
            file.write("")
        return []

    with open(CACHE_FILE, "r", encoding="utf-8") as file:
        return file.read().splitlines()


def write_cache(notices):
    """Writes all notices to cache."""
    with open(CACHE_FILE, "w", encoding="utf-8") as file:
        file.write("\n".join(notices))


async def send_email(subject, body):
    """Sends an email notification to multiple recipients asynchronously."""
    try:
        msg = MIMEMultipart()
        msg["From"] = f"{EMAIL_SENDER_NAME} <{EMAIL_SENDER}>"
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))

        async with SMTP("smtp.gmail.com", port=465, use_tls=True) as smtp:
            await smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)

            for recipient in EMAIL_RECEIVERS:
                msg["To"] = recipient
                await smtp.send_message(msg)

        print("✅ Email sent successfully to all recipients!")
    except Exception as e:
        logging.error(f"❌ Failed to send email: {e}")
        print(f"❌ Failed to send email: {e}")


async def send_telegram_message(message):
    """Sends a Telegram message to multiple users."""
    for chat_id in TELEGRAM_CHAT_IDS:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {"chat_id": chat_id, "text": message}

        try:
            response = requests.post(url, data=data)
            if response.status_code == 200:
                print(f"✅ Sent Telegram message to {chat_id}")
            else:
                print(f"❌ Failed to send Telegram message: {response.json()}")
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to send Telegram message: {e}")


async def main():
    """Main script execution."""
    all_new_notices, last_modified = fetch_notices()

    if all_new_notices is None:
        return

    cached_notices = read_cached_notices()
    if not all_new_notices:
        logging.error("No notices found on the website.")
        return

    write_cache(all_new_notices)
    await send_email("📢 RGCCR Notice Update", "<br>".join(all_new_notices[:NOTICE_LIMIT]))
    await send_telegram_message("\n".join(all_new_notices[:NOTICE_LIMIT]))


if __name__ == "__main__":
    asyncio.run(main())
