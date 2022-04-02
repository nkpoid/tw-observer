import json
import logging
import os
import re
from collections import OrderedDict
from datetime import datetime
from logging import getLogger
from typing import List

import requests
import tweepy
from apscheduler.schedulers.blocking import BlockingScheduler
from pymongo import MongoClient

scheduler = BlockingScheduler(timezone="Asia/Tokyo")
logging.basicConfig(level=logging.INFO)


def load_jsonc(filepath: str):
    with open(filepath) as f:
        text = f.read()
    text_without_comment = re.sub(r"/\*[\s\S]*?\*/|//.*", "", text)
    return json.loads(text_without_comment)


@scheduler.scheduled_job("interval", minutes=15, next_run_time=datetime.now())  # type: ignore
def observe_task():
    logger = getLogger("tw-observer")
    logger.info("Start observe task...")

    mc = MongoClient(os.environ["MONGODB_URI"])
    db = mc.tw_observer
    notifications: List[str] = []

    tokens = load_jsonc("./tokens.jsonc")
    for token in tokens:
        tc = tweepy.Client(
            os.environ["BEARER_TOKEN"],
            os.environ["CONSUMER_KEY"],
            os.environ["CONSUMER_SECRET"],
            token["oauth_token"],
            token["oauth_token_secret"],
        )

        me: tweepy.User = tc.get_me(user_fields=["protected"]).data  # type:ignore
        logger.info(f"Processing @{me.username}")
        collection = db[me.username]

        prev_followers = list(collection.find({}, {"_id": False}))
        _current_followers = list(
            tweepy.Paginator(tc.get_users_followers, id=me.id, user_auth=me.protected, max_results=1000).flatten()
        )
        current_followers = [{"id": u.id, "username": u.username} for u in _current_followers]

        for pf in prev_followers:
            userid = pf["id"]
            cf = next(filter(lambda _cf: _cf["id"] == userid, current_followers), None)
            if cf:
                if pf["username"] != cf["username"]:
                    notifications.append(f"@{pf['username']} has renamed to @{cf['username']}")
            else:
                _res = tc.get_user(id=userid)
                if errors := _res.errors:  # type:ignore
                    notifications.append(errors[0]["detail"])
                else:
                    user: tweepy.User = _res.data  # type:ignore
                    notifications.append(
                        f"[@{user.username}](https://twitter.com/{user.username}) has been removed **{me.username}**"
                    )

        collection.delete_many({})
        collection.insert_many(current_followers)

    if notifications:
        requests.post(
            os.environ["WEBHOOK_URL"],
            json.dumps({"embeds": [{"description": "\n".join(list(OrderedDict.fromkeys(notifications)))}]}),
            headers={"Content-Type": "application/json"},
        )

    mc.close()
    logger.info("Done.")


if __name__ == "__main__":
    scheduler.start()
