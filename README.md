# RGCCR Notice Bot

## Overview
The **RGCCR Notice Bot** is a Python-based automation tool designed to monitor and notify users of updates on the notice board of the Rangpur Govt. City College (RGCCR) website (`https://rgccr.gov.bd/notice_categories/notice/`). It leverages web scraping, asynchronous programming, and notification systems to fetch the latest notices, compare them with previously stored data, and deliver real-time updates via email and Telegram. This tool is efficient and reliable, making it an essential resource for students and staff needing timely access to official announcements.

## Features
- **Web Scraping**: Uses `BeautifulSoup` to fetch up to 10 notices, collecting date, title, and URL for each.
- **Unique Notice Identification**: Combines title and URL (e.g., `title|url`) to uniquely identify notices and prevent duplicates.
- **New Notice Detection**: Compares fetched notices with the last 5 stored entries, marking notices before the first match as new. If no match is found, all 10 fetched notices are considered new.
- **Notification System**:
  - **Email**: Sends HTML-formatted emails with a table of new notices and clickable links.
  - **Telegram**: Sends Markdown-formatted messages with notice details and links.
- **Error Management**: Logs errors to a file and emails the developer if issues arise.
- **Testing Mode**: Offers an optional mode for debugging with test recipients.
- **Asynchronous Execution**: Employs `aiohttp` and `aiosmtplib` for fast, non-blocking operations.

## Installation

### Prerequisites
- Python 3.8 or higher
- An internet connection for scraping and notifications

### Steps
1. **Clone the Repository**:
   ```bash
   git clone https://github.com/mrbadasss/rgccr-notice-bot.git
   cd rgccr-notice-bot
   ```
2. **Install Dependencies: Install required packages from requirements.txt**:
   ```bash
   pip install -r requirements.txt
   ```
   **Contents of requirements.txt:**
   ```bash
   requests
   aiohttp
   aiosmtplib
   beautifulsoup4
   python-dotenv
   ```
3. **Configure Environment Variables: Create a .env file in the project root**:
   ```bash
   EMAIL_SENDER=your-email@gmail.com
   EMAIL_PASSWORD=your-app-specific-password
   EMAIL_RECEIVERS=receiver1@example.com\nreceiver2@example.com
   TEST_EMAIL_RECEIVERS=test1@example.com\ntest2@example.com
   TELEGRAM_BOT_TOKEN=your-telegram-bot-token
   TELEGRAM_CHAT_IDS=chat-id1\nchat-id2
   TEST_TELEGRAM_CHAT_IDS=test-chat-id1\ntest-chat-id2
   DEVELOPER_EMAIL=developer@example.com
   ```
   - **Email**: Use a Gmail account with an app-specific password (from Google Account Security).
   - **Telegram**: Obtain a bot token from BotFather and chat IDs from @getidsbot. Use newlines (\n) to separate multiple values.
  4. **Enable Testing Mode (Optional): Create data/testing_mode with 1 to enable**:
   ```bash
   mkdir -p data
   echo "1" > data/testing_mode
   ```
   **Disable by setting to 0 or removing the file**:
   ```bash
   echo "0" > data/testing_mode
   ```
   
