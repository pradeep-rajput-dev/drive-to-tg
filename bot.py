import os
import re
import json
import asyncio
import tempfile
from pathlib import Path

from pyrogram import Client, filters
from pyrogram.types import Message
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

BOT_TOKEN = os.environ["BOT_TOKEN"]
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SERVICE_ACCOUNT_JSON = os.environ["SERVICE_ACCOUNT_JSON"]

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
creds = service_account.Credentials.from_service_account_info(
    json.loads(SERVICE_ACCOUNT_JSON), scopes=SCOPES
)
drive = build("drive", "v3", credentials=creds, cache_discovery=False)

app = Client("drive_to_tg", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

def extract_file_id(text):
    for pattern in [
        r"/file/d/([a-zA-Z0-9_-]+)",
        r"[?&]id=([a-zA-Z0-9_-]+)",
        r"/open\?id=([a-zA-Z0-9_-]+)",
    ]:
        m = re.search(pattern, text)
        if m:
            return m.group(1)
    value = text.strip()
    return value if re.fullmatch(r"[a-zA-Z0-9_-]{10,}", value) else None

def get_file(file_id):
    return drive.files().get(
        fileId=file_id,
        fields="id,name,mimeType,size,capabilities(canDownload)",
        supportsAllDrives=True,
    ).execute()

def download_file(file_id, destination):
    request = drive.files().get_media(fileId=file_id, supportsAllDrives=True)
    with open(destination, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request, chunksize=8 * 1024 * 1024)
        done = False
        while not done:
            _, done = downloader.next_chunk()

@app.on_message(filters.command("start"))
async def start(_, message: Message):
    await message.reply_text(
        "Drive to Telegram Bot\n\n"
        "Google Drive ka downloadable file link bhejo.\n"
        "Bot Drive ki download restriction bypass nahi karta."
    )

@app.on_message(filters.command("help"))
async def help_cmd(_, message: Message):
    await message.reply_text(
        "Google Drive file link bhejo.\n\n"
        "Private file ke liye configured service-account email ke saath "
        "file share karna zaroori hai."
    )

@app.on_message(filters.text & ~filters.command(["start", "help"]))
async def handle_link(_, message: Message):
    file_id = extract_file_id(message.text or "")
    if not file_id:
        await message.reply_text("Valid Google Drive file link nahi mila.")
        return

    status = await message.reply_text("Drive file check kar raha hoon...")
    tmp_path = None

    try:
        info = await asyncio.to_thread(get_file, file_id)
        name = info.get("name", "drive_file")
        size = int(info.get("size") or 0)
        can_download = info.get("capabilities", {}).get("canDownload", False)

        if not can_download:
            await status.edit_text(
                "Is file ke liye download permission available nahi hai. "
                "Owner se download/copy permission enable karwao."
            )
            return

        if size and size > 2 * 1024 * 1024 * 1024:
            await status.edit_text("File 2 GB se badi hai.")
            return

        safe_name = Path(name).name.replace("\\", "_").replace("/", "_")
        fd, tmp_path = tempfile.mkstemp(suffix=Path(safe_name).suffix)
        os.close(fd)

        await status.edit_text("Downloading: " + safe_name)
        await asyncio.to_thread(download_file, file_id, tmp_path)

        await status.edit_text("Telegram par upload kar raha hoon...")
        await message.reply_document(
            document=tmp_path,
            caption="File: " + safe_name,
            force_document=True,
        )
        await status.delete()

    except Exception as e:
        error = str(e)
        if "403" in error or "insufficientFilePermissions" in error:
            msg = "Google Drive ne download permission deny kar di."
        elif "404" in error:
            msg = "File nahi mili ya configured account ko access nahi hai."
        else:
            msg = "Error: " + error[:800]
        await status.edit_text(msg)
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

if __name__ == "__main__":
    app.run()
