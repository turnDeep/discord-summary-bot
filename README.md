# Discord Summary Bot

This bot monitors specified Discord channels and periodically generates summaries of the conversations using the Gemini API. It can also provide manual summaries, display recent messages, and more.

## Features

- Automatic summaries at configurable intervals.
- Manual summary generation via command.
- Customizable list of channels to monitor.
- Identification of key topics, active users, and recent messages in summaries.
- Powered by Google's latest Gemini models (default: Gemini 2.5 Pro)
- Fallback to simple keyword-based summary if Gemini API fails or is not configured.
- Commands to manage monitored channels and bot settings.
- Advanced, more detailed summaries using an asynchronous Gemini API call.
- Environment variable support for most configurations (e.g., API keys, channel IDs, summary interval).
- Regular cleanup of old message data and garbage collection for better memory management.
- Logic to determine if a summary is needed based on message count, unique authors, and content length.
- API usage tracking and system resource monitoring commands for administrators.
- Dynamic model switching via command (administrator only)

## Requirements

- Python 3.11+ (Recommended: Python 3.11.x as specified in `runtime.txt`)
- Discord Bot Token
- Google API Key (for Gemini)
- Latest Google GenAI SDK (`google-genai>=0.8.0`)

## Setup and Configuration

### Installation

1. **Clone the repository (or download the files):**
   ```bash
   # If you are using git
   # git clone <repository_url>
   # cd <repository_name>
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   This will install `discord.py`, `google-genai` (the latest Google Gen AI SDK), `python-dotenv`, and `psutil`.

### Configuration

Configure the bot using the `.env` file. Copy the template below and fill in your credentials:

```env
# Discord Bot Token
# Discord Developer Portal (https://discord.com/developers/applications) から取得
DISCORD_BOT_TOKEN=your_discord_bot_token

# Google API Key for Gemini
# Google AI Studio (https://makersuite.google.com/app/apikey) から取得
GOOGLE_API_KEY=your_google_api_key

# オプション設定（設定しない場合はデフォルト値が使用されます）

# 使用するGeminiモデル デフォルト: gemini-2.5-pro
# 他のオプション: gemini-2.0-flash-001, gemini-2.0-pro など
GEMINI_MODEL=gemini-2.5-pro

# 要約を投稿するチャンネルのID（必須）
# Discordで右クリック→「IDをコピー」で取得可能
SUMMARY_CHANNEL_ID=123456789012345678

# 監視するチャンネルのIDリスト（カンマ区切り）
MONITORING_CHANNELS=111111111111111111,222222222222222222

# 要約を生成する間隔（分）デフォルト: 60
SUMMARY_INTERVAL=60

# 1回の要約に含める最大メッセージ数 デフォルト: 50
MAX_MESSAGES_PER_SUMMARY=50
```

**Getting the credentials:**

1. **Discord Bot Token:**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Create a New Application
   - Go to the "Bot" tab
   - Click "Add Bot"
   - Copy the token

2. **Google API Key:**
   - Visit [Google AI Studio](https://aistudio.google.com/app/apikey)
   - Create and obtain your API key

3. **Channel IDs:**
   - In Discord, enable Developer Mode (User Settings → App Settings → Advanced)
   - Right-click on the desired channel and select "Copy ID"

### Running the Bot

1. **Ensure all configurations are set in the `.env` file**
2. **Run the bot:**
   ```bash
   python bot.py
   ```

## Commands

All commands are prefixed with `!`.

- `!summary [channel]` - Generates a summary for the specified channel (e.g., `!summary #general`) or the current channel if none is provided.
- `!advanced_summary [channel]` - Generates a more detailed and structured summary using the Gemini API's advanced capabilities.
- `!recent [limit]` - Shows the most recent messages (default 10) in the current monitored channel.
- `!status` - Displays the bot's current operational status, including the summary channel, monitored channels, summary interval, AI model status, and uptime.
- `!set_summary_channel <#channel_mention>` - (Administrator only) Sets the channel where the bot will post automatic summaries.
- `!add_monitor <#channel_mention>` - (Administrator only) Adds a channel to the monitoring list.
- `!remove_monitor <#channel_mention>` - (Administrator only) Removes a channel from the monitoring list.
- `!set_model <model_name>` - (Administrator only) Changes the Gemini model being used (e.g., `!set_model gemini-2.0-flash-001`).
- `!api_usage` - (Administrator only) Displays the current usage of the Gemini API including daily usage and predictions.
- `!system` - (Administrator only) Shows system resource usage including CPU, memory, and the current model being used.

## Available Models

The bot supports various Gemini models. The default is `gemini-2.5-pro`, but you can use:

- `gemini-2.5-pro` (Default - Most advanced)
- `gemini-2.0-flash-001` (Faster, lighter)
- `gemini-2.0-pro` (Balanced performance)
- Other models as they become available

You can change the model using the `!set_model` command or by setting the `GEMINI_MODEL` environment variable.

## How it Works

1. The bot listens to messages in channels listed in `MONITORING_CHANNELS`.
2. Messages are stored in a temporary buffer with metadata (author, content, timestamp, etc.).
3. Periodically (defined by `SUMMARY_INTERVAL`) or when `!summary`/`!advanced_summary` is called:
   - The bot checks if a summary is needed based on message count and author diversity
   - If needed, messages are sent to the Gemini API for analysis
   - The API processes the conversation and returns a structured summary
   - The summary is posted as an embed in the `SUMMARY_CHANNEL_ID`
4. A background cleanup task runs every 6 hours to manage memory usage
5. All API calls are tracked for usage monitoring

## Deployment (Example: Railway)

1. Ensure your `Procfile` is present: `worker: python bot.py`
2. Ensure `runtime.txt` specifies Python version: `python-3.11.x`
3. Push your code to a GitHub repository
4. In Railway:
   - Create a new project and deploy from your GitHub repository
   - Go to your service settings → Variables
   - Add all environment variables from your `.env` file
5. Railway will use the `Procfile` to start the bot

## Latest SDK Features

This bot uses the latest Google GenAI SDK (`google-genai`) which provides:

- Improved performance and reliability
- Better async support with `client.aio.models.generate_content()`
- Enhanced configuration options with `types.GenerateContentConfig`
- Support for the latest Gemini models including Gemini 2.5 Pro
- More robust error handling

## Security Notes

- Never commit your `.env` file to version control
- Keep your API keys and bot tokens secure
- The `.gitignore` file is configured to exclude sensitive files
- Regularly rotate your API keys for security

## Contributing

Feel free to open issues or submit pull requests to improve the bot. Make sure to test your changes thoroughly before submitting.

## License

This project is provided as-is for educational and personal use.