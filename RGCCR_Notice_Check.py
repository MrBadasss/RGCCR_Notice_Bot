import os
import smtplib
import requests
import logging
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
EMAIL_SENDER_NAME = "Notice Board Bot"

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_IDS = os.getenv("TELEGRAM_CHAT_IDS", "").split(",")  # Multiple IDs allowed

# URLs & Cache
NOTICE_URL = "https://rgccr.gov.bd/notice_categories/notice/"
CACHE_FILE = "data/previous_notices.txt"
LAST_MODIFIED_FILE = "data/last_modified.txt"
LOG_FILE = "data/error.log"
NOTICE_LIMIT = 10  # Only keep track of the latest 10 notices for notification

# Ensure required directories exist
os.makedirs("data", exist_ok=True)

# Setup logging
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def fetch_notices():
    """Fetches notices using Last-Modified header and retry logic."""
    headers = {}

    # Load Last-Modified timestamp for efficiency
    if os.path.exists(LAST_MODIFIED_FILE):
        with open(LAST_MODIFIED_FILE, "r") as f:
            last_modified = f.read().strip()
            if last_modified:
                headers["If-Modified-Since"] = last_modified

    try:
        response = requests.get(NOTICE_URL, headers=headers, timeout=10)

        # If status 304 (Not Modified), return None to avoid unnecessary parsing
        if response.status_code == 304:
            print("✅ No changes detected using Last-Modified header.")
            logging.info("No changes detected using Last-Modified header.")
            return None, None

        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Save new Last-Modified timestamp if available
        if "Last-Modified" in response.headers:
            with open(LAST_MODIFIED_FILE, "w") as f:
                f.write(response.headers["Last-Modified"])

        # Extract notices
        notice_table = soup.select_one("table.table-striped")
        if not notice_table:
            raise ValueError("❌ Notice table not found!")

        extracted_notices = []
        for row in notice_table.select("tbody tr"):
            cols = row.find_all("td")
            if len(cols) < 3:
                continue  # Skip invalid rows

            title = cols[0].text.strip()
            date = cols[1].text.strip()
            link_tag = cols[2].find("a")
            link = link_tag["href"] if link_tag else "No link"

            extracted_notices.append(f"{date} - {title} - {link}")

        return extracted_notices if extracted_notices else [], response.headers.get("Last-Modified")

    except Exception as e:
        logging.error(f"Error fetching notices: {e}")
        return [], None


def read_cached_notices():
    """Reads the cached notices from the file. Creates file if missing."""
    if not os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "w", encoding="utf-8") as file:
            file.write("")
        return []

    with open(CACHE_FILE, "r", encoding="utf-8") as file:
        return file.read().splitlines()


def write_cache(notices):
    """Writes all notices to cache, ensuring tracking."""
    with open(CACHE_FILE, "w", encoding="utf-8") as file:
        file.write("\n".join(notices))


def send_email(subject, body):
    """Sends an email notification."""
    try:
        msg = MIMEMultipart()
        msg["From"] = f"{EMAIL_SENDER_NAME} <{EMAIL_SENDER}>"
        msg["To"] = EMAIL_RECEIVER
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)

        print("✅ Email sent successfully!")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        logging.error(f"Failed to send email: {e}")


def send_telegram_message(message):
    """Sends a message to multiple Telegram users."""
    for chat_id in TELEGRAM_CHAT_IDS:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": message}
        requests.post(url, json=payload)


def main():
    """Main script execution."""
    print("🔄 Checking for new notices...")
    all_new_notices, last_modified = fetch_notices()

    if all_new_notices is None:
        return

    cached_notices = read_cached_notices()

    new_notices = [n for n in all_new_notices if n not in cached_notices]

    if new_notices:
        print("✅ New notices detected!")
        write_cache(all_new_notices)

        message = "\n".join(new_notices[:NOTICE_LIMIT])
        send_email("📢 Notice Board Update", message)
        send_telegram_message(message)
    else:
        print("✅ No new notices detected.")


if __name__ == "__main__":
    main()
