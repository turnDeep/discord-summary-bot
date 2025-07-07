# Discord側での設定手順

このガイドでは、Discord Summary Botをデプロイ後、Discord側で必要な設定について説明します。

## 🚨 重要な前提条件

このBotは**全チャンネル自動監視版**です：
- ✅ 招待されたサーバーの全テキストチャンネルを自動監視
- ✅ `bot-summaries`チャンネルを自動作成
- ✅ 監視チャンネルの個別設定は不要

## 📋 設定手順

### 1. **Discord Developer Portalでの必須設定**

#### A. Message Content Intentを有効化（最重要！）

1. **Discord Developer Portal**にアクセス
   - https://discord.com/developers/applications
   
2. **あなたのアプリケーション**を選択

3. **左メニューの「Bot」**をクリック

4. **下にスクロールして「Privileged Gateway Intents」**セクションを探す

5. **以下を必ず有効にする**：
   - ✅ **MESSAGE CONTENT INTENT** ← コマンドを認識するために必須！
   - ✅ **SERVER MEMBERS INTENT**
   - ✅ **PRESENCE INTENT**

6. **「Save Changes」**をクリック

> ⚠️ **注意**: Message Content Intentが無効だと、Botは起動してもコマンドに反応しません！

### 2. **BotをDiscordサーバーに招待**

#### A. 招待URLの生成

1. **Discord Developer Portal**で**OAuth2 → URL Generator**を開く

2. **SCOPES**で以下を選択：
   - ✅ `bot`
   - ✅ `applications.commands`（オプション）

3. **BOT PERMISSIONS**で以下を必ず選択：
   - ✅ **View Channels**（チャンネルを見る）← メッセージを読むために必須！
   - ✅ **Send Messages**（メッセージを送信）
   - ✅ **Read Message History**（メッセージ履歴を読む）
   - ✅ **Manage Channels**（チャンネルの管理）← bot-summaries作成用
   - ✅ **Embed Links**（埋め込みリンク）

4. **生成されたURLをコピー**

#### B. Botの招待

1. **コピーしたURLをブラウザで開く**
2. **招待したいサーバーを選択**
3. **「認証」をクリック**
4. 権限を確認して**「はい」**

### 3. **Botの自動セットアップ確認**

Botがサーバーに参加すると、自動的に：
- ✅ `bot-summaries`チャンネルが作成される（または既存のものを使用）
- ✅ 全テキストチャンネルの監視が開始される
- ✅ 1時間ごとの自動要約がスケジュールされる

### 4. **動作確認**

#### ① Botの状態を確認
任意のチャンネルで以下を実行：
```
!status
```

以下のような情報が表示されれば正常：
- 要約チャンネル: #bot-summaries
- アクティブなチャンネル: （メッセージがあるチャンネル一覧）
- バッファ内のメッセージ数: X件
- 要約間隔: 60分
- AI要約: gemini-2.5-pro 使用中

#### ② 手動で要約を生成してテスト
1. いくつかのチャンネルでメッセージを投稿
2. 任意のチャンネルで実行：
```
!summary
```
3. 要約が表示されれば成功！

## 🔧 トラブルシューティング

### ❌ Botがオフライン
- デプロイが正常に完了しているか確認
- 環境変数（DISCORD_BOT_TOKEN、GOOGLE_API_KEY）が正しく設定されているか確認

### ❌ !summaryコマンドが反応しない
1. **Message Content Intent**が有効になっているか再確認
2. Botに必要な権限（特に**View Channels**）があるか確認
3. デプロイ先（Railway/Heroku等）でアプリを再起動

### ❌ bot-summariesチャンネルが作成されない
- Botに**Manage Channels**権限があるか確認
- 手動でチャンネルを作成し、`!set_summary_channel #bot-summaries`で設定も可能

### ❌ 要約が投稿されない
- `!status`でアクティブなチャンネルがあるか確認
- Bot参加後に投稿されたメッセージのみが対象（過去のメッセージは含まれない）
- 1時間以内に1件以上のメッセージが必要

### ❌ 特定のチャンネルを監視対象外にしたい
- チャンネルの権限設定でBotの「View Channel」権限を外す
- プライベートチャンネルは自動的に対象外

## 📝 利用可能なコマンド一覧

| コマンド | 説明 | 必要権限 |
|---------|------|---------|
| `!summary` | 手動で要約を生成（実行したチャンネルに返信） | 全員 |
| `!status` | Botの現在の状態を表示 | 全員 |
| `!toggle_summary` | 自動要約のON/OFF切り替え | 管理者 |
| `!set_summary_channel #channel` | 要約投稿先チャンネルを変更 | 管理者 |
| `!api_usage` | Gemini API使用状況を表示 | 管理者 |
| `!system` | システムリソース情報を表示 | 管理者 |

## 💡 使い方のヒント

### 初回セットアップ後
1. **テスト投稿**: 複数のチャンネルで会話をする
2. **手動実行**: `!summary`で動作確認
3. **自動要約待機**: 1時間後に自動要約が`#bot-summaries`に投稿される

### 権限の確認方法（Discord側）
1. **サーバー設定**（サーバー名の横の▼ → サーバー設定）
2. **ロール**または**連携サービス**
3. **hana-summary-bot**を選択
4. 必要な権限が有効になっているか確認

### 複数サーバーでの使用
- 同じBotを複数のサーバーに招待可能
- 各サーバーで独立して動作
- サーバーごとに要約設定が可能

## ⚠️ よくある間違い

1. **Message Content Intentを有効にし忘れる**
   - 症状：Botは起動するがコマンドに反応しない
   - 解決：Developer PortalでIntentを有効化

2. **View Channels権限を付与し忘れる**
   - 症状：Botがメッセージを読めない
   - 解決：招待時に権限を正しく設定

3. **過去のメッセージを要約しようとする**
   - 注意：Bot参加後のメッセージのみが対象
   - 解決：新しくメッセージを投稿してから要約

これで設定は完了です！何か問題があれば、トラブルシューティングセクションを参照してください。