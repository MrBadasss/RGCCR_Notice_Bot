import os
import smtplib
import requests
from bs4 import BeautifulSoup
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# Email Configuration
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
EMAIL_SENDER_NAME = "RGCCR Notice Bot"

# Notice Website URL
NOTICE_URL = "https://rgccr.gov.bd/notice_categories/notice/"
CACHE_FILE = "data/previous_notices.txt"
ERROR_LOG_FILE = "data/error.log"

def fetch_notices():
    """Fetch all notices from the RGCCR website with retries."""
    retries = 3
    for attempt in range(retries):
        try:
            print(f"🌐 Fetching notices... (Attempt {attempt + 1}/{retries})")
            response = requests.get(NOTICE_URL, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            notice_table = soup.select_one("table.table-striped")
            
            if not notice_table:
                raise ValueError("⚠️ Could not find the notice table in the webpage.")

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

            return extracted_notices if extracted_notices else []

        except requests.exceptions.RequestException as e:
            print(f"⚠️ Network error: {e}")
            time.sleep(5)  # Wait before retrying

    log_error("❌ Failed to fetch notices after multiple attempts.")
    return []

def read_cached_notices():
    """Reads cached notices from file."""
    if not os.path.exists(CACHE_FILE):
        return []
    with open(CACHE_FILE, "r", encoding="utf-8") as file:
        return file.read().splitlines()

def write_cache(notices):
    """Writes the latest notices to the cache file."""
    with open(CACHE_FILE, "w", encoding="utf-8") as file:
        file.write("\n".join(notices))

def detect_new_notices(new_notices, cached_notices):
    """Detects new notices by comparing with cached data."""
    return [notice for notice in new_notices if notice not in cached_notices]

def send_email(subject, body, attach_error_log=False):
    """Sends an email notification with optional error log attachment."""
    try:
        msg = MIMEMultipart()
        msg["From"] = f"{EMAIL_SENDER_NAME} <{EMAIL_SENDER}>"
        msg["To"] = EMAIL_RECEIVER
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        if attach_error_log and os.path.exists(ERROR_LOG_FILE):
            with open(ERROR_LOG_FILE, "r", encoding="utf-8") as file:
                error_content = file.read()
            msg.attach(MIMEText(f"\n📜 Error Log:\n{error_content}", "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)

        print("✅ Email sent successfully!")
    except Exception as e:
        log_error(f"❌ Failed to send email: {e}")

def log_error(error_message):
    """Logs errors to a file and prints them."""
    print(error_message)
    with open(ERROR_LOG_FILE, "a", encoding="utf-8") as file:
        file.write(f"{error_message}\n")
    send_email("🚨 RGCCR Notice Check Error", error_message, attach_error_log=True)

def main():
    """Main execution function."""
    print("🔄 Checking for new notices...")
    new_notices = fetch_notices()
    cached_notices = read_cached_notices()

    if not new_notices:
        log_error("⚠️ No notices found on the website.")
        return

    new_entries = detect_new_notices(new_notices, cached_notices)
    
    if new_entries:
        print(f"✅ {len(new_entries)} new notices found! Updating cache and sending email...")
        write_cache(new_notices)  # Update cache with all notices

        notice_list = "\n".join(new_entries)
        send_email("📢 New RGCCR Notice Alert!", f"New notices detected:\n\n{notice_list}")
    else:
        print("✅ No new notices detected.")

if __name__ == "__main__":
    main()
