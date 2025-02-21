import os
import aiohttp
import asyncio
import logging
from bs4 import BeautifulSoup
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
from aiosmtplib import SMTP  # Async SMTP for email sending

# Load environment variables
load_dotenv()

# Email Configuration
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVERS = os.getenv("EMAIL_RECEIVERS").split(",")  # Multiple recipients
EMAIL_SENDER_NAME = "Notice Bot"

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_IDS = os.getenv("TELEGRAM_CHAT_IDS").split(",")  # Multiple chat IDs

# URLs & Cache
NOTICE_URL = "https://rgccr.gov.bd/notice_categories/notice/"
CACHE_FILE = "data/previous_notices.txt"
LAST_MODIFIED_FILE = "data/last_modified.txt"
LOG_FILE = "data/error.log"
NOTICE_LIMIT = 10  # Latest 10 notices for email and Telegram

# Ensure required directories exist
os.makedirs("data", exist_ok=True)

# Setup logging
logging.basicConfig(filename=LOG_FILE, level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")


async def fetch_notices():
    """Fetch notices asynchronously using Last-Modified header for efficiency."""
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

            extracted_notices = []
            for i, row in enumerate(notice_table.select("tbody tr")):
                cols = row.find_all("td")
                if len(cols) < 3:
                    continue  # Skip invalid rows

                title = cols[0].text.strip()
                date = cols[1].text.strip()
                link_tag = cols[2].find("a")
                link = link_tag["href"] if link_tag else "No link"

                # Ensure Bangla URLs are clickable
                formatted_link = f'<a href="{link}" target="_blank">{link}</a>' if link != "No link" else "No link"
                extracted_notices.append(f"{i+1}. {date} - {title} - {formatted_link}")

            return extracted_notices if extracted_notices else [], response.headers.get("Last-Modified")


async def read_cached_notices():
    """Reads cached notices asynchronously."""
    if not os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "w") as file:
            file.write("")
        return []

    with open(CACHE_FILE, "r") as file:
        return file.read().splitlines()


async def write_cache(notices):
    """Writes all notices to cache asynchronously."""
    with open(CACHE_FILE, "w") as file:
        file.write("\n".join(notices))


async def send_email(subject, notices):
    """Sends an email notification asynchronously to multiple recipients."""
    try:
        msg = MIMEMultipart()
        msg["From"] = f"{EMAIL_SENDER_NAME} <{EMAIL_SENDER}>"
        msg["To"] = ", ".join(EMAIL_RECEIVERS)
        msg["Subject"] = subject

        # Format the email body with an HTML table
        email_body = """
        <html><body>
        <h3>📢 New Notices:</h3>
        <table border="1" cellspacing="0" cellpadding="5">
        <tr><th>#</th><th>Date</th><th>Title</th><th>Link</th></tr>
        """
        
        for i, notice in enumerate(notices[:NOTICE_LIMIT]):
            parts = notice.split(" - ")
            if len(parts) < 3:
                continue  # Skip notices with missing data

            title = parts[1] if len(parts) > 1 else "N/A"
            date = parts[0] if len(parts) > 0 else "N/A"
            link = parts[2] if len(parts) > 2 else "No link"

            email_body += f"<tr><td>{i+1}</td><td>{date}</td><td>{title}</td><td>{link}</td></tr>"

        email_body += "</table></body></html>"

        msg.attach(MIMEText(email_body, "html"))

        async with SMTP(hostname="smtp.gmail.com", port=465, use_tls=True) as smtp:
            await smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
            await smtp.send_message(msg)

        print("✅ Email sent successfully!")
    except Exception as e:
        logging.error(f"❌ Failed to send email: {e}")
        print(f"❌ Failed to send email: {e}")


def escape_markdown(text):
    """Escape Markdown special characters for Telegram"""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return "".join(f"\\{c}" if c in escape_chars else c for c in text)


async def send_telegram_messages(notices):
    """Send a Telegram message to multiple chat IDs with formatted notices."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    message = "📢 *New Notices:*\n\n"
    
    for notice in notices[:NOTICE_LIMIT]:
        parts = notice.split(" - ")
        if len(parts) < 3:
            continue  # Skip malformed notices
        
        title = escape_markdown(parts[1]) if len(parts) > 1 else "N/A"
        date = escape_markdown(parts[0]) if len(parts) > 0 else "N/A"
        link = parts[2] if len(parts) > 2 else "No link"

        message += f"📌 *{date}* - [{title}]({link})\n"

    async with aiohttp.ClientSession() as session:
        for chat_id in TELEGRAM_CHAT_IDS:
            async with session.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "MarkdownV2"}) as response:
                resp_json = await response.json()
                if resp_json.get("ok"):
                    print(f"✅ Sent Telegram message to {chat_id}")
                else:
                    print(f"❌ Failed to send Telegram message to {chat_id}: {resp_json}")


async def main():
    """Main script execution."""
    print("🔄 Checking for new notices...")
    all_new_notices, last_modified = await fetch_notices()

    if all_new_notices is None:
        return

    cached_notices = await read_cached_notices()

    if not all_new_notices:
        logging.error("No notices found on the website.")
        return

    new_notices = [notice for notice in all_new_notices if notice not in cached_notices]
    removed_notices = [notice for notice in cached_notices if notice not in all_new_notices]

    if new_notices or removed_notices:
        print("✅ Changes detected!")
        await write_cache(all_new_notices)

        await send_email("📢 Notice Update", new_notices)
        await send_telegram_messages(new_notices)
    else:
        print("✅ No new notices detected.")


if __name__ == "__main__":
    asyncio.run(main())
