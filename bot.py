import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import asyncio
from collections import defaultdict
import google.generativeai as genai  # Gemini API
import os  # 環境変数用
from dotenv import load_dotenv  # .envファイル用
import time  # rate_limit用
from functools import wraps, lru_cache  # rate_limit用とcache用
import hashlib # cache用

load_dotenv()  # .envファイルから環境変数を読み込む

# Botの設定

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Gemini APIの設定

# 環境変数から読み込む場合:

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
# GEMINI_API_KEY = 'YOUR_GEMINI_API_KEY_HERE' # Hardcoded key removed
if not GEMINI_API_KEY:
    print("エラー: GEMINI_API_KEY が設定されていません。")
    # 必要に応じてここでプログラムを終了するか、デフォルトの動作を設定します。
else:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-pro')

# 設定項目

SUMMARY_CHANNEL_ID = 123456789  # 要約を投稿するチャンネルのID
MONITORING_CHANNELS = [987654321, 876543210]  # 監視するチャンネルのIDリスト
SUMMARY_INTERVAL = 60  # 要約を生成する間隔（分）
MAX_MESSAGES_PER_SUMMARY = 50  # 1回の要約に含める最大メッセージ数

# メッセージを保存する辞書

message_buffer = defaultdict(list)

class MessageData:
    def __init__(self, message):
        self.author = message.author.name
        self.content = message.content
        self.timestamp = message.created_at
        self.jump_url = message.jump_url
        self.channel_name = message.channel.name
        self.attachments = len(message.attachments)
        self.embeds = len(message.embeds)

# レート制限デコレーター
def rate_limit(calls_per_minute=60):
    def decorator(func):
        last_called = []

        @wraps(func)
        async def wrapper(*args, **kwargs):
            now = time.time()
            # 古いタイムスタンプをフィルタリング
            last_called[:] = [t for t in last_called if now - t < 60]

            if len(last_called) >= calls_per_minute:
                # 最初の呼び出しからの経過時間に基づいてスリープ時間を計算
                sleep_time = 60 - (now - last_called[0])
                if sleep_time > 0: # Ensure sleep_time is positive
                    print(f"Rate limit reached. Sleeping for {sleep_time:.2f} seconds.")
                    await asyncio.sleep(sleep_time) # Use asyncio.sleep for async functions

            last_called.append(time.time()) # Record current call time
            # Correctly call sync or async function
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                # For synchronous functions, run in executor to avoid blocking asyncio loop
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

        return wrapper
    return decorator

def create_summary_embed(messages, channel_name):
    """要約用のEmbedを作成"""
    embed = discord.Embed(
        title=f"📋 {channel_name} の要約",
        description=f"過去{SUMMARY_INTERVAL}分間のメッセージ要約",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )

    # メッセージの統計
    total_messages = len(messages)
    unique_authors = len(set(msg.author for msg in messages))

    embed.add_field(
        name="📊 統計",
        value=f"メッセージ数: {total_messages}\n投稿者数: {unique_authors}",
        inline=False
    )

    # 主要なトピック（Gemini APIを使用）
    topics = summarize_messages(messages)
    if topics:
        embed.add_field(
            name="🎯 主要なトピック",
            value=topics[:1024],  # Embedフィールドの文字数制限
            inline=False
        )

    # アクティブな投稿者TOP3
    author_counts = defaultdict(int)
    for msg in messages:
        author_counts[msg.author] += 1

    top_authors = sorted(author_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    if top_authors:
        author_text = "\n".join([f"{i+1}. {author}: {count}件"
                                for i, (author, count) in enumerate(top_authors)])
        embed.add_field(
            name="👥 アクティブな投稿者",
            value=author_text,
            inline=True
        )

    # 最新のメッセージ（最大5件）
    recent_messages = messages[-5:] if len(messages) > 5 else messages
    if recent_messages:
        recent_text = []
        for msg in recent_messages:
            text = f"**{msg.author}**: {msg.content[:50]}..."
            if msg.attachments > 0:
                text += f" 📎({msg.attachments})"
            text += f"\n[→ 元の投稿]({msg.jump_url})"
            recent_text.append(text)

        embed.add_field(
            name="💬 最新のメッセージ",
            value="\n\n".join(recent_text[:5]),
            inline=False
        )

    return embed

# Helper function to create a hash for caching from message objects
def create_message_hash(messages: list[MessageData]) -> str:
    """Creates a SHA256 hash from a list of MessageData objects for caching."""
    hasher = hashlib.sha256()
    # Sort messages by timestamp to ensure consistent hash for the same set of messages.
    # Using specific attributes that define the content relevant for summary.
    sorted_messages = sorted(messages, key=lambda m: m.timestamp)
    for msg in sorted_messages:
        data_to_hash = f"{msg.author}:{msg.content}:{msg.timestamp}:{msg.attachments}:{msg.embeds}"
        hasher.update(data_to_hash.encode('utf-8'))
    return hasher.hexdigest()

# --- Synchronous Summarization with Caching ---
@rate_limit(calls_per_minute=60) # Rate limit before caching
@lru_cache(maxsize=100)
def _cached_summarize_messages_api(message_content_hash: str, conversation_text: str):
    """Internal function to call Gemini API for synchronous summarization, with caching and rate limiting."""
    if not conversation_text:
        return "要約するメッセージがありません。"
    try:
        prompt = f"""以下のDiscordの会話を分析して、簡潔な要約を作成してください：

会話内容：
{conversation_text}

以下の点を含めて要約してください：
1. 主要なトピックや話題
2. 重要な決定事項や合意事項
3. 質問と回答のペア
4. 注目すべき情報や発言
要約は簡潔で分かりやすく、箇条書きを使って構造化してください。"""
        response = model.generate_content(prompt)
        if response.text:
            return response.text[:1024]
        else:
            return "要約の生成に失敗しました。"
    except Exception as e:
        print(f"Gemini API エラー (_cached_summarize_messages_api): {e}")
        # This cached function cannot call generate_simple_summary directly as it lacks MessageData list
        raise # Re-raise the exception to be handled by the caller, allowing fallback

def summarize_messages(messages: list[MessageData]):
    """メッセージを要約する関数（Gemini APIを使用）, now with caching and rate limiting."""
    if not messages:
        return "要約するメッセージがありません。"

    message_texts = []
    for msg in messages:
        text = f"{msg.author}: {msg.content}"
        if msg.attachments > 0:
            text += f" [添付ファイル: {msg.attachments}件]"
        if msg.embeds > 0:
            text += f" [Embed: {msg.embeds}件]"
        message_texts.append(text)
    conversation_for_prompt = "\n".join(message_texts)

    # Create a hash of the MessageData objects themselves for the cache key
    data_hash = create_message_hash(messages)

    try:
        # Call the internal cached and rate-limited function
        return _cached_summarize_messages_api(data_hash, conversation_for_prompt)
    except Exception as e:
        # If _cached_summarize_messages_api raises an error (e.g., API error after rate limit/cache miss)
        print(f"Error in summarize_messages calling cached API: {e}")
        return generate_simple_summary(messages) # Fallback to simple summary

# --- Asynchronous Summarization with Caching ---
@rate_limit(calls_per_minute=60) # Rate limit before caching
@lru_cache(maxsize=100)
async def _cached_async_summarize_messages_api(message_content_hash: str, conversation_text: str):
    """Internal async function to call Gemini API, with caching and rate limiting."""
    if not conversation_text:
        return "要約するメッセージがありません。"
    try:
        prompt = f"""あなたはDiscordサーバーの会話を分析する専門家です。
以下の会話を分析して、包括的な要約を作成してください。
会話内容：
{conversation_text}
要約には以下を含めてください：
1. **主要トピック**: 会話の中心となった話題
2. **重要な情報**: 共有された重要な情報やリンク
3. **決定事項**: 何か決定されたことがあれば記載
4. **アクションアイテム**: 誰かが行うべきタスク
5. **質問と回答**: 解決された質問と未解決の質問
6. **全体的な雰囲気**: 会話のトーンや感情
Markdown形式で構造化して出力してください。"""

        # model.generate_content is synchronous, run in executor for async context
        response = await asyncio.get_event_loop().run_in_executor(
            None, model.generate_content, prompt
        )
        if response.text:
            return response.text[:1024]
        else:
            return "要約の生成に失敗しました。"
    except Exception as e:
        print(f"Gemini API エラー (_cached_async_summarize_messages_api): {e}")
        raise # Re-raise to be handled by caller

async def async_summarize_messages(messages: list[MessageData]):
    """非同期版の要約関数（より高度な処理用）, now with caching and rate limiting."""
    if not messages:
        return "要約するメッセージがありません。"

    message_texts = []
    for msg in messages:
        text = f"{msg.author}: {msg.content}"
        if msg.attachments > 0:
            text += f" [添付ファイル: {msg.attachments}件]"
        if msg.embeds > 0:
            text += f" [Embed: {msg.embeds}件]"
        message_texts.append(text)
    conversation_for_prompt = "\n".join(message_texts)

    data_hash = create_message_hash(messages)

    try:
        return await _cached_async_summarize_messages_api(data_hash, conversation_for_prompt)
    except Exception as e:
        print(f"Error in async_summarize_messages calling cached API: {e}")
        return generate_simple_summary(messages) # Fallback

# generate_simple_summary was here, it's fine, it's used by the new functions.
# The duplicated old summarize_messages logic (which was a block of loose code) and
# the duplicated async_summarize_messages function definition are removed by this search and replace.

def generate_simple_summary(messages):
    """Gemini APIが使えない場合の簡易要約"""
    topics = []
    content_words = defaultdict(int)

    for msg in messages:
        words = msg.content.lower().split()
        for word in words:
            if len(word) > 4:  # 4文字以上の単語をカウント
                content_words[word] += 1

    # 頻出単語TOP5
    top_words = sorted(content_words.items(), key=lambda x: x[1], reverse=True)[:5]
    if top_words:
        return "頻出キーワード: " + ", ".join([word for word, _ in top_words])

    return "特定のトピックは見つかりませんでした。"

# The duplicated async_summarize_messages function that was here has been removed.
# The current async_summarize_messages (defined earlier with caching) is the correct one.

@bot.event
async def on_ready():
    print(f'{bot.user} がログインしました！')
    summary_task.start()

@bot.event
async def on_message(message):
    # Bot自身のメッセージは無視
    if message.author.bot:
        return

    # 監視対象チャンネルのメッセージを保存
    if message.channel.id in MONITORING_CHANNELS:
        message_data = MessageData(message)
        message_buffer[message.channel.id].append(message_data)

        # バッファサイズの制限（メモリ対策）
        if len(message_buffer[message.channel.id]) > MAX_MESSAGES_PER_SUMMARY * 2:
            message_buffer[message.channel.id] = message_buffer[message.channel.id][-MAX_MESSAGES_PER_SUMMARY:]

    await bot.process_commands(message)

@tasks.loop(minutes=SUMMARY_INTERVAL)
async def summary_task():
    """定期的に要約を生成して投稿"""
    summary_channel = bot.get_channel(SUMMARY_CHANNEL_ID)
    if not summary_channel:
        print("要約チャンネルが見つかりません")
        return

    for channel_id in MONITORING_CHANNELS:
        if channel_id in message_buffer and message_buffer[channel_id]:
            channel = bot.get_channel(channel_id)
            if not channel:
                continue

            messages = message_buffer[channel_id][-MAX_MESSAGES_PER_SUMMARY:]

            if messages:
                embed = create_summary_embed(messages, channel.name)
                await summary_channel.send(embed=embed)

                # 処理済みメッセージをクリア
                message_buffer[channel_id].clear()

@bot.command(name='summary')
async def manual_summary(ctx, channel: discord.TextChannel = None):
    """手動で要約を生成するコマンド"""
    if not channel:
        channel = ctx.channel

    if channel.id not in MONITORING_CHANNELS:
        await ctx.send("このチャンネルは監視対象ではありません。")
        return

    if channel.id not in message_buffer or not message_buffer[channel.id]:
        await ctx.send("要約するメッセージがありません。")
        return

    messages = message_buffer[channel.id][-MAX_MESSAGES_PER_SUMMARY:]
    embed = create_summary_embed(messages, channel.name)
    await ctx.send(embed=embed)

@bot.command(name='recent')
async def recent_messages(ctx, limit: int = 10):
    """最近のメッセージを表示"""
    if ctx.channel.id not in MONITORING_CHANNELS:
        await ctx.send("このチャンネルは監視対象ではありません。")
        return

    messages = message_buffer[ctx.channel.id][-limit:]
    if not messages:
        await ctx.send("表示するメッセージがありません。")
        return

    embed = discord.Embed(
        title=f"最新の{len(messages)}件のメッセージ",
        color=discord.Color.green()
    )

    for msg in messages:
        embed.add_field(
            name=f"{msg.author} - {msg.timestamp.strftime('%H:%M')}",
            value=f"{msg.content[:100]}{'...' if len(msg.content) > 100 else ''}\n[元の投稿]({msg.jump_url})",
            inline=False
        )

    await ctx.send(embed=embed)

@bot.command(name='set_summary_channel')
@commands.has_permissions(administrator=True)
async def set_summary_channel(ctx, channel: discord.TextChannel):
    """要約投稿チャンネルを設定"""
    global SUMMARY_CHANNEL_ID
    SUMMARY_CHANNEL_ID = channel.id
    await ctx.send(f"要約チャンネルを {channel.mention} に設定しました。")

@bot.command(name='add_monitor')
@commands.has_permissions(administrator=True)
async def add_monitor_channel(ctx, channel: discord.TextChannel):
    """監視チャンネルを追加"""
    if channel.id not in MONITORING_CHANNELS:
        MONITORING_CHANNELS.append(channel.id)
        await ctx.send(f"{channel.mention} を監視対象に追加しました。")
    else:
        await ctx.send(f"{channel.mention} は既に監視対象です。")

@bot.command(name='remove_monitor')
@commands.has_permissions(administrator=True)
async def remove_monitor_channel(ctx, channel: discord.TextChannel):
    """監視チャンネルを削除"""
    if channel.id in MONITORING_CHANNELS:
        MONITORING_CHANNELS.remove(channel.id)
        if channel.id in message_buffer:
            del message_buffer[channel.id]
        await ctx.send(f"{channel.mention} を監視対象から削除しました。")
    else:
        await ctx.send(f"{channel.mention} は監視対象ではありません。")

@bot.command(name='status')
async def bot_status(ctx):
    """Botの状態を表示"""
    embed = discord.Embed(
        title="Bot Status",
        color=discord.Color.blue()
    )

    summary_ch = bot.get_channel(SUMMARY_CHANNEL_ID)
    embed.add_field(
        name="要約チャンネル",
        value=summary_ch.mention if summary_ch else "未設定",
        inline=False
    )

    monitor_channels = []
    for ch_id in MONITORING_CHANNELS:
        ch = bot.get_channel(ch_id)
        if ch:
            count = len(message_buffer.get(ch_id, []))
            monitor_channels.append(f"{ch.mention} ({count}件)")

    embed.add_field(
        name="監視中のチャンネル",
        value="\n".join(monitor_channels) if monitor_channels else "なし",
        inline=False
    )

    embed.add_field(
        name="要約間隔",
        value=f"{SUMMARY_INTERVAL}分",
        inline=True
    )

    embed.add_field(
        name="AI要約",
        value="Gemini Pro 使用中" if GEMINI_API_KEY else "未設定",
        inline=True
    )

    await ctx.send(embed=embed)

@bot.command(name='advanced_summary')
async def advanced_summary(ctx, channel: discord.TextChannel = None):
    """より詳細な要約を生成（非同期版）"""
    if not channel:
        channel = ctx.channel

    if channel.id not in MONITORING_CHANNELS:
        await ctx.send("このチャンネルは監視対象ではありません。")
        return

    if channel.id not in message_buffer or not message_buffer[channel.id]:
        await ctx.send("要約するメッセージがありません。")
        return

    # 処理中メッセージ
    processing_msg = await ctx.send("🔄 詳細な要約を生成中...")

    try:
        messages = message_buffer[channel.id][-MAX_MESSAGES_PER_SUMMARY:]

        # 非同期版の要約を使用
        summary = await async_summarize_messages(messages)

        embed = discord.Embed(
            title=f"📊 {channel.name} の詳細要約",
            description=summary[:4096],  # Embed全体の文字数制限
            color=discord.Color.gold(),
            timestamp=datetime.utcnow()
        )

        # メッセージ統計
        embed.add_field(
            name="📈 統計情報",
            value=f"分析メッセージ数: {len(messages)}\n"
                  f"期間: 過去{SUMMARY_INTERVAL}分間\n"
                  f"投稿者数: {len(set(msg.author for msg in messages))}",
            inline=False
        )

        await processing_msg.delete()
        await ctx.send(embed=embed)

    except Exception as e:
        await processing_msg.edit(content=f"❌ エラーが発生しました: {str(e)}")

# Botを起動

if __name__ == "__main__":
    DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    if not DISCORD_BOT_TOKEN:
        print("エラー: DISCORD_BOT_TOKEN が設定されていません。")
    else:
        bot.run(DISCORD_BOT_TOKEN)
