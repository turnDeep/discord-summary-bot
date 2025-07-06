# Discord Summary Bot

This bot monitors specified Discord channels and periodically generates summaries of the conversations using the Gemini API. It can also provide manual summaries, display recent messages, and more.

## Features

- Automatic summaries at configurable intervals.
- Manual summary generation via command.
- Customizable list of channels to monitor.
- Identification of key topics, active users, and recent messages in summaries.
- Fallback to simple keyword-based summary if Gemini API fails.
- Commands to manage monitored channels and bot settings.
- Advanced, more detailed summaries using an asynchronous Gemini API call.

## Setup and Configuration

To get the bot running, you need to configure a few things.

### Prerequisites

- Python 3.7+ (Recommended: Python 3.11.x as specified in `runtime.txt`)
- A Discord Bot Token
- A Gemini API Key

### Installation

1.  **Clone the repository (or download the files):**
    If you haven't already, get the bot's code:
    ```bash
    # If you are using git
    # git clone <repository_url>
    # cd <repository_name>
    ```
2.  **Install dependencies:**
    Open a terminal in the bot's directory and run:
    ```bash
    pip install -r requirements.txt
    ```
    This will install `discord.py`, `google-generativeai`, and `python-dotenv`.

### Configuration

You need to set the following credentials and IDs. You can either set them as environment variables (recommended for security and flexibility) or directly modify the `bot.py` file.

**1. Discord Bot Token:**

   This token is required for the bot to connect to Discord.
   - **Environment Variable (Recommended):** Create a file named `.env` in the same directory as `bot.py` and add the following line:
     ```
     DISCORD_BOT_TOKEN='YOUR_DISCORD_BOT_TOKEN_HERE'
     ```
     Then, in `bot.py`, make sure the bot loads this variable:
     ```python
     # Near the top of bot.py, ensure os is imported
     import os
     from dotenv import load_dotenv
     load_dotenv() # Loads variables from .env file

     # ... other imports ...

     # At the end of bot.py, change how the bot is run:
     if __name__ == "__main__":
         DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
         if not DISCORD_BOT_TOKEN:
             print("Error: DISCORD_BOT_TOKEN not found. Please set it in your .env file or environment variables.")
         else:
             bot.run(DISCORD_BOT_TOKEN)
     ```
   - **Directly in `bot.py` (Less Secure):**
     ```python
     # At the end of bot.py:
     # bot.run(os.getenv(‘DISCORD_BOT_TOKEN’)) # Comment this out or remove
     bot.run('YOUR_DISCORD_BOT_TOKEN_HERE') # Replace with your actual token
     ```
   *How to get a token:* Go to the [Discord Developer Portal](https://discord.com/developers/applications), create a New Application, go to the "Bot" tab, click "Add Bot", and then copy the token. **Treat this token like a password!**

**2. Gemini API Key:**

   This key is required to use Google's Gemini API for generating summaries.
   - **Environment Variable (Recommended):** Add to your `.env` file:
     ```
     GEMINI_API_KEY='YOUR_GEMINI_API_KEY_HERE'
     ```
     Then, in `bot.py`, ensure it's loaded:
     ```python
     # Near the top of bot.py:
     # GEMINI_API_KEY = os.getenv(‘GEMINI_API_KEY’) # This line should already be there or similar
     GEMINI_API_KEY = os.getenv('GEMINI_API_KEY') # Ensure it uses os.getenv
     if GEMINI_API_KEY:
         genai.configure(api_key=GEMINI_API_KEY)
         model = genai.GenerativeModel('gemini-pro')
     else:
         print("Warning: GEMINI_API_KEY not found. AI summaries will be disabled. Using simple summary fallback.")
         model = None # Or handle appropriately
     ```
   - **Directly in `bot.py` (Less Secure):**
     ```python
     GEMINI_API_KEY = 'YOUR_GEMINI_API_KEY_HERE' # Replace with your actual key
     genai.configure(api_key=GEMINI_API_KEY)
     model = genai.GenerativeModel('gemini-pro')
     ```
   *How to get a key:* Visit [Google AI Studio](https://aistudio.google.com/app/apikey) to create and obtain your API key.

**3. Summary Channel ID:**

   This is the ID of the Discord channel where the bot will post the generated summaries.
   - **In `bot.py` (Default):**
     ```python
     SUMMARY_CHANNEL_ID = 123456789  # Replace with your desired summary channel ID
     ```
     You can also use the `!set_summary_channel <#channel_mention>` command once the bot is running (requires administrator permissions).
   *How to get a Channel ID:* In Discord, enable Developer Mode (User Settings -> App Settings -> Advanced). Then, right-click on the desired channel and select "Copy ID".

**4. Monitoring Channel IDs:**

   These are the IDs of the Discord channels that the bot will monitor for messages to summarize.
   - **In `bot.py` (Default):**
     ```python
     MONITORING_CHANNELS = [987654321, 876543210]  # Replace with your desired channel IDs, e.g., [112233445566778899, 998877665544332211]
     ```
   You can add or remove channel IDs from this list directly in the code, or use the bot commands `!add_monitor <#channel_mention>` and `!remove_monitor <#channel_mention>` (require administrator permissions).

**5. Other Settings (Optional in `bot.py`):**

   You can also adjust these settings near the top of `bot.py`:
   - `SUMMARY_INTERVAL = 60`: How often (in minutes) summaries are automatically generated.
   - `MAX_MESSAGES_PER_SUMMARY = 50`: The maximum number of recent messages to consider for each summary.

### Running the Bot

1.  **Ensure all configurations are set.**
2.  Open a terminal in the bot's directory.
3.  Run the bot:
    ```bash
    python bot.py
    ```

If you are deploying to a platform like Railway, the `Procfile` (`worker: python bot.py`) and `runtime.txt` will be used. Ensure your environment variables (`DISCORD_BOT_TOKEN`, `GEMINI_API_KEY`) are set in Railway's service settings.

## Commands

All commands are prefixed with `!`.

-   `!summary [channel]` - Generates a summary for the specified channel (e.g., `!summary #general`) or the current channel if none is provided. The channel must be in the monitoring list.
-   `!advanced_summary [channel]` - Generates a more detailed and structured summary for the specified or current channel. This uses a more comprehensive prompt for the Gemini API.
-   `!recent [limit]` - Shows the most recent messages (default 10, max usually around 25 due to Discord embed limits) in the current monitored channel. Example: `!recent 5`.
-   `!status` - Displays the bot's current operational status, including the summary channel, all monitored channels (with buffered message counts), summary interval, and AI model status.
-   `!set_summary_channel <#channel_mention>` - (Administrator only) Sets the channel where the bot will post automatic summaries. Example: `!set_summary_channel #bot-summaries`.
-   `!add_monitor <#channel_mention>` - (Administrator only) Adds a channel to the list of channels the bot monitors. Example: `!add_monitor #important-updates`.
-   `!remove_monitor <#channel_mention>` - (Administrator only) Removes a channel from the monitoring list. Example: `!remove_monitor #old-channel`.

## How it Works

1.  The bot listens to messages in channels listed in `MONITORING_CHANNELS`.
2.  Messages are stored in a temporary buffer (`message_buffer`).
3.  Periodically (defined by `SUMMARY_INTERVAL`) or when `!summary`/`!advanced_summary` is called:
    a.  The collected messages are sent to the Gemini API (if configured and available).
    b.  Gemini API processes the conversation and returns a summary based on the provided prompt.
    c.  If the Gemini API fails or is not configured, a simple keyword-based summary is generated as a fallback.
    d.  The summary is posted as an embed in the `SUMMARY_CHANNEL_ID`.
4.  The `MessageData` class structures message information, including author, content, timestamp, attachments, and embeds, to provide richer context for summaries.
5.  Various commands allow users to interact with the bot for on-demand summaries, status checks, and configuration changes.

## Deployment (Example: Railway)

1.  Ensure your `Procfile` is present and correct: `worker: python bot.py`.
2.  Ensure `runtime.txt` specifies your desired Python version (e.g., `python-3.11.x`).
3.  Push your code to a GitHub repository.
4.  In Railway:
    a.  Create a new project and deploy from your GitHub repository.
    b.  Go to your service settings -> Variables.
    c.  Add your `DISCORD_BOT_TOKEN` and `GEMINI_API_KEY` as environment variables.
    d.  If you've modified `bot.py` to take `SUMMARY_CHANNEL_ID` or `MONITORING_CHANNELS` from environment variables, add those too.
5.  Railway will use the `Procfile` to start the bot.

## `.gitignore`

The `.gitignore` file is included to prevent common unnecessary files or sensitive information from being committed to version control. This includes:
-   `.env` files (which should contain your secret tokens and keys)
-   Python bytecode and cache folders (`__pycache__/`, `*.pyc`, `*.pyo`, `*.pyd`)
-   Virtual environment folders (`env/`, `venv/`)
-   IDE configuration folders (`.vscode/`, `.idea/`)

**Important:** Always ensure your `.env` file (or any file containing sensitive credentials) is listed in `.gitignore` *before* your first commit if you are using a local `.env` file. If you accidentally commit sensitive data, you should invalidate the tokens/keys and clean your Git history.
