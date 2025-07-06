import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import asyncio
from collections import defaultdict
from google import genai  # 新しいGoogle Gen AI SDK
from google.genai import types
import os
from dotenv import load_dotenv
import psutil
import platform
import gc

# .envファイルから環境変数を読み込み
load_dotenv()

# 環境変数から設定を読み込み
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# 環境変数が設定されているか確認
if not DISCORD_BOT_TOKEN:
    raise ValueError("DISCORD_BOT_TOKENが設定されていません。.envファイルを確認してください。")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEYが設定されていません。.envファイルを確認してください。")

# Google Gen AI SDKのクライアント作成
client = genai.Client(api_key=GOOGLE_API_KEY)

# Botの設定
intents = discord.Intents.default()
intents.message_content = True  # メッセージ内容を読むために必要
intents.guilds = True
# intents.members = True  # これは今回のBotでは不要なのでコメントアウト

bot = commands.Bot(command_prefix='!', intents=intents)

# 設定項目（環境変数から読み込み可能）
SUMMARY_CHANNEL_ID = int(os.getenv('SUMMARY_CHANNEL_ID', 0))  # 要約を投稿するチャンネルのID
MONITORING_CHANNELS = os.getenv('MONITORING_CHANNELS', '').split(',') if os.getenv('MONITORING_CHANNELS') else []  # 監視するチャンネルのIDリスト
MONITORING_CHANNELS = [int(ch) for ch in MONITORING_CHANNELS if ch]  # 文字列を整数に変換
SUMMARY_INTERVAL = int(os.getenv('SUMMARY_INTERVAL', 60))  # 要約を生成する間隔（分）
MAX_MESSAGES_PER_SUMMARY = int(os.getenv('MAX_MESSAGES_PER_SUMMARY', 50))  # 1回の要約に含める最大メッセージ数
MAX_BUFFER_SIZE = 100  # メッセージバッファの最大サイズ

# メッセージを保存する辞書
message_buffer = defaultdict(list)

# API使用量追跡用
daily_api_calls = 0
last_reset_date = datetime.now().date()

class MessageData:
    def __init__(self, message):
        self.author = message.author.name
        self.content = message.content
        self.timestamp = message.created_at
        self.jump_url = message.jump_url
        self.channel_name = message.channel.name
        self.attachments = len(message.attachments)
        self.embeds = len(message.embeds)

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

def summarize_messages(messages):
    """メッセージを要約する関数（Google Gen AI SDKを使用）"""
    global daily_api_calls, last_reset_date
    
    # 日付が変わったらAPI使用量をリセット
    if datetime.now().date() != last_reset_date:
        daily_api_calls = 0
        last_reset_date = datetime.now().date()
    
    if not messages:
        return "要約するメッセージがありません。"
    
    try:
        # メッセージを整形
        message_texts = []
        for msg in messages:
            text = f"{msg.author}: {msg.content}"
            if msg.attachments > 0:
                text += f" [添付ファイル: {msg.attachments}件]"
            if msg.embeds > 0:
                text += f" [Embed: {msg.embeds}件]"
            message_texts.append(text)
        
        # 会話履歴を結合
        conversation = "\n".join(message_texts)
        
        # プロンプトを構築
        prompt = f"""以下のDiscordの会話を分析して、簡潔な要約を作成してください：

会話内容：
{conversation}

以下の点を含めて要約してください：
1. 主要なトピックや話題
2. 重要な決定事項や合意事項
3. 質問と回答のペア
4. 注目すべき情報や発言

要約は簡潔で分かりやすく、箇条書きを使って構造化してください。"""
        
        # APIを呼び出し
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt,
            generation_config=types.GenerateContentConfig( # 'config' を 'generation_config' に変更
                temperature=0.3,
                max_output_tokens=1000,
            ),
        )
        
        daily_api_calls += 1
        
        # レスポンスのテキストを取得
        if response.text:
            return response.text[:1024]  # Embedフィールドの文字数制限
        else:
            return "要約の生成に失敗しました。"
            
    except Exception as e:
        print(f"Gemini API エラー: {e}")
        return generate_simple_summary(messages)

async def async_summarize_messages(messages):
    """非同期版の要約関数（より高度な処理用）"""
    global daily_api_calls, last_reset_date
    
    # 日付が変わったらAPI使用量をリセット
    if datetime.now().date() != last_reset_date:
        daily_api_calls = 0
        last_reset_date = datetime.now().date()
    
    if not messages:
        return "要約するメッセージがありません。"
    
    try:
        # メッセージを整形
        message_texts = []
        for msg in messages:
            text = f"{msg.author}: {msg.content}"
            if msg.attachments > 0:
                text += f" [添付ファイル: {msg.attachments}件]"
            if msg.embeds > 0:
                text += f" [Embed: {msg.embeds}件]"
            message_texts.append(text)
        
        conversation = "\n".join(message_texts)
        
        # より詳細なプロンプト
        prompt = f"""あなたはDiscordサーバーの会話を分析する専門家です。
以下の会話を分析して、包括的な要約を作成してください。

会話内容：
{conversation}

要約には以下を含めてください：
1. **主要トピック**: 会話の中心となった話題
2. **重要な情報**: 共有された重要な情報やリンク
3. **決定事項**: 何か決定されたことがあれば記載
4. **アクションアイテム**: 誰かが行うべきタスク
5. **質問と回答**: 解決された質問と未解決の質問
6. **全体的な雰囲気**: 会話のトーンや感情

Markdown形式で構造化して出力してください。"""
        
        # 非同期でAPIを呼び出し
        response = await client.aio.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt,
            generation_config=types.GenerateContentConfig( # 'config' を 'generation_config' に変更 (SDKのドキュメントに合わせる)
                temperature=0.3,
                max_output_tokens=1500,
            ),
        )
        
        daily_api_calls += 1
        
        if response.text:
            return response.text[:1024]
        else:
            return "要約の生成に失敗しました。"
            
    except Exception as e:
        print(f"Gemini API エラー: {e}")
        return generate_simple_summary(messages)

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

def needs_summary(messages):
    """要約が必要かどうかを判定"""
    if len(messages) < 5:
        return False
    
    # 同じユーザーの連続投稿が多い場合は要約不要
    authors = [msg.author for msg in messages]
    unique_authors = len(set(authors))
    
    if unique_authors == 1 and len(messages) < 10:
        return False
    
    # 短いメッセージばかりの場合
    total_length = sum(len(msg.content) for msg in messages)
    if total_length < 200:  # 合計200文字未満
        return False
    
    return True

@bot.event
async def on_ready():
    bot.start_time = datetime.now()
    print(f'{bot.user} がログインしました！')
    summary_task.start()
    cleanup_task.start()

@bot.event
async def on_message(message):
    # Bot自身のメッセージは無視
    if message.author.bot:
        return
    
    # 監視対象チャンネルのメッセージを保存
    if message.channel.id in MONITORING_CHANNELS:
        message_data = MessageData(message)
        message_buffer[message.channel.id].append(message_data)
        
        # より積極的なメモリ管理
        if len(message_buffer[message.channel.id]) > MAX_BUFFER_SIZE:
            # 古いメッセージを削除
            message_buffer[message.channel.id] = message_buffer[message.channel.id][-MAX_BUFFER_SIZE:]
    
    await bot.process_commands(message)

@tasks.loop(minutes=SUMMARY_INTERVAL)
async def summary_task():
    """定期的に要約を生成して投稿"""
    summary_channel = bot.get_channel(SUMMARY_CHANNEL_ID)
    if not summary_channel:
        print("要約チャンネルが見つかりません")
        return
    
    api_calls = 0  # API呼び出し回数をカウント
    
    for channel_id in MONITORING_CHANNELS:
        if channel_id in message_buffer and message_buffer[channel_id]:
            channel = bot.get_channel(channel_id)
            if not channel:
                continue
            
            messages = message_buffer[channel_id][-MAX_MESSAGES_PER_SUMMARY:]
            
            # メッセージが少なすぎる場合はスキップ
            if not needs_summary(messages):
                print(f"チャンネル {channel.name}: 要約不要（メッセージ数: {len(messages)}）")
                continue
            
            try:
                embed = create_summary_embed(messages, channel.name)
                await summary_channel.send(embed=embed)
                api_calls += 1
                
                # API呼び出し間隔を空ける（レート制限対策）
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"要約エラー: {e}")
            
            # 処理済みメッセージをクリア
            message_buffer[channel_id].clear()
    
    print(f"[{datetime.now()}] 要約完了: {api_calls}回のAPI呼び出し")

@tasks.loop(hours=6)  # 6時間ごとに実行
async def cleanup_task():
    """定期的なメモリクリーンアップ"""
    # 古いメッセージをクリア
    for channel_id in list(message_buffer.keys()):
        if channel_id not in MONITORING_CHANNELS:
            del message_buffer[channel_id]
    
    # ガベージコレクション実行
    gc.collect()
    print(f"[{datetime.now()}] メモリクリーンアップ完了")

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
        value="Gemini Pro 使用中" if GOOGLE_API_KEY else "未設定",
        inline=True
    )
    
    # 稼働時間
    if hasattr(bot, 'start_time'):
        uptime = datetime.now() - bot.start_time
        embed.add_field(
            name="稼働時間",
            value=f"{uptime.days}日 {uptime.seconds // 3600}時間",
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

@bot.command(name='api_usage')
@commands.has_permissions(administrator=True)
async def api_usage(ctx):
    """API使用量を表示"""
    global daily_api_calls, last_reset_date
    
    # 日付が変わったらリセット
    if datetime.now().date() != last_reset_date:
        daily_api_calls = 0
        last_reset_date = datetime.now().date()
    
    embed = discord.Embed(
        title="📊 Gemini API 使用状況",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="本日の使用回数",
        value=f"{daily_api_calls} / 1,500回",
        inline=False
    )
    
    embed.add_field(
        name="使用率",
        value=f"{(daily_api_calls / 1500 * 100):.1f}%",
        inline=True
    )
    
    embed.add_field(
        name="残り回数",
        value=f"{1500 - daily_api_calls}回",
        inline=True
    )
    
    # 予測
    hours_passed = datetime.now().hour
    if hours_passed > 0:
        predicted_daily = (daily_api_calls / hours_passed) * 24
        embed.add_field(
            name="本日の予測使用回数",
            value=f"約{int(predicted_daily)}回",
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command(name='system')
@commands.has_permissions(administrator=True)
async def system_info(ctx):
    """システムリソースの使用状況を表示"""
    # CPU使用率
    cpu_percent = psutil.cpu_percent(interval=1)
    
    # メモリ使用率
    memory = psutil.virtual_memory()
    memory_percent = memory.percent
    memory_used = memory.used / 1024 / 1024 / 1024  # GB
    memory_total = memory.total / 1024 / 1024 / 1024  # GB
    
    # プロセス情報
    process = psutil.Process()
    process_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    embed = discord.Embed(
        title="🖥️ システム情報",
        color=discord.Color.green()
    )
    
    embed.add_field(
        name="CPU",
        value=f"{cpu_percent}%",
        inline=True
    )
    
    embed.add_field(
        name="メモリ",
        value=f"{memory_percent}% ({memory_used:.1f}/{memory_total:.1f} GB)",
        inline=True
    )
    
    embed.add_field(
        name="Bot使用メモリ",
        value=f"{process_memory:.1f} MB",
        inline=True
    )
    
    embed.add_field(
        name="Python",
        value=platform.python_version(),
        inline=True
    )
    
    embed.add_field(
        name="稼働時間",
        value=f"{(datetime.now() - bot.start_time).days}日" if hasattr(bot, 'start_time') else "不明",
        inline=True
    )
    
    await ctx.send(embed=embed)

# Botを起動
if __name__ == "__main__":
    bot.run(DISCORD_BOT_TOKEN)
