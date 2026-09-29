import os
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient

client = MongoClient(os.environ["MONGODB_URI"])
dbx = client[os.environ.get("MONGODB_DB", "drive_to_tg")]

def save_state(state, user_id):
    dbx.oauth_states.update_one(
        {"_id": state},
        {"$set": {"user_id": int(user_id), "created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )

def pop_state(state):
    doc = dbx.oauth_states.find_one_and_delete({"_id": state})
    if not doc:
        return None
    if datetime.now(timezone.utc) - doc["created_at"] > timedelta(minutes=15):
        return None
    return doc["user_id"]

def save_token(user_id, token):
    dbx.tokens.update_one(
        {"_id": int(user_id)},
        {"$set": {"access_token": token["access_token"], "refresh_token": token.get("refresh_token"), "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )

def get_token(user_id):
    return dbx.tokens.find_one({"_id": int(user_id)})

def delete_token(user_id):
    dbx.tokens.delete_one({"_id": int(user_id)})
