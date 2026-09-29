import os
import re
import asyncio
import tempfile
import secrets
from pathlib import Path
from urllib.parse import urlencode

from pyrogram import Client, filters
from pyrogram.types import Message
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

import storage as db

BOT_TOKEN = os.environ["BOT_TOKEN"]
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BASE_URL = os.environ["BASE_URL"].rstrip("/")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", BASE_URL + "/oauth/callback")
REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", BASE_URL + "/oauth/callback")

app = Client("drive_to_tg", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

EXPORT_TYPES = {
    "application/vnd.google-apps.document": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"
    ),
    "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.drawing": ("image/png", ".png"),
}

def extract_file_id(text):
    for pattern in (
        r"/file/d/([a-zA-Z0-9_-]+)",
        r"[?&]id=([a-zA-Z0-9_-]+)",
        r"/open?id=([a-zA-Z0-9_-]+)",
    ):
        m = re.search(pattern, text)
        if m:
            return m.group(1)
    value = text.strip()
    return value if re.fullmatch(r"[a-zA-Z0-9_-]{10,}", value) else None

def make_oauth_url(user_id):
    state = secrets.token_urlsafe(32)
    db.save_state(state, user_id)
    params = {
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/drive.readonly",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)

def credentials_for(user_id):
    token = db.get_token(user_id)
    if not token:
        return None
    return Credentials(
        token=token["access_token"],
        refresh_token=token.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )

def get_file(service, file_id):
    return service.files().get(
        fileId=file_id,
        fields="id,name,mimeType,size,capabilities(canDownload)",
        supportsAllDrives=True,
    ).execute()

def download_file(service, file_id, destination, mime_type):
    if mime_type in EXPORT_TYPES:
        request = service.files().export_media(
            fileId=file_id, mimeType=EXPORT_TYPES[mime_type][0]
        )
    else:
        request = service.files().get_media(
            fileId=file_id, supportsAllDrives=True
        )
    with open(destination, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request, chunksize=8 * 1024 * 1024)
        done = False
        while not done:
            _, done = downloader.next_chunk()

@app.on_message(filters.command("start"))
async def start(_, message: Message):
    await message.reply_text(
        "📥 Drive → Telegram\n\n"
        "1️⃣ Pehle /login karo\n"
        "2️⃣ Google account connect karo\n"
        "3️⃣ Phir Drive link bhejo\n\n"
        "Har user apna Google account connect karega. JSON ki zarurat nahi."
    )

@app.on_message(filters.command("login"))
async def login(_, message: Message):
    await message.reply_text(
        "🔐 Google Drive connect karne ke liye ye link open karo:\n\n"
        + make_oauth_url(message.from_user.id)
        + "\n\nAuthorization ke baad isi bot mein Drive link bhejna."
    )

@app.on_message(filters.command("logout"))
async def logout(_, message: Message):
    db.delete_token(message.from_user.id)
    await message.reply_text("✅ Google Drive account disconnect kar diya.")

@app.on_message(filters.command("mystatus"))
async def mystatus(_, message: Message):
    if db.get_token(message.from_user.id):
        await message.reply_text("✅ Google Drive connected hai.")
    else:
        await message.reply_text("❌ Drive connected nahi hai. /login karo.")

@app.on_message(filters.text & ~filters.command(["start", "login", "logout", "mystatus"]))
async def handle_link(_, message: Message):
    creds = credentials_for(message.from_user.id)
    if not creds:
        await message.reply_text("❌ Pehle /login karke Google Drive connect karo.")
        return

    file_id = extract_file_id(message.text or "")
    if not file_id:
        await message.reply_text("❌ Valid Google Drive file link nahi mila.")
        return

    status = await message.reply_text("🔎 Drive file check kar raha hoon...")
    tmp_path = None

    try:
        service = build("drive", "v3", credentials=creds, cache_discovery=False)
        info = await asyncio.to_thread(get_file, service, file_id)
        name = info.get("name", "drive_file")
        mime_type = info.get("mimeType", "application/octet-stream")
        size = int(info.get("size") or 0)

        if not info.get("capabilities", {}).get("canDownload", False):
            await status.edit_text(
                "❌ Is file par download permission available nahi hai."
            )
            return

        if size and size > 2 * 1024 * 1024 * 1024:
            await status.edit_text("❌ File 2 GB se badi hai.")
            return

        suffix = Path(name).suffix
        if mime_type in EXPORT_TYPES:
            suffix = EXPORT_TYPES[mime_type][1]
            name = Path(name).stem + suffix

        safe_name = Path(name).name.replace("\\", "_").replace("/", "_")
        fd, tmp_path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)

        await status.edit_text("⬇️ Downloading: " + safe_name)
        await asyncio.to_thread(download_file, service, file_id, tmp_path, mime_type)

        await status.edit_text("📤 Telegram par upload kar raha hoon...")
        await message.reply_document(
            document=tmp_path,
            caption="📁 " + safe_name,
            force_document=True,
        )
        await status.delete()

    except Exception as e:
        error = str(e)
        if "403" in error:
            msg = "❌ Google Drive ne access/download deny kar diya."
        elif "404" in error:
            msg = "❌ File nahi mili ya aapke Google account ko access nahi hai."
        else:
            msg = "❌ Error: " + error[:700]
        await status.edit_text(msg)
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

if __name__ == "__main__":
    app.run()
