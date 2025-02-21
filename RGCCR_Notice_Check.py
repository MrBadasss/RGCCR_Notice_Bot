import os
import aiohttp
import asyncio
import logging
from bs4 import BeautifulSoup
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
from aiosmtplib import SMTP

# Load environment variables
load_dotenv()

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVERS = os.getenv("EMAIL_RECEIVERS").split(",")
EMAIL_SENDER_NAME = "Notice Bot"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_IDS = os.getenv("TELEGRAM_CHAT_IDS").split(",")

NOTICE_URL = "https://rgccr.gov.bd/notice_categories/notice/"
LATEST_NOTICE_FILE = "data/latest_notice.txt"
LOG_FILE = "data/error.log"
NOTICE_LIMIT = 10  # Fetch latest 10 notices
EMAIL_NOTICE_LIMIT = 5  # Include last 5 notices in email and Telegram

os.makedirs("data", exist_ok=True)
logging.basicConfig(filename=LOG_FILE, level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")


async def fetch_latest_notices():
    """Fetch the latest notices from the website."""
    async with aiohttp.ClientSession() as session:
        async with session.get(NOTICE_URL, timeout=5) as response:
            if response.status != 200:
                raise ValueError(f"❌ Failed to fetch notices: {response.status}")

            soup = BeautifulSoup(await response.text(), "html.parser")
            notice_table = soup.select_one("table.table-striped")

            if not notice_table:
                raise ValueError("❌ Notice table not found!")

            notices = []
            for row in notice_table.select("tbody tr")[:NOTICE_LIMIT]:  # Limit to first 10 notices
                cols = row.find_all("td")
                if len(cols) < 3:
                    continue  # Skip invalid rows

                title = cols[0].text.strip()
                date = cols[1].text.strip()
                link_tag = cols[2].find("a")
                link = link_tag["href"] if link_tag else "No link"

                notices.append((date, title, link))

            return notices


async def read_latest_notice():
    """Reads the last stored notice ID (title)."""
    if not os.path.exists(LATEST_NOTICE_FILE):
        return None

    with open(LATEST_NOTICE_FILE, "r") as file:
        return file.read().strip()


async def write_latest_notice(latest_notice_id):
    """Stores the latest notice ID (title)."""
    with open(LATEST_NOTICE_FILE, "w") as file:
        file.write(latest_notice_id)


async def send_email(subject, notices):
    """Send email notification with the last notices based on EMAIL_NOTICE_LIMIT."""
    try:
        msg = MIMEMultipart()
        msg["From"] = f"{EMAIL_SENDER_NAME} <{EMAIL_SENDER}>"
        msg["To"] = ", ".join(EMAIL_RECEIVERS)
        msg["Subject"] = subject

        # Create an HTML email body with a "View" button
        email_body = f"""
        <html><body>
        <h3>📢 New Notices (Last {EMAIL_NOTICE_LIMIT}):</h3>
        <table border="1" cellspacing="0" cellpadding="5">
        <tr><th>#</th><th>Date</th><th>Title</th><th>Link</th></tr>
        """

        for i, (date, title, link) in enumerate(notices[:EMAIL_NOTICE_LIMIT]):
            view_button = (
                f'<a href="{link}" target="_blank" style="text-decoration:none;">'
                f'<button style="padding:5px 10px;background-color:#007BFF;color:white;border:none;border-radius:5px;">View</button></a>'
                if link != "No link"
                else "No link"
            )
            email_body += f"<tr><td>{i+1}</td><td>{date}</td><td>{title}</td><td>{view_button}</td></tr>"

        email_body += "</table></body></html>"

        msg.attach(MIMEText(email_body, "html"))

        async with SMTP(hostname="smtp.gmail.com", port=465, use_tls=True) as smtp:
            await smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
            await smtp.send_message(msg)

        print("✅ Email sent successfully!")
    except Exception as e:
        logging.error(f"❌ Failed to send email: {e}")
        print(f"❌ Failed to send email: {e}")


async def send_telegram_messages(notices):
    """Send a plain text Telegram message to multiple chat IDs."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    # Generate a simple text message without formatting
    message = f"📢 New Notices (Last {EMAIL_NOTICE_LIMIT}):\n\n"

    for i, (date, title, link) in enumerate(notices[:EMAIL_NOTICE_LIMIT]):
        message += f"{i+1}. {date} - {title}\n"
        if link != "No link":
            message += f"   🔗 {link}\n"

    async with aiohttp.ClientSession() as session:
        for chat_id in TELEGRAM_CHAT_IDS:
            async with session.post(url, json={"chat_id": chat_id, "text": message}) as response:
                resp_json = await response.json()
                if resp_json.get("ok"):
                    print(f"✅ Sent Telegram message to {chat_id}")
                else:
                    print(f"❌ Failed to send Telegram message to {chat_id}: {resp_json}")


async def main():
    """Main script execution with optimized notice detection."""
    print("🔄 Checking for new notices...")
    latest_notices = await fetch_latest_notices()

    if not latest_notices:
        print("✅ No notices found on the website.")
        return

    last_stored_notice_id = await read_latest_notice()

    # Compare only the latest notice
    latest_notice_id = latest_notices[0][1]  # Use the title as the unique identifier

    if last_stored_notice_id != latest_notice_id:
        print("✅ New notice detected!")
        await write_latest_notice(latest_notice_id)  # Update stored notice

        # Send notifications with the last EMAIL_NOTICE_LIMIT notices
        await send_email("📢 Notice Update", latest_notices[:EMAIL_NOTICE_LIMIT])
        await send_telegram_messages(latest_notices[:EMAIL_NOTICE_LIMIT])
    else:
        print("✅ No new notices detected.")


if __name__ == "__main__":
    asyncio.run(main())
