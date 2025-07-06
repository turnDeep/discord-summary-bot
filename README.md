# Discord Summary Bot

This bot monitors specified Discord channels and periodically generates summaries of the conversations using the Gemini API. It can also provide manual summaries, display recent messages, and more.

## Features

- Automatic summaries at configurable intervals.
- Manual summary generation via command.
- Customizable list of channels to monitor.
- Identification of key topics, active users, and recent messages in summaries.
- Fallback to simple keyword-based summary if Gemini API (currently `gemini-1.5-flash`) fails or is not configured.
- Commands to manage monitored channels and bot settings.
- Advanced, more detailed summaries using an asynchronous Gemini API call.
- Environment variable support for most configurations (e.g., API keys, channel IDs, summary interval).
- Regular cleanup of old message data and garbage collection for better memory management.
- Logic to determine if a summary is needed based on message count, unique authors, and content length.
- API usage tracking and system resource monitoring commands for administrators.

## Setup and Configuration

To get the bot running, you need to configure a few things.

### Prerequisites

- Python 3.7+ (Recommended: Python 3.11.x as specified in `runtime.txt`)
- A Discord Bot Token
- A Google API Key (for Gemini)

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
    This will install `discord.py`, `google.genai` (the new Google Gen AI SDK), `python-dotenv`, and `psutil`.

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
     GOOGLE_API_KEY='YOUR_GOOGLE_API_KEY_HERE'
     ```
     Then, in `bot.py`, ensure it's loaded:
     ```python
     # Near the top of bot.py:
     GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY') # Ensure it uses os.getenv
     if GOOGLE_API_KEY:
         genai.configure(api_key=GOOGLE_API_KEY) # Updated SDK usage
         # Note: Model selection is now typically done when calling the generation method
         # client = genai.Client(api_key=GOOGLE_API_KEY) # client initialization
         # model = client.models.get('gemini-1.5-flash') # or similar, depending on SDK version
     else:
         print("Warning: GOOGLE_API_KEY not found. AI summaries will be disabled. Using simple summary fallback.")
         # model = None # Or handle appropriately
     ```
   - **Directly in `bot.py` (Less Secure):**
     ```python
     GOOGLE_API_KEY = 'YOUR_GOOGLE_API_KEY_HERE' # Replace with your actual key
     genai.configure(api_key=GOOGLE_API_KEY)
     # client = genai.Client(api_key=GOOGLE_API_KEY)
     # model = client.models.get('gemini-1.5-flash')
     ```
   *How to get a key:* Visit [Google AI Studio](https://aistudio.google.com/app/apikey) to create and obtain your API key. The bot currently uses the `gemini-1.5-flash` model.

**3. Summary Channel ID:**

   This is the ID of the Discord channel where the bot will post the generated summaries.
   - **In `bot.py` (Default):**
     ```python
     SUMMARY_CHANNEL_ID = 123456789  # Replace with your desired summary channel ID
     ```
     You can also use the `!set_summary_channel <#channel_mention>` command once the bot is running (requires administrator permissions).
   *How to get a Channel ID:* In Discord, enable Developer Mode (User Settings -> App Settings -> Advanced). Then, right-click on the desired channel and select "Copy ID".
   This setting can also be configured via the `SUMMARY_CHANNEL_ID` environment variable (e.g., `SUMMARY_CHANNEL_ID='YOUR_SUMMARY_CHANNEL_ID'`).

**4. Monitoring Channel IDs:**

   These are the IDs of the Discord channels that the bot will monitor for messages to summarize.
   - **Environment Variable (Recommended):** Set `MONITORING_CHANNELS` as a comma-separated string of channel IDs in your `.env` file or environment variables:
     ```
     MONITORING_CHANNELS='YOUR_CHANNEL_ID_1,YOUR_CHANNEL_ID_2'
     ```
     If this environment variable is not set, the bot will default to an empty list, and you will need to add channels using bot commands.
   - **In `bot.py` (Fallback if environment variable is not set):**
     ```python
     MONITORING_CHANNELS = [] # Default is empty, e.g., [112233445566778899, 998877665544332211]
     ```
   You can use the bot commands `!add_monitor <#channel_mention>` and `!remove_monitor <#channel_mention>` (require administrator permissions) to manage this list dynamically.

**5. Other Settings (Configurable via Environment Variables or in `bot.py`):**

   These settings can be adjusted either directly in `bot.py` or preferably through environment variables. Environment variables will override values set in `bot.py`.
   - `SUMMARY_INTERVAL`: How often (in minutes) summaries are automatically generated. Default: `60`.
     - Environment Variable: `SUMMARY_INTERVAL='30'`
     - In `bot.py`: `SUMMARY_INTERVAL = int(os.getenv('SUMMARY_INTERVAL', 60))`
   - `MAX_MESSAGES_PER_SUMMARY`: The maximum number of recent messages to consider for each summary. Default: `50`.
     - Environment Variable: `MAX_MESSAGES_PER_SUMMARY='100'`
     - In `bot.py`: `MAX_MESSAGES_PER_SUMMARY = int(os.getenv('MAX_MESSAGES_PER_SUMMARY', 50))`
   - `MAX_BUFFER_SIZE`: The maximum number of messages to keep in the buffer for each channel before older messages are discarded. Default: `100`.
     - Environment Variable: `MAX_BUFFER_SIZE='200'`
     - In `bot.py`: `MAX_BUFFER_SIZE = int(os.getenv('MAX_BUFFER_SIZE', 100))`

### Running the Bot

1.  **Ensure all configurations are set.**
2.  Open a terminal in the bot's directory.
3.  Run the bot:
    ```bash
    python bot.py
    ```

If you are deploying to a platform like Railway, the `Procfile` (`worker: python bot.py`) and `runtime.txt` will be used. Ensure your environment variables (`DISCORD_BOT_TOKEN`, `GOOGLE_API_KEY`, and other optional settings like `SUMMARY_CHANNEL_ID`, `MONITORING_CHANNELS`, etc.) are set in Railway's service settings.

## Commands

All commands are prefixed with `!`.

-   `!summary [channel]` - Generates a summary for the specified channel (e.g., `!summary #general`) or the current channel if none is provided. The channel must be in the monitoring list.
-   `!advanced_summary [channel]` - Generates a more detailed and structured summary for the specified or current channel. This uses a more comprehensive prompt for the Gemini API.
-   `!recent [limit]` - Shows the most recent messages (default 10, max usually around 25 due to Discord embed limits) in the current monitored channel. Example: `!recent 5`.
-   `!status` - Displays the bot's current operational status, including the summary channel, all monitored channels (with buffered message counts), summary interval, AI model status, and uptime.
-   `!set_summary_channel <#channel_mention>` - (Administrator only) Sets the channel where the bot will post automatic summaries. Example: `!set_summary_channel #bot-summaries`.
-   `!add_monitor <#channel_mention>` - (Administrator only) Adds a channel to the list of channels the bot monitors. Example: `!add_monitor #important-updates`.
-   `!remove_monitor <#channel_mention>` - (Administrator only) Removes a channel from the monitoring list. Example: `!remove_monitor #old-channel`.
-   `!api_usage` - (Administrator only) Displays the current usage of the Gemini API for the day, including the number of calls made, the percentage used, and the remaining calls. It also provides a prediction for the total daily usage.
-   `!system` - (Administrator only) Shows the system resource usage of the server where the bot is running, including CPU usage, memory usage (total and bot-specific), Python version, and bot uptime.

## How it Works

1.  The bot listens to messages in channels listed in `MONITORING_CHANNELS`.
2.  Messages are stored in a temporary buffer (`message_buffer`).
3.  Periodically (defined by `SUMMARY_INTERVAL`) or when `!summary`/`!advanced_summary` is called:
    a.  The bot first checks if a summary is needed based on factors like message count and diversity of authors using the `needs_summary` logic.
    b.  If a summary is needed, the collected messages are sent to the Gemini API (model `gemini-1.5-flash`, using the `google.genai` SDK) if configured and available.
    c.  The Gemini API processes the conversation and returns a summary. The `!advanced_summary` command uses a more detailed prompt and an asynchronous API call for a more comprehensive result.
    d.  If the Gemini API fails or is not configured, a simple keyword-based summary is generated as a fallback.
    e.  The summary is posted as an embed in the `SUMMARY_CHANNEL_ID`.
4.  The `MessageData` class structures message information, including author, content, timestamp, jump URL, channel name, and counts of attachments/embeds, to provide richer context for summaries.
5.  Various commands allow users to interact with the bot for on-demand summaries, status checks, configuration changes, API usage viewing, and system resource monitoring.
6.  A background task (`cleanup_task`) runs periodically (e.g., every 6 hours) to clear out message buffers for channels no longer being monitored and to trigger Python's garbage collector, helping to manage memory usage.

## Deployment (Example: Railway)

1.  Ensure your `Procfile` is present and correct: `worker: python bot.py`.
2.  Ensure `runtime.txt` specifies your desired Python version (e.g., `python-3.11.x`).
3.  Push your code to a GitHub repository.
4.  In Railway:
    a.  Create a new project and deploy from your GitHub repository.
    b.  Go to your service settings -> Variables.
    c.  Add your `DISCORD_BOT_TOKEN` and `GOOGLE_API_KEY` as environment variables.
    d.  If you intend to use environment variables for other settings like `SUMMARY_CHANNEL_ID`, `MONITORING_CHANNELS`, `SUMMARY_INTERVAL`, `MAX_MESSAGES_PER_SUMMARY`, or `MAX_BUFFER_SIZE`, add those here as well.
5.  Railway will use the `Procfile` to start the bot.

## `.gitignore`

The `.gitignore` file is included to prevent common unnecessary files or sensitive information from being committed to version control. This includes:
-   `.env` files (which should contain your secret tokens and keys)
-   Python bytecode and cache folders (`__pycache__/`, `*.pyc`, `*.pyo`, `*.pyd`)
-   Virtual environment folders (`env/`, `venv/`)
-   IDE configuration folders (`.vscode/`, `.idea/`)

**Important:** Always ensure your `.env` file (or any file containing sensitive credentials) is listed in `.gitignore` *before* your first commit if you are using a local `.env` file. If you accidentally commit sensitive data, you should invalidate the tokens/keys and clean your Git history.
