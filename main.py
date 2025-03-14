import sys
import os
from datetime import datetime
import pytz
import requests
from flask import Flask, request, jsonify

# 日本時間のタイムスタンプを取得
jst = pytz.timezone('Asia/Tokyo')
timestamp = datetime.now(jst).strftime("%Y-%m-%d_%H-%M-%S")

# 新しいログファイル名を作成
log_filename = f"server_{timestamp}.log"

# Console と ログの両方に出力するクラスを作成
class Logger:
    def __init__(self, filename):
        self.terminal = sys.stdout  # Console用
        self.log = open(filename, "w")  # ログファイル用

    def write(self, message):
        self.terminal.write(message)  # Consoleに出力
        self.terminal.flush()
        self.log.write(message)  # ログファイルに出力
        self.log.flush()

    def flush(self):
        self.terminal.flush()
        self.log.flush()

# stdoutとstderrの両方をLoggerに設定
sys.stdout = Logger(log_filename)
sys.stderr = sys.stdout  # エラーメッセージも記録

print(f"✅ ログファイル: {log_filename} に出力開始！")
print("🚀 サーバーを起動します...")

app = Flask(__name__)

ZAPIER_WEBHOOK_URL = "https://hooks.zapier.com/hooks/catch/17697150/2te7aqa/"
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")  # ボットトークンを取得

# ✅ Flask のルートエンドポイント（GET /）
@app.route("/", methods=["GET"])
def health_check():
    return "Slack Webhook Server is Running!", 200

# 🔹 Slack API でユーザー情報を取得する関数
def get_user_info(user_id):
    url = f"https://slack.com/api/users.info?user={user_id}"
    headers = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}

    response = requests.get(url, headers=headers)
    data = response.json()

    # Slack API のレスポンスをログに出力
    print(f"🔍 Slack API Response (users.info): {data}")

    if data.get("ok"):
        user_profile = data.get("user", {})
        return {
            "user_id": user_id,
            "real_name": user_profile.get("real_name", "Unknown"),
            "display_name": user_profile.get("profile", {}).get("display_name", "Unknown"),
            "email": user_profile.get("profile", {}).get("email", "Unknown")
        }
    return {"user_id": user_id, "real_name": "Unknown", "display_name": "Unknown", "email": "Unknown"}

# 🔹 Slack API でチャンネル名を取得する関数
def get_channel_name(channel_id):
    url = f"https://slack.com/api/conversations.info?channel={channel_id}"
    headers = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}

    response = requests.get(url, headers=headers)
    data = response.json()

    if data.get("ok"):
        return data["channel"].get("name", "Unknown")
    else:
        print(f"❌ Slack API Error (conversations.info): {data.get('error', 'Unknown error')}")
        return "Unknown"

# 🔹 Slack の Webhook エンドポイント（GET & POST）
@app.route("/slack/webhook", methods=["POST", "GET"])
def slack_webhook():
    try:
        if request.method == "GET":
            return "Slack Webhook is active!", 200  # Request URL の確認用

        data = request.json

        # ✅ Slack の Challenge Request に対応（追加）
        if "challenge" in data:
            return jsonify({"challenge": data["challenge"]})  # Challenge をそのまま返す

        event = data.get("event", {})

        # ボットメッセージを無視
        if event.get("subtype") == "bot_message":
            return jsonify({"status": "ignored_bot_message"}), 200

        # ✅ ユーザー情報を取得
        user_id = event.get("user", "Unknown")
        user_info = get_user_info(user_id)

        # ✅ Console にログを出力
        print(f"📡 Message received from User: {user_info['real_name']} ({user_info['display_name']})")
        print(f"💬 Message: {event.get('text', 'No text provided')}")

        # ✅ Zapier にデータを送信
        zapier_data = {
            "user_id": user_info["user_id"],
            "real_name": user_info["real_name"],
            "display_name": user_info["display_name"],
            "email": user_info["email"],
            "text": event.get("text", ""),
            "channel": event.get("channel", ""),
            "ts": event.get("ts", ""),
            "thread_ts": event.get("thread_ts", ""),  # 🔹 スレッドのトップメッセージの ts を追加
            "team": event.get("team", ""),
            "client_msg_id": event.get("client_msg_id", ""),
            "event_ts": event.get("event_ts", ""),
            "blocks": event.get("blocks", [])
        }

        # ✅ Slack メッセージの URL を作成
        base_url = f"https://tsuchinoko.slack.com/archives/{zapier_data['channel']}/p{zapier_data['ts'].replace('.', '')}"
        if zapier_data["thread_ts"]:
            base_url += f"?thread_ts={zapier_data['thread_ts']}&cid={zapier_data['channel']}"

        print(f"🔗 Slack メッセージリンク: {base_url}")
        zapier_data["message_url"] = base_url

        response = requests.post(ZAPIER_WEBHOOK_URL, json=zapier_data)
        print(f"📡 Sent data to Zapier: {response.status_code} - {response.text}")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print("❌ Error:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)