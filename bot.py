import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta, time
import asyncio
from collections import defaultdict, deque
from google import genai  # 新しいGoogle Gen AI SDK
from google.genai import types  # types のインポート
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

# Google Gen AI SDKのクライアント作成（最新SDK仕様）
client = genai.Client(api_key=GOOGLE_API_KEY)

# Botの設定
intents = discord.Intents.default()
intents.message_content = True  # メッセージ内容を読むために必要
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

# 設定項目
MAX_MESSAGES_PER_SUMMARY = int(os.getenv('MAX_MESSAGES_PER_SUMMARY', 100))  # 1回の要約に含める最大メッセージ数
BOT_CHANNEL_NAME = os.getenv('BOT_CHANNEL_NAME', 'bot-summaries')  # Bot用チャンネルの名前

# 使用するモデル（環境変数で設定可能）
MODEL_NAME = os.getenv('GEMINI_MODEL', 'gemini-2.5-pro')

# 要約スケジュール（時刻と要約期間）
SUMMARY_SCHEDULE = [
    {"hour": 6, "minute": 0, "hours_back": 24, "description": "過去24時間"},
    {"hour": 12, "minute": 0, "hours_back": 6, "description": "6時から12時"},
    {"hour": 18, "minute": 0, "hours_back": 6, "description": "12時から18時"},
]

# サーバーごとの設定を保存
server_configs = {}
# メッセージを保存する辞書（サーバーID -> チャンネルID -> メッセージリスト）
# 24時間分のメッセージを保持するためにタイムスタンプ付きで管理
message_buffers = defaultdict(lambda: defaultdict(lambda: deque()))

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
        self.channel_id = message.channel.id
        self.attachments = len(message.attachments)
        self.embeds = len(message.embeds)

def get_messages_in_timerange(guild_id, hours_back):
    """指定時間内のメッセージを取得"""
    cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
    messages_by_channel = {}
    
    for channel_id, messages in message_buffers[guild_id].items():
        filtered_messages = [
            msg for msg in messages 
            if msg.timestamp.replace(tzinfo=None) > cutoff_time
        ]
        if filtered_messages:
            # チャンネル名でグループ化
            channel_name = filtered_messages[0].channel_name
            messages_by_channel[channel_name] = filtered_messages
    
    return messages_by_channel

def cleanup_old_messages():
    """24時間以上前のメッセージを削除"""
    cutoff_time = datetime.utcnow() - timedelta(hours=24)
    
    for guild_id in message_buffers:
        for channel_id in message_buffers[guild_id]:
            # dequeから古いメッセージを削除
            while (message_buffers[guild_id][channel_id] and 
                   message_buffers[guild_id][channel_id][0].timestamp.replace(tzinfo=None) < cutoff_time):
                message_buffers[guild_id][channel_id].popleft()

def generate_simple_summary(messages_by_channel):
    """Gemini APIが使えない場合の簡易要約"""
    summaries = []
    
    for channel_name, messages in messages_by_channel.items():
        content_words = defaultdict(int)
        
        for msg in messages:
            words = msg.content.lower().split()
            for word in words:
                if len(word) > 4:  # 4文字以上の単語をカウント
                    content_words[word] += 1
        
        # 頻出単語TOP3
        top_words = sorted(content_words.items(), key=lambda x: x[1], reverse=True)[:3]
        if top_words:
            keywords = ", ".join([word for word, _ in top_words])
            summaries.append(f"**#{channel_name}**: {keywords}")
    
    if summaries:
        return "\n".join(summaries)
    return "特定のトピックは見つかりませんでした。"

def summarize_all_channels(messages_by_channel):
    """全チャンネルのメッセージを統合して要約する関数"""
    global daily_api_calls, last_reset_date
    
    # 日付が変わったらAPI使用量をリセット
    if datetime.now().date() != last_reset_date:
        daily_api_calls = 0
        last_reset_date = datetime.now().date()
    
    if not any(messages_by_channel.values()):
        return "要約するメッセージがありません。"
    
    try:
        # 全チャンネルのメッセージを整形
        all_conversations = []
        
        for channel_name, messages in messages_by_channel.items():
            if not messages:
                continue
            
            channel_text = f"\n=== #{channel_name} ===\n"
            message_texts = []
            
            # 最新のMAX_MESSAGES_PER_SUMMARY件のみ処理
            for msg in messages[-MAX_MESSAGES_PER_SUMMARY:]:
                text = f"{msg.author}: {msg.content}"
                if msg.attachments > 0:
                    text += f" [添付ファイル: {msg.attachments}件]"
                if msg.embeds > 0:
                    text += f" [Embed: {msg.embeds}件]"
                message_texts.append(text)
            
            channel_text += "\n".join(message_texts)
            all_conversations.append(channel_text)
        
        # 全会話を結合
        full_conversation = "\n\n".join(all_conversations)
        
        # プロンプトを構築
        prompt = f"""以下は複数のDiscordチャンネルでの会話です。各チャンネルごとに要約を作成してください：

{full_conversation}

以下の形式で要約してください：
1. 各チャンネルごとの主要なトピックや話題
2. 重要な決定事項や合意事項（あれば）
3. 注目すべき情報や発言
4. 全体的な活動状況

チャンネルごとに見出しをつけて、簡潔にまとめてください。"""
        
        # APIを呼び出し
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=2000,
            ),
        )
        
        daily_api_calls += 1
        
        # レスポンスのテキストを取得
        if response.text:
            return response.text
        else:
            return "要約の生成に失敗しました。"
            
    except Exception as e:
        print(f"Gemini API エラー: {e}")
        return generate_simple_summary(messages_by_channel)

async def get_or_create_bot_channel(guild):
    """Bot用チャンネルを取得または作成"""
    # 既存のbot-summariesチャンネルを探す
    for channel in guild.text_channels:
        if channel.name == BOT_CHANNEL_NAME:
            return channel
    
    # なければ作成
    try:
        channel = await guild.create_text_channel(
            name=BOT_CHANNEL_NAME,
            topic="このチャンネルはBotが定期的に要約を投稿します。"
        )
        return channel
    except discord.Forbidden:
        print(f"チャンネル作成権限がありません: {guild.name}")
        return None

def create_server_summary_embed(guild, messages_by_channel, time_description):
    """サーバー全体の要約用Embedを作成"""
    embed = discord.Embed(
        title=f"📋 {guild.name} サーバー要約",
        description=f"{time_description}の活動要約",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    
    # 全体の統計
    total_messages = sum(len(messages) for messages in messages_by_channel.values())
    active_channels = len([ch for ch, msgs in messages_by_channel.items() if msgs])
    all_authors = set()
    for messages in messages_by_channel.values():
        for msg in messages:
            all_authors.add(msg.author)
    
    embed.add_field(
        name="📊 統計",
        value=f"総メッセージ数: {total_messages}\n"
              f"アクティブチャンネル数: {active_channels}\n"
              f"投稿者数: {len(all_authors)}",
        inline=False
    )
    
    # チャンネル別の活動状況
    if active_channels > 0:
        channel_stats = []
        for channel_name, messages in sorted(messages_by_channel.items(), 
                                            key=lambda x: len(x[1]), 
                                            reverse=True)[:5]:  # TOP5チャンネル
            if messages:
                channel_stats.append(f"**#{channel_name}**: {len(messages)}件")
        
        if channel_stats:
            embed.add_field(
                name="📍 アクティブなチャンネル (TOP5)",
                value="\n".join(channel_stats),
                inline=False
            )
    
    # 要約内容
    summary = summarize_all_channels(messages_by_channel)
    
    # 要約が長すぎる場合は分割
    if len(summary) > 1024:
        # 最初の1000文字を表示
        embed.add_field(
            name="🎯 要約",
            value=summary[:1000] + "...",
            inline=False
        )
        # 残りは別フィールドに
        remaining = summary[1000:]
        while remaining and len(embed) < 5900:  # Embed全体の制限
            chunk = remaining[:1024]
            embed.add_field(
                name="　",  # 空白の全角スペース
                value=chunk,
                inline=False
            )
            remaining = remaining[1024:]
    else:
        embed.add_field(
            name="🎯 要約",
            value=summary,
            inline=False
        )
    
    return embed

async def setup_guild(guild):
    """サーバーの初期設定"""
    guild_id = guild.id
    
    # Bot用チャンネルを取得または作成
    bot_channel = await get_or_create_bot_channel(guild)
    
    server_configs[guild_id] = {
        'summary_channel': bot_channel,
        'enabled': True
    }
    
    if bot_channel:
        print(f"サーバー '{guild.name}' の設定完了。要約チャンネル: #{bot_channel.name}")
    else:
        print(f"サーバー '{guild.name}' でチャンネル作成に失敗しました。")

async def post_scheduled_summary(schedule_info):
    """スケジュールに従って要約を投稿"""
    for guild_id, config in server_configs.items():
        if not config['enabled'] or not config['summary_channel']:
            continue
        
        guild = bot.get_guild(guild_id)
        if not guild:
            continue
        
        # 指定時間内のメッセージを取得
        messages_by_channel = get_messages_in_timerange(guild_id, schedule_info['hours_back'])
        
        if messages_by_channel:
            try:
                embed = create_server_summary_embed(
                    guild, 
                    messages_by_channel, 
                    schedule_info['description']
                )
                summary_channel = config['summary_channel']
                
                if summary_channel:
                    await summary_channel.send(embed=embed)
                    total_messages = sum(len(msgs) for msgs in messages_by_channel.values())
                    print(f"[{datetime.now()}] {guild.name} の{schedule_info['description']}要約を投稿しました（{total_messages}件のメッセージ）")
                
            except Exception as e:
                print(f"要約エラー ({guild.name}): {e}")
        else:
            print(f"[{datetime.now()}] {guild.name}: {schedule_info['description']}に新しいメッセージがないため要約をスキップ")

@bot.event
async def on_ready():
    bot.start_time = datetime.now()
    print(f'{bot.user} がログインしました！')
    print(f'使用モデル: {MODEL_NAME}')
    print(f'要約スケジュール: 6時(24時間分)、12時(6時間分)、18時(6時間分)')
    
    # 既に参加している全サーバーの設定
    for guild in bot.guilds:
        await setup_guild(guild)
    
    # 定期タスクを開始
    scheduled_summary_task.start()
    cleanup_task.start()

@bot.event
async def on_guild_join(guild):
    """新しいサーバーに参加した時の処理"""
    print(f"新しいサーバーに参加しました: {guild.name}")
    await setup_guild(guild)

@bot.event
async def on_guild_remove(guild):
    """サーバーから削除された時の処理"""
    guild_id = guild.id
    if guild_id in server_configs:
        del server_configs[guild_id]
    if guild_id in message_buffers:
        del message_buffers[guild_id]
    print(f"サーバーから削除されました: {guild.name}")

@bot.event
async def on_message(message):
    # Bot自身のメッセージは無視
    if message.author.bot:
        return
    
    # DM は無視
    if not message.guild:
        return
    
    # Bot用チャンネルへの投稿は無視
    if message.channel.name == BOT_CHANNEL_NAME:
        return
    
    # メッセージを保存
    guild_id = message.guild.id
    channel_id = message.channel.id
    
    message_data = MessageData(message)
    message_buffers[guild_id][channel_id].append(message_data)
    
    await bot.process_commands(message)

@tasks.loop(minutes=1)
async def scheduled_summary_task():
    """1分ごとにスケジュールをチェックして要約を投稿"""
    now = datetime.now()
    current_time = time(now.hour, now.minute)
    
    for schedule in SUMMARY_SCHEDULE:
        scheduled_time = time(schedule['hour'], schedule['minute'])
        
        # 現在時刻が予定時刻と一致する場合
        if (current_time.hour == scheduled_time.hour and 
            current_time.minute == scheduled_time.minute):
            await post_scheduled_summary(schedule)
            
            # 古いメッセージをクリーンアップ
            cleanup_old_messages()

@tasks.loop(hours=6)  # 6時間ごとに実行
async def cleanup_task():
    """定期的なメモリクリーンアップ"""
    # 削除されたサーバーのデータをクリア
    for guild_id in list(message_buffers.keys()):
        if guild_id not in server_configs:
            del message_buffers[guild_id]
    
    # 24時間以上前のメッセージを削除
    cleanup_old_messages()
    
    # ガベージコレクション実行
    gc.collect()
    print(f"[{datetime.now()}] メモリクリーンアップ完了")

@bot.command(name='summary')
async def manual_summary(ctx, hours: int = 24):
    """手動で現在のサーバーの要約を生成するコマンド
    
    使用例:
    !summary - 過去24時間の要約
    !summary 6 - 過去6時間の要約
    !summary 48 - 過去48時間の要約
    """
    if not ctx.guild:
        await ctx.send("このコマンドはサーバー内でのみ使用できます。")
        return
    
    # 時間の範囲を制限（最大72時間）
    if hours < 1:
        hours = 1
    elif hours > 72:
        hours = 72
    
    guild_id = ctx.guild.id
    
    # 指定時間内のメッセージを取得
    messages_by_channel = get_messages_in_timerange(guild_id, hours)
    
    if not messages_by_channel:
        await ctx.send(f"過去{hours}時間の要約するメッセージがありません。")
        return
    
    embed = create_server_summary_embed(ctx.guild, messages_by_channel, f"過去{hours}時間")
    await ctx.send(embed=embed)

@bot.command(name='status')
async def bot_status(ctx):
    """Botの状態を表示"""
    if not ctx.guild:
        await ctx.send("このコマンドはサーバー内でのみ使用できます。")
        return
    
    guild_id = ctx.guild.id
    config = server_configs.get(guild_id, {})
    
    embed = discord.Embed(
        title="Bot Status",
        color=discord.Color.blue()
    )
    
    # 要約チャンネル
    summary_ch = config.get('summary_channel')
    embed.add_field(
        name="要約チャンネル",
        value=summary_ch.mention if summary_ch else "未設定",
        inline=False
    )
    
    # 監視状況
    active_channels = []
    total_buffered = 0
    for channel_id, messages in message_buffers[guild_id].items():
        if messages:
            channel = ctx.guild.get_channel(channel_id)
            if channel:
                active_channels.append(f"#{channel.name}: {len(messages)}件")
                total_buffered += len(messages)
    
    embed.add_field(
        name="アクティブなチャンネル",
        value="\n".join(active_channels[:10]) if active_channels else "なし",  # 最大10個表示
        inline=False
    )
    
    if len(active_channels) > 10:
        embed.add_field(
            name="",
            value=f"... 他 {len(active_channels) - 10} チャンネル",
            inline=False
        )
    
    embed.add_field(
        name="バッファ内のメッセージ数",
        value=f"合計 {total_buffered} 件（過去24時間）",
        inline=True
    )
    
    # 次回の要約時刻
    now = datetime.now()
    next_summaries = []
    for schedule in SUMMARY_SCHEDULE:
        scheduled_time = datetime.combine(now.date(), time(schedule['hour'], schedule['minute']))
        if scheduled_time < now:
            scheduled_time += timedelta(days=1)
        time_until = scheduled_time - now
        hours_until = int(time_until.total_seconds() // 3600)
        minutes_until = int((time_until.total_seconds() % 3600) // 60)
        next_summaries.append(f"{schedule['hour']}時 ({hours_until}時間{minutes_until}分後) - {schedule['description']}")
    
    embed.add_field(
        name="次回の要約",
        value="\n".join(next_summaries),
        inline=False
    )
    
    embed.add_field(
        name="AI要約",
        value=f"{MODEL_NAME} 使用中" if GOOGLE_API_KEY else "未設定",
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

@bot.command(name='toggle_summary')
@commands.has_permissions(administrator=True)
async def toggle_summary(ctx):
    """このサーバーの要約機能のON/OFF切り替え"""
    if not ctx.guild:
        return
    
    guild_id = ctx.guild.id
    if guild_id in server_configs:
        server_configs[guild_id]['enabled'] = not server_configs[guild_id]['enabled']
        status = "有効" if server_configs[guild_id]['enabled'] else "無効"
        await ctx.send(f"要約機能を{status}にしました。")
    else:
        await ctx.send("サーバー設定が見つかりません。")

@bot.command(name='set_summary_channel')
@commands.has_permissions(administrator=True)
async def set_summary_channel(ctx, channel: discord.TextChannel):
    """要約投稿チャンネルを設定"""
    if not ctx.guild:
        return
    
    guild_id = ctx.guild.id
    if guild_id in server_configs:
        server_configs[guild_id]['summary_channel'] = channel
        await ctx.send(f"要約チャンネルを {channel.mention} に設定しました。")
    else:
        await ctx.send("サーバー設定が見つかりません。")

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
    
    embed.add_field(
        name="使用モデル",
        value=MODEL_NAME,
        inline=True
    )
    
    # 予測（1日3回の要約 × サーバー数）
    total_servers = len(server_configs)
    active_servers = len([c for c in server_configs.values() if c['enabled']])
    predicted_daily = active_servers * 3
    embed.add_field(
        name="本日の予測使用回数",
        value=f"約{predicted_daily}回（{active_servers}サーバー × 3回）",
        inline=False
    )
    
    # 全サーバーの統計
    embed.add_field(
        name="サーバー統計",
        value=f"総数: {total_servers}\nアクティブ: {active_servers}",
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
        name="使用モデル",
        value=MODEL_NAME,
        inline=True
    )
    
    embed.add_field(
        name="稼働時間",
        value=f"{(datetime.now() - bot.start_time).days}日" if hasattr(bot, 'start_time') else "不明",
        inline=True
    )
    
    # サーバー数
    embed.add_field(
        name="参加サーバー数",
        value=f"{len(bot.guilds)} サーバー",
        inline=True
    )
    
    await ctx.send(embed=embed)

# Botを起動
if __name__ == "__main__":
    bot.run(DISCORD_BOT_TOKEN)