import os

import tweepy

client = tweepy.Client(
    os.environ["BEARER_TOKEN"],
    os.environ["CONSUMER_KEY"],
    os.environ["CONSUMER_SECRET"],
    os.environ["OAUTH_TOKEN"],
    os.environ["OAUTH_TOKEN_SECRET"],
)

me: tweepy.User = client.get_me().data  # type:ignore
print(list(tweepy.Paginator(client.get_users_followers, id=me.id, max_results=1000).flatten()))

for follower in tweepy.Paginator(client.get_users_followers, id=me.id, max_results=1000).flatten():
    print(repr(follower))
# followers = client.get_users_followers(me.id, max_results=1000).data
