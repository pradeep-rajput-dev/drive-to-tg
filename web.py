import os
import requests
from flask import Flask, request

from storage import pop_state, save_token

app = Flask(__name__)

@app.get("/")
def home():
    return "Drive to Telegram bot is running."

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/oauth/callback")
def oauth_callback():
    error = request.args.get("error")
    if error:
        return "Google authorization cancelled or denied: " + error, 400

    code = request.args.get("code")
    state = request.args.get("state")
    if not code or not state:
        return "Invalid OAuth callback.", 400

    user_id = pop_state(state)
    if not user_id:
        return "Authorization link expired. Go back to Telegram and run /login again.", 400

    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "redirect_uri": os.environ["BASE_URL"].rstrip("/") + "/oauth/callback",
            "grant_type": "authorization_code",
        },
        timeout=30,
    )

    if not response.ok:
        return "Google token exchange failed.", 400

    token = response.json()
    if "access_token" not in token:
        return "Google did not return an access token.", 400

    save_token(user_id, token)

    return (
        "<h2>Google Drive connected successfully.</h2>"
        "<p>You can close this page and return to Telegram.</p>"
    )
