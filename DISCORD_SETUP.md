素晴らしい！BotがDiscordに正常に接続できています。次はDiscord側での設定を行いましょう。

## Discord側での設定手順

### 1. **BotをDiscordサーバーに招待**

まだBotをサーバーに追加していない場合：

1. **Discord Developer Portal**にアクセス
   - https://discord.com/developers/applications
   - あなたのアプリケーションを選択

2. **OAuth2 → URL Generator**を開く

3. **SCOPES**で以下を選択：
   - ✅ `bot`
   - ✅ `applications.commands`（オプション）

4. **BOT PERMISSIONS**で以下を選択：
   - ✅ Send Messages
   - ✅ Embed Links
   - ✅ Read Message History
   - ✅ View Channels
   - ✅ Use Slash Commands（オプション）

5. **生成されたURLをコピー**して、ブラウザで開く

6. **招待したいサーバーを選択**して「認証」

### 2. **Discordでの初期設定**

Botがサーバーに参加したら、以下のコマンドを実行：

#### ① 要約チャンネルの設定（必須）
```
!set_summary_channel #要約チャンネル名
```
例：`!set_summary_channel #bot-summaries`

#### ② 監視チャンネルの追加（必須）
```
!add_monitor #監視したいチャンネル名
```
例：`!add_monitor #general`
例：`!add_monitor #development`

複数のチャンネルを監視したい場合は、チャンネルごとにコマンドを実行してください。

### 3. **動作確認**

#### ① Botの状態を確認
```
!status
```
以下のような情報が表示されます：
- 要約チャンネル
- 監視中のチャンネル
- 要約間隔
- AI要約の状態

#### ② 手動で要約を生成してテスト
```
!summary
```
監視チャンネルに5件以上のメッセージがある場合、要約が生成されます。

### 4. **よくあるトラブルと解決方法**

#### 「このチャンネルは監視対象ではありません」と表示される場合
- `!add_monitor #チャンネル名`を実行して監視対象に追加

#### 「要約するメッセージがありません」と表示される場合
- Bot起動後に投稿されたメッセージのみが対象です
- 監視チャンネルで何件かメッセージを投稿してから再度実行

#### 要約チャンネルに投稿されない場合
- `!status`で要約チャンネルが正しく設定されているか確認
- Botに必要な権限（Send Messages、Embed Links）があるか確認

### 5. **便利なコマンド一覧**

```
# 基本コマンド
!status              - Botの状態確認
!summary             - 手動で要約生成
!recent 10           - 最新10件のメッセージ表示

# 管理者用コマンド（要Administrator権限）
!set_summary_channel #チャンネル - 要約投稿先設定
!add_monitor #チャンネル         - 監視チャンネル追加
!remove_monitor #チャンネル      - 監視チャンネル削除
!api_usage                       - API使用状況
!system                          - システム情報

# 高度な機能
!advanced_summary    - より詳細な要約を生成
```

### 6. **自動要約の確認**

設定が完了したら、60分後（`SUMMARY_INTERVAL`の設定値）に自動的に要約が投稿されます。

すぐに確認したい場合は：
1. 監視チャンネルで会話をする
2. `!summary`コマンドで手動実行

これで設定完了です！何か問題があれば教えてください。
