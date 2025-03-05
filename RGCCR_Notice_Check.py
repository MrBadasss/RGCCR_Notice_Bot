import os
import aiohttp
import asyncio
import logging
from bs4 import BeautifulSoup
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
from aiosmtplib import SMTP

# Load environment variables from a .env file for secure configuration
print("🌍 Loading environment variables from .env file...")
load_dotenv()
print("✅ Environment variables loaded successfully.")

# Retrieve configuration details from environment variables
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVERS = os.getenv("EMAIL_RECEIVERS", "").split("\n")
TEST_EMAIL_RECEIVERS = os.getenv("TEST_EMAIL_RECEIVERS", "").split("\n")
EMAIL_SENDER_NAME = "RGCCR Notice Bot"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_IDS = os.getenv("TELEGRAM_CHAT_IDS", "").split("\n")
TEST_TELEGRAM_CHAT_IDS = os.getenv("TEST_TELEGRAM_CHAT_IDS", "").split("\n")

DEVELOPER_EMAIL = os.getenv("DEVELOPER_EMAIL")

# Define constants for the script
NOTICE_URL = "https://rgccr.gov.bd/notice_categories/notice/"
LATEST_NOTICE_FILE = "data/latest_notice.txt"
LOG_FILE = "data/error.log"
NOTICE_LIMIT = 10  # Maximum number of notices to fetch at once
STORED_NOTICE_LIMIT = 5  # Number of recent notice titles to store

# Ensure the data directory exists to store files
print("📁 Checking if 'data' directory exists...")
os.makedirs("data", exist_ok=True)
print("✅ 'data' directory is ready.")

# Configure logging to track errors in a persistent log file
print("📋 Setting up logging configuration...")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
print("✅ Logging configured to write errors to", LOG_FILE)

# Function to determine if testing mode is enabled
def is_testing_mode():
    """Check if the script should run in testing mode by reading a file."""
    testing_file = "data/testing_mode"
    if os.path.exists(testing_file):
        with open(testing_file, "r", encoding="utf-8") as f:
            return f.read().strip() == "1"
    return False

async def fetch_latest_notices():
    """Fetch the latest notices from the RGCCR website."""
    print("🔄 Starting to fetch the latest notices from", NOTICE_URL)
    try:
        async with aiohttp.ClientSession() as session:
            print("🌐 Opening HTTP session to fetch webpage content...")
            async with session.get(NOTICE_URL, timeout=5) as response:
                print(f"ℹ️ Received response with status code: {response.status}")
                if response.status != 200:
                    raise ValueError(f"❌ Failed to fetch notices: HTTP status {response.status}")
                print("📄 Parsing webpage content with BeautifulSoup...")
                soup = BeautifulSoup(await response.text(), "html.parser")
                notice_table = soup.select_one("table.table-striped")
                if not notice_table:
                    raise ValueError("❌ Notice table not found on the webpage!")

                notices = []
                print(f"🔍 Scraping up to {NOTICE_LIMIT} notices from the table...")
                for row in notice_table.select("tbody tr")[:NOTICE_LIMIT]:
                    cols = row.find_all("td")
                    if len(cols) < 3:
                        print("⚠️ Skipping malformed table row with insufficient columns.")
                        continue
                    title = cols[0].text.strip()
                    date = cols[1].text.strip()
                    link_tag = cols[2].find("a")
                    link = link_tag["href"] if link_tag else "No link"
                    notices.append((date, title, link))
                    print(f"✅ Added notice: {title} (Date: {date})")
                print(f"✅ Successfully fetched {len(notices)} notices from the website.")
                return notices
    except Exception as e:
        error_msg = f"❌ Error fetching notices from {NOTICE_URL}: {str(e)}"
        logging.error(error_msg)
        print(error_msg)
        return []

async def read_latest_notices():
    """Read the list of stored notice titles from the file."""
    print("📖 Attempting to read the stored notices from", LATEST_NOTICE_FILE)
    if not os.path.exists(LATEST_NOTICE_FILE):
        print("ℹ️ No stored notice file found. Treating all fetched notices as new.")
        return []
    try:
        with open(LATEST_NOTICE_FILE, "r", encoding="utf-8") as file:
            stored_titles = [line.strip() for line in file if line.strip()]
            print(f"✅ Retrieved {len(stored_titles)} stored notice titles: {stored_titles}")
            return stored_titles
    except Exception as e:
        error_msg = f"❌ Failed to read stored notices from {LATEST_NOTICE_FILE}: {str(e)}"
        logging.error(error_msg)
        print(error_msg)
        return []

async def write_latest_notices(latest_notice_titles):
    """Write the list of recent notice titles to the storage file, limited to STORED_NOTICE_LIMIT."""
    print(f"💾 Preparing to update stored notices with {len(latest_notice_titles)} titles")
    try:
        with open(LATEST_NOTICE_FILE, "w", encoding="utf-8") as file:
            # Take the last STORED_NOTICE_LIMIT titles (assuming fetch order is newest first)
            notices_to_store = latest_notice_titles[-STORED_NOTICE_LIMIT:]
            for title in notices_to_store:
                file.write(f"{title}\n")
        print(f"✅ Successfully updated {LATEST_NOTICE_FILE} with {len(notices_to_store)} recent notice titles")
    except Exception as e:
        error_msg = f"❌ Failed to write latest notices to {LATEST_NOTICE_FILE}: {str(e)}"
        logging.error(error_msg)
        print(error_msg)

async def send_email(subject, notices, receivers):
    """Send an email notification containing the new notices using Bcc."""
    print("📧 Preparing to send email notification to", ", ".join(receivers))
    try:
        msg = MIMEMultipart()
        msg["From"] = f"{EMAIL_SENDER_NAME} <{EMAIL_SENDER}>"
        msg["To"] = ", ".join(receivers)
        msg["Subject"] = subject

        print("📝 Constructing HTML email body with notice details...")
        email_body = f"""
        <html><body>
        <h3>📢 NEW NOTICE COUNT: {len(notices)}</h3>
        <p>The following new notices were found on the RGCCR website:</p>
        <table border="1" cellspacing="0" cellpadding="5">
        <tr><th>#</th><th>Date</th><th>Title</th><th>Link</th></tr>
        """
        for i, (date, title, link) in enumerate(notices):
            view_button = (
                f'<a href="{link}" target="_blank" style="text-decoration:none;">'
                f'<button style="padding:5px 10px;background-color:#007BFF;color:white;border:none;border-radius:5px;">View</button></a>'
                if link != "No link" else "No link"
            )
            email_body += f"<tr><td>{i + 1}</td><td>{date}</td><td>{title}</td><td>{view_button}</td></tr>"
        email_body += "</table></body></html>"

        msg.attach(MIMEText(email_body, "html"))
        print("📤 Connecting to SMTP server to send email...")
        async with SMTP(hostname="smtp.gmail.com", port=465, use_tls=True) as smtp:
            print("🔑 Logging into SMTP server with sender credentials...")
            await smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
            print("🚀 Sending email to recipients...")
            await smtp.send_message(msg)
        print(f"✅ Email successfully sent to: {', '.join(receivers)}")
    except Exception as e:
        error_msg = f"❌ Failed to send email to {', '.join(receivers)}: {str(e)}"
        logging.error(error_msg)
        print(error_msg)

async def send_telegram_messages(notices, chat_ids):
    """Send Telegram notifications with the new notices, using Markdown formatting."""
    print("📱 Preparing to send Telegram notifications to chat IDs:", ", ".join(chat_ids))
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    print(f"📝 Building Telegram message for {len(notices)} new notices...")
    message = f"📢 *NEW NOTICE COUNT: {len(notices)}*\n\n"
    for i, (date, title, link) in enumerate(notices):
        message += f"{i + 1}. {date} - {title}\n"
        if link != "No link":
            message += f"   🔗 [View]({link})\n"
        else:
            message += "   No link available\n"

    async with aiohttp.ClientSession() as session:
        for chat_id in chat_ids:
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            print(f"📤 Sending Telegram message to chat ID: {chat_id}")
            try:
                async with session.post(url, json=payload) as response:
                    resp_json = await response.json()
                    if resp_json.get("ok"):
                        print(f"✅ Telegram message successfully sent to chat ID: {chat_id}")
                    else:
                        error_msg = f"❌ Failed to send Telegram message to chat ID {chat_id}: {resp_json.get('description')}"
                        logging.error(error_msg)
                        print(error_msg)
            except Exception as e:
                error_msg = f"❌ Error sending Telegram message to chat ID {chat_id}: {str(e)}"
                logging.error(error_msg)
                print(error_msg)

async def send_error_email(error_msg):
    """Send an error notification to the repository developer."""
    if not DEVELOPER_EMAIL:
        print("❌ DEVELOPER_EMAIL is not set. Cannot send error notice.")
        return
    try:
        msg = MIMEMultipart()
        msg["From"] = f"{EMAIL_SENDER_NAME} <{EMAIL_SENDER}>"
        msg["To"] = DEVELOPER_EMAIL
        msg["Subject"] = "❌ Error in RGCCR Notice Checker"
        msg.attach(MIMEText(f"<pre>{error_msg}</pre>", "html"))
        async with SMTP(hostname="smtp.gmail.com", port=465, use_tls=True) as smtp:
            await smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
            await smtp.send_message(msg)
        print(f"✅ Error notice sent to {DEVELOPER_EMAIL}")
    except Exception as e:
        print(f"❌ Failed to send error notice: {str(e)}")

async def main():
    """Main function to orchestrate notice checking and notification sending."""
    print("🚀 Starting the RGCCR Notice Checker script...")
    try:
        # Determine receivers based on testing mode
        if is_testing_mode():
            print("🔧 Running in testing mode. Using test receivers.")
            email_receivers = TEST_EMAIL_RECEIVERS
            telegram_chat_ids = TEST_TELEGRAM_CHAT_IDS
        else:
            print("▶️ Running in normal mode. Using regular receivers.")
            email_receivers = EMAIL_RECEIVERS
            telegram_chat_ids = TELEGRAM_CHAT_IDS

        # Fetch the latest notices from the website
        print("🔍 Initiating notice fetch process...")
        latest_notices = await fetch_latest_notices()
        if not latest_notices:
            print("ℹ️ No notices were fetched from the website. Exiting script.")
            return

        # Read the list of stored notice titles
        print("📋 Checking for previously stored notices...")
        stored_notice_titles = await read_latest_notices()

        # Identify new notices by comparing with the stored titles
        new_notices = []
        if not stored_notice_titles:
            print("ℹ️ No previous notices stored. All fetched notices are considered new.")
            new_notices = latest_notices
        else:
            print(f"🔎 Comparing {len(latest_notices)} fetched notices against {len(stored_notice_titles)} stored titles...")
            for notice in latest_notices:
                _, notice_title, _ = notice  # Unpack only the title for comparison
                if notice_title not in stored_notice_titles:
                    new_notices.append(notice)
                    print(f"🆕 Detected new notice: '{notice_title}'")
                else:
                    print(f"✅ Found match with stored title: '{notice_title}'")

        if new_notices:
            print(f"🎉 Found {len(new_notices)} new notice(s)! Proceeding with notifications...")
            # Send email notification with new notices
            await send_email(f"📢 RGCCR Notice Bot: {len(new_notices)} New Notice(s)", new_notices, email_receivers)
            # Send Telegram notifications with new notices
            await send_telegram_messages(new_notices, telegram_chat_ids)
            # Update the stored notices with the latest titles
            print("🔄 Updating the stored notices to the latest fetched notice titles...")
            latest_notice_titles = [notice[1] for notice in latest_notices]  # Extract titles
            await write_latest_notices(latest_notice_titles)
            print("✅ Notice checking and notification process completed successfully!")
        else:
            print("ℹ️ No new notices detected since the last check.")
    except Exception as e:
        error_msg = f"❌ An unexpected error occurred in the main function: {str(e)}"
        logging.error(error_msg)
        print(error_msg)
        await send_error_email(error_msg)
    finally:
        print("🏁 RGCCR Notice Checker script execution finished.")

if __name__ == "__main__":
    print("▶️ Launching the notice checker script...")
    asyncio.run(main())
    print("🛑 Script execution completed.")
