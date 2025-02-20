import os
import smtplib
import requests
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

# Setup logging
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def fetch_notices():
    """Fetches notices from the website using Last-Modified header and retry logic."""
    headers = {}

    # Load Last-Modified timestamp for efficient fetching
    if os.path.exists(LAST_MODIFIED_FILE):
        with open(LAST_MODIFIED_FILE, "r") as f:
            last_modified = f.read().strip()
            if last_modified:
                headers["If-Modified-Since"] = last_modified

    # Retry logic (max 3 attempts)
    attempts = 3
    for attempt in range(1, attempts + 1):
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

        except requests.exceptions.RequestException as e:
            logging.error(f"Attempt {attempt}: Network error while fetching notices: {e}")
            if attempt < attempts:
                time.sleep(3)  # Wait before retrying
            else:
                log_error(f"Failed to fetch notices after {attempts} attempts: {e}")
                return [], None

        except Exception as e:
            log_error(f"Unexpected error: {e}")
            return [], None


def read_cached_notices():
    """Reads the cached notices from the file."""
    if not os.path.exists(CACHE_FILE):
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


def log_error(error_message):
    """Logs an error and sends an email notification."""
    print(f"❌ Error: {error_message}")
    logging.error(error_message)
    send_email("RGCCR Notice Check Error", f"An error occurred:\n{error_message}")


def format_notices_for_email(new_notices, removed_notices):
    """Formats email content with new & removed notices in HTML table format."""
    email_body = ""

    if new_notices:
        email_body += "<h3>🆕 New Notices:</h3><table border='1'><tr><th>#</th><th>Date</th><th>Title</th><th>Link</th></tr>"
        for i, notice in enumerate(new_notices[:NOTICE_LIMIT]):
            date, title, link = notice.split(" - ")
            email_body += f"<tr><td>{i+1}</td><td>{date}</td><td>{title}</td><td><a href='{link}'>View</a></td></tr>"
        email_body += "</table><br>"

    if removed_notices:
        email_body += "<h3>❌ Removed Notices:</h3><ul>"
        for notice in removed_notices:
            email_body += f"<li>{notice}</li>"
        email_body += "</ul><br>"

    return email_body if email_body else None


def main():
    """Main script execution."""
    print("🔄 Checking for new notices...")
    all_new_notices, last_modified = fetch_notices()

    # If Last-Modified header confirmed no changes, exit
    if all_new_notices is None:
        return

    cached_notices = read_cached_notices()

    if not all_new_notices:
        log_error("No notices found on the website.")
        return

    # Detect new notices and removed notices
    new_notices = [notice for notice in all_new_notices if notice not in cached_notices]
    removed_notices = [notice for notice in cached_notices if notice not in all_new_notices]

    if new_notices or removed_notices:
        print("✅ Changes detected!")
        write_cache(all_new_notices)  # Store full notices for tracking

        # Format email content
        email_body = format_notices_for_email(new_notices, removed_notices)
        if email_body:
            send_email("📢 RGCCR Notice Update", email_body, html=True)
    else:
        print("✅ No new notices detected.")


if __name__ == "__main__":
    main()
