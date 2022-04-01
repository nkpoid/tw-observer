import os

import tweepy

auth = tweepy.OAuthHandler(os.environ['CONSUMER_KEY'], os.environ['CONSUMER_SECRET'])
print(auth.get_authorization_url())
verifier = input('Verifier:')
print(auth.get_access_token(verifier))
