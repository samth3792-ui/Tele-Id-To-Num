import asyncio
import re
import json
import os
from http.server import BaseHTTPRequestHandler
from pyrogram import Client
from pyrogram.errors import FloodWait

# Telegram details
API_ID = 29969433
API_HASH = "884f9ffa4e8ece099cccccade82effac"
PHONE_NUMBER = "+919214045762"
TARGET_BOT = "@telebrecheddb_bot"

# Vercel के लिए special path
SESSION_PATH = "/tmp/vercel_session"

# Bot का reply parse करने का function
def parse_bot_response(text: str) -> dict:
    text = text.replace("Телефон", "Phone") \
               .replace("История изменения имени", "Name change history") \
               .replace("Интересовались этим", "Viewed by")
    
    data = {
        "success": True,
        "username": None,
        "id": None,
        "phone": None,
        "viewed_by": None,
        "name_history": []
    }
    
    username_match = re.search(r"t\.me/([A-Za-z0-9_]+)", text)
    if username_match:
        data["username"] = username_match.group(1)
    
    id_match = re.search(r"ID[:： ]+(\d+)", text)
    if id_match:
        data["id"] = id_match.group(1)
    
    phone_match = re.search(r"Phone[:： ]+(\d+)", text)
    if phone_match:
        data["phone"] = phone_match.group(1)
    
    viewed_match = re.search(r"Viewed by[:： ]*(\d+)", text)
    if viewed_match:
        data["viewed_by"] = int(viewed_match.group(1))
    
    history_match = re.findall(r"(\d{2}\.\d{2}\.\d{4}) → @([\w\d_]+),\s*([\w\d, ]+)", text)
    for d, u, i in history_match:
        ids = re.findall(r"\d+", i)
        data["name_history"].append({
            "date": d,
            "username": u,
            "id": ids[0] if ids else None
        })
    
    return data

# Main function जो Telegram bot से बात करेगी
async def check_username(username: str) -> dict:
    username = username.strip()
    if username.startswith("@"):
        username = username[1:]
    
    # Pyrogram client बनाओ
    app = Client(
        SESSION_PATH,  # ✅ यहाँ fix किया है
        api_id=API_ID,
        api_hash=API_HASH,
        phone_number=PHONE_NUMBER
    )
    
    try:
        # Client start करो
        await app.start()
        message_to_send = f"t.me/{username}"
        
        # Bot को message भेजो
        sent = await app.send_message(TARGET_BOT, message_to_send)
        
        # Bot का reply wait करो
        reply_text = None
        for _ in range(8):  # 8 * 2 = 16 seconds
            async for msg in app.get_chat_history(TARGET_BOT, limit=5):
                if msg.id > sent.id and not msg.outgoing and msg.text:
                    reply_text = msg.text
                    break
            if reply_text:
                break
            await asyncio.sleep(2)
        
        if not reply_text:
            return {"success": False, "error": "Bot ने reply नहीं दिया"}
        
        return parse_bot_response(reply_text)
        
    except FloodWait as e:
        return {"success": False, "error": f"Telegram ने wait करने को कहा: {e.value} seconds"}
    except Exception as e:
        return {"success": False, "error": f"Error: {str(e)}"}
    finally:
        # Client stop करो
        if app.is_connected:
            await app.stop()

# Vercel के लिए handler
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # URL से username निकालो
        from urllib.parse import urlparse, parse_qs
        query = parse_qs(urlparse(self.path).query)
        username = query.get('username', [None])[0]
        
        if not username:
            self.send_response(400)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = json.dumps({"success": False, "error": "Username दो जैसे: ?username=@example"})
            self.wfile.write(response.encode())
            return
        
        try:
            # Async function run करो
            result = asyncio.run(check_username(username))
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result, indent=2).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = json.dumps({"success": False, "error": str(e)})
            self.wfile.write(response.encode())
