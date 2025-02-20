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

NOTICE_URL = "https://rgccr.gov.bd/notice_categories/notice/"
CACHE_FILE = "data/previous_notices.txt"
NOTICE_LIMIT = 10  # Only keep track of the latest 10 notices

def fetch_notices():
    """Fetches all notices from the website."""
    try:
        response = requests.get(NOTICE_URL, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Find the notice table
        notice_table = soup.select_one("table.table-striped")

        if not notice_table:
            raise ValueError("❌ Notice table not found!")

        extracted_notices = []
        for row in notice_table.select("tbody tr"):
            cols = row.find_all("td")
            if len(cols) < 3:
                continue  # Skip invalid rows

            title = cols[0].text.strip()  # Title column
            date = cols[1].text.strip()   # Date column
            link_tag = cols[2].find("a")  # Details column
            link = link_tag["href"] if link_tag else "No link"

            extracted_notices.append(f"{date} - {title} - {link}")

        return extracted_notices if extracted_notices else []

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
    """Writes all notices to cache, but email will only contain the latest 10."""
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

def log_error(error_message):
    """Logs an error and sends an email notification."""
    print(f"❌ Error: {error_message}")
    send_email("RGCCR Notice Check Error", f"An error occurred:\n{error_message}")

def format_notices_for_email(notices):
    """Formats the latest 10 notices with indexing for email."""
    formatted_notices = "\n".join([f"{i+1}. {notice}" for i, notice in enumerate(notices[:NOTICE_LIMIT])])
    return formatted_notices

def main():
    """Main script execution."""
    print("🔄 Checking for new notices...")
    all_new_notices = fetch_notices()
    cached_notices = read_cached_notices()

    if not all_new_notices:
        log_error("No notices found on the website.")
        return

    # If new notices are different from cached, update and notify
    if all_new_notices != cached_notices:
        print("✅ New notices found!")
        write_cache(all_new_notices)  # Store all notices for tracking

        latest_notices = all_new_notices[:NOTICE_LIMIT]  # Only the latest 10 for notification
        formatted_email_body = format_notices_for_email(latest_notices)

        send_email("📢 RGCCR Notice Update", f"New notices detected:\n\n{formatted_email_body}")
    else:
        print("✅ No new notices detected.")

if __name__ == "__main__":
    main()
