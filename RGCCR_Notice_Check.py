import os
import smtplib
import aiohttp
import asyncio
import time
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
EMAIL_SENDER_NAME = "RGCCR Notice Bot"

# URLs & Cache
NOTICE_URL = "https://rgccr.gov.bd/notice_categories/notice/"
CACHE_FILE = "data/previous_notices.txt"
LAST_MODIFIED_FILE = "data/last_modified.txt"
LOG_FILE = "data/error.log"
NOTICE_LIMIT = 10  # Only keep track of the latest 10 notices for email notifications

# Ensure required directories exist
os.makedirs("data", exist_ok=True)

# Setup logging
logging.basicConfig(filename=LOG_FILE, level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")


async def fetch_notices():
    """Fetches notices asynchronously using Last-Modified header for efficiency."""
    headers = {}

    # Load Last-Modified timestamp for efficient fetching
    if os.path.exists(LAST_MODIFIED_FILE):
        with open(LAST_MODIFIED_FILE, "r") as f:
            last_modified = f.read().strip()
            if last_modified:
                headers["If-Modified-Since"] = last_modified

    async with aiohttp.ClientSession() as session:
        async with session.get(NOTICE_URL, headers=headers, timeout=5) as response:
            if response.status == 304:
                print("✅ No changes detected using Last-Modified header.")
                return None, None

            response_text = await response.text()

            soup = BeautifulSoup(response_text, "html.parser")
            notice_table = soup.select_one("table.table-striped")

            if not notice_table:
                raise ValueError("❌ Notice table not found!")

            extracted_notices = [
                f"{row.find_all('td')[1].text.strip()} - {row.find_all('td')[0].text.strip()} - {row.find_all('td')[2].find('a')['href'] if row.find_all('td')[2].find('a') else 'No link'}"
                for row in notice_table.select("tbody tr") if len(row.find_all('td')) >= 3
            ]

            return extracted_notices if extracted_notices else [], response.headers.get("Last-Modified")


def read_cached_notices():
    """Reads the cached notices from the file. Creates file if missing."""
    if not os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "w", encoding="utf-8") as file:
            file.write("")
        return []

    with open(CACHE_FILE, "r", encoding="utf-8") as file:
        return file.read().splitlines()


def write_cache(notices):
    """Writes all notices to cache, ensuring we track everything."""
    with open(CACHE_FILE, "w", encoding="utf-8") as file:
        file.write("\n".join(notices))


def send_email(subject, body, html=False):
    """Sends an email notification in either plain text or HTML."""
    try:
        msg = MIMEMultipart()
        msg["From"] = f"{EMAIL_SENDER_NAME} <{EMAIL_SENDER}>"
        msg["To"] = EMAIL_RECEIVER
        msg["Subject"] = subject

        if html:
            msg.attach(MIMEText(body, "html"))
        else:
            msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)

        print("✅ Email sent successfully!")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        logging.error(f"Failed to send email: {e}")


async def main():
    """Main script execution."""
    print("🔄 Checking for new notices...")
    all_new_notices, last_modified = await fetch_notices()

    if all_new_notices is None:
        return

    cached_notices = read_cached_notices()

    if not all_new_notices:
        logging.error("No notices found on the website.")
        return

    new_notices = [notice for notice in all_new_notices if notice not in cached_notices]
    removed_notices = [notice for notice in cached_notices if notice not in all_new_notices]

    if new_notices or removed_notices:
        print("✅ Changes detected!")
        write_cache(all_new_notices)

        email_body = "\n".join([f"{i+1}. {notice}" for i, notice in enumerate(new_notices[:NOTICE_LIMIT])])
        send_email("📢 RGCCR Notice Update", email_body)
    else:
        print("✅ No new notices detected.")


if __name__ == "__main__":
    asyncio.run(main())
