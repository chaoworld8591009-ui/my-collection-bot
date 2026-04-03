from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import json, os

app = Flask(__name__)

line_bot_api = LineBotApi(os.environ.get("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.environ.get("CHANNEL_SECRET"))

DATA_FILE = "data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"categories": ["好吃", "好玩", "好買", "想去"], "items": []}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    data = load_data()
    reply = handle_command(text, data)
    save_data(data)
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

def handle_command(text, data):
    items = data["items"]
    cats = data["categories"]

    if text == "清單" or text == "選單":
        return (
            "📋 指令說明\n"
            "──────────\n"
            "➕ 新增：\n"
            "  格式：#新增 分類 名稱\n"
            "  例：#新增 好吃 青木原拉麵\n\n"
            "📂 查看分類：\n"
            "  直接輸入分類名稱\n"
            "  例：好吃\n\n"
            "🔍 查全部：\n"
            "  輸入「全部」\n\n"
            "⭐ 評分：\n"
            "  格式：#評分 名稱 星數\n"
            "  例：#評分 青木原拉麵 5\n\n"
            "✅ 完成：\n"
            "  格式：#完成 名稱\n\n"
            "🗑 刪除：\n"
            "  格式：#刪除 名稱\n\n"
            "📁 分類管理：\n"
            "  #新增分類 名稱\n"
            "  #刪除分類 名稱"
        )

    if text == "全部":
        pending = [i for i in items if not i.get("done")]
        if not pending:
            return "📭 目前沒有收藏！"
        result = "📋 全部收藏：\n──────────\n"
        for i, item in enumerate(pending, 1):
            stars = "⭐" * item.get("stars", 0)
            result += f"{i}. [{item['cat']}] {item['name']} {stars}\n"
            if item.get("note"):
                result += f"   📝 {item['note']}\n"
        return result.strip()

    if text in cats:
        cat_items = [i for i in items if i["cat"] == text and not i.get("done")]
        if not cat_items:
            return f"📭 「{text}」還沒有收藏！\n輸入「#新增 {text} 名稱」來新增"
        result = f"📂 {text}：\n──────────\n"
        for i, item in enumerate(cat_items, 1):
            stars = "⭐" * item.get("stars", 0)
            result += f"{i}. {item['name']} {stars}\n"
            if item.get("note"):
                result += f"   📝 {item['note']}\n"
        return result.strip()

    if text.startswith("#新增 "):
        parts = text[4:].split(" ", 1)
        if len(parts) < 2:
            return "格式：#新增 分類 名稱\n例：#新增 好吃 青木原拉麵"
        cat, name = parts[0], parts[1]
        if cat not in cats:
            return f"❌ 分類「{cat}」不存在\n目前分類：{'、'.join(cats)}"
        items.append({"name": name, "cat": cat, "stars": 0, "note": "", "done": False})
        return f"✅ 已新增「{name}」到「{cat}」！"

    if text.startswith("#評分 "):
        parts = text[4:].rsplit(" ", 1)
        if len(parts) < 2 or not parts[1].isdigit():
            return "格式：#評分 名稱 星數\n例：#評分 青木原拉麵 5"
        name, stars = parts[0], int(parts[1])
        stars = max(0, min(5, stars))
        for item in items:
            if item["name"] == name:
                item["stars"] = stars
                return f"⭐ 已將「{name}」評為 {'⭐'*stars}"
        return f"❌ 找不到「{name}」"

    if text.startswith("#備註 "):
        parts = text[4:].split(" ", 1)
        if len(parts) < 2:
            return "格式：#備註 名稱 備註內容"
        name, note = parts[0], parts[1]
        for item in items:
            if item["name"] == name:
                item["note"] = note
                return f"📝 已幫「{name}」加上備註！"
        return f"❌ 找不到「{name}」"

    if text.startswith("#完成 "):
        name = text[4:]
        for item in items:
            if item["name"] == name:
                item["done"] = True
                return f"✅ 「{name}」已標記完成！"
        return f"❌ 找不到「{name}」"

    if text.startswith("#刪除 "):
        name = text[4:]
        before = len(items)
        data["items"] = [i for i in items if i["name"] != name]
        if len(data["items"]) < before:
            return f"🗑 已刪除「{name}」"
        return f"❌ 找不到「{name}」"

    if text.startswith("#新增分類 "):
        cat = text[6:]
        if cat in cats:
            return f"❌ 分類「{cat}」已存在"
        cats.append(cat)
        return f"📁 已新增分類「{cat}」！\n目前分類：{'、'.join(cats)}"

    if text.startswith("#刪除分類 "):
        cat = text[6:]
        if cat not in cats:
            return f"❌ 找不到分類「{cat}」"
        cats.remove(cat)
        return f"🗑 已刪除分類「{cat}」"

    return "輸入「清單」查看所有指令 😊"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
