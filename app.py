import json
import logging
import os
import re
from collections import OrderedDict
from datetime import datetime
from logging import getLogger

import requests
import tweepy
from apscheduler.schedulers.blocking import BlockingScheduler

import redis


def load_jsonc(filepath: str):
    with open(filepath) as f:
        text = f.read()
    text_without_comment = re.sub(r"/\*[\s\S]*?\*/|//.*", "", text)
    return json.loads(text_without_comment)


def to_twitter_link(username: str) -> str:
    return f"[@{username}](https://twitter.com/{username})"


def friendship_observe_task(r: redis.Redis):
    logger = getLogger("tw-observer")
    logger.info("Start observe task...")

    notifications: list[str] = []

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

        redis_key = f"friendship_observe:{me.username}"
        if d := r.get(redis_key):
            prev_followers = json.loads(d)
        else:
            prev_followers = []
        _current_followers = list(
            tweepy.Paginator(tc.get_users_followers, id=me.id, user_auth=me.protected, max_results=1000).flatten()
        )
        current_followers = [{"id": u.id, "username": u.username} for u in _current_followers]

        for pf in prev_followers:
            userid = pf["id"]
            cf = next(filter(lambda _cf: _cf["id"] == userid, current_followers), None)
            if cf:
                if pf["username"] != cf["username"]:
                    notifications.append(f"@{pf['username']} has renamed to {to_twitter_link(cf['username'])}")
            else:
                _res = tc.get_user(id=userid)
                if errors := _res.errors:  # type:ignore
                    notifications.append(errors[0]["detail"])
                else:
                    user: tweepy.User = _res.data  # type:ignore
                    notifications.append(f"{to_twitter_link(user.username)} has been removed **{me.username}**")

        r.set(redis_key, json.dumps(current_followers))

    if notifications:
        requests.post(
            os.environ["WEBHOOK_URL"],
            json.dumps({"embeds": [{"description": "\n".join(list(OrderedDict.fromkeys(notifications)))}]}),
            headers={"Content-Type": "application/json"},
        )

    logger.info("Done.")


if __name__ == "__main__":
    scheduler = BlockingScheduler(timezone="Asia/Tokyo")
    logging.basicConfig(level=logging.INFO)

    r = redis.from_url(os.environ["REDIS_URL"])

    scheduler.add_job(friendship_observe_task, "interval", [r], minutes=15, next_run_time=datetime.now())  # type:ignore

    scheduler.start()
