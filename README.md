# Drive to TG

Selling-ready Google Drive → Telegram bot with **per-user Google OAuth**.

## User flow

1. User opens the bot.
2. User sends /login.
3. Bot gives a Google authorization link.
4. User connects their own Google account.
5. User sends a Drive file link.
6. Bot downloads only files that the connected Google account is allowed to download and uploads them to Telegram.

Customers do **not** need a service-account JSON.

## Required Heroku Config Vars

```
BOT_TOKEN
API_ID
API_HASH
BASE_URL
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
MONGODB_URI
```

Optional:

```
MONGODB_DB
```

## Google OAuth setup

Create a Google Cloud OAuth 2.0 **Web application** client.

Authorized redirect URI must be:

```
https://YOUR-HEROKU-DOMAIN/oauth/callback
```

Set the same URL as BASE_URL without the trailing slash.

Enable the Google Drive API and configure the OAuth consent screen. For production use, Google may require consent-screen verification depending on the scopes, users, and project configuration.

## MongoDB

Use MongoDB Atlas or another reachable MongoDB deployment. The bot stores OAuth tokens per Telegram user.

## Important

The bot does not bypass Google Drive download/copy restrictions. If the connected Google account cannot download a file, the bot cannot download it either.

Google Docs, Sheets, Slides and Drawings are exported to supported formats. Normal uploaded files such as videos, PDFs, ZIPs, images and audio are downloaded as files.

Folder downloading is not included in this version.
