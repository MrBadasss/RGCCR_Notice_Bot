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

# Website URL & Cache File
NOTICE_URL = "https://rgccr.gov.bd/notice_categories/notice/"
CACHE_DIR = "data"
CACHE_FILE = os.path.join(CACHE_DIR, "previous_notices.txt")
ERROR_LOG_FILE = os.path.join(CACHE_DIR, "error.log")


def fetch_notices():
    """Fetches the latest notices from the RGCCR website."""
    try:
        response = requests.get(NOTICE_URL, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        notice_table = soup.select_one("table.table-striped")  # Locate the table

        if not notice_table:
            log_error("Could not find the notice table on the page.")
            return []

        extracted_notices = []
        for row in notice_table.select("tbody tr"):
            columns = row.find_all("td")
            if len(columns) < 3:
                continue  # Skip if there aren't enough columns

            title = columns[0].text.strip()
            date = columns[1].text.strip()
            link = columns[2].find("a")["href"] if columns[2].find("a") else "No link"

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
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as file:
        file.write("\n".join(notices))


def send_email(subject, body):
    """Sends an email notification with the bot's name as the sender."""
    try:
        bot_name = "RGCCR Notice Bot"  # Change to your bot's name
        sender_with_name = f"{bot_name} <{EMAIL_SENDER}>"

        msg = MIMEMultipart()
        msg["From"] = sender_with_name  # Use the formatted sender
        msg["To"] = EMAIL_RECEIVER
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)

        print("✅ Email sent successfully!")
    except Exception as e:
        log_error(f"Failed to send email: {e}")


def log_error(error_message):
    """Logs an error and sends an email alert."""
    print(f"❌ Error: {error_message}")

    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(ERROR_LOG_FILE, "a", encoding="utf-8") as file:
        file.write(f"{error_message}\n")

    send_email("❌ RGCCR Notice Check Error", f"An error occurred:\n{error_message}")


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
