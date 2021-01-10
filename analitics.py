# coding=utf-8
import tweepy
import requests
import json
import re
import os

# .envからTwitter APIの認証情報を取得する
CONSUMER_KEY = os.environ['CONSUMER_KEY']
CONSUMER_SECRET = os.environ['CONSUMER_SECRET']
ACCESS_TOKEN = os.environ['ACCESS_TOKEN']
ACCESS_TOKEN_SECRET = os.environ['ACCESS_TOKEN_SECRET']

# .envからGOOGLE_ACCESS_TOKENを取得する
GOOGLE_ACCESS_TOKEN = os.environ['GOOGLE_ACCESS_TOKEN']
ANALYZE_SENTIMENT_URL = 'https://language.googleapis.com/v1/documents:analyzeSentiment?key={}'.format(
    GOOGLE_ACCESS_TOKEN)

# .envからWEBHOOK_URLを取得する
WEBHOOK_URL = os.environ['WEBHOOK_URL']

def analyse_sentiment(content):
    header = {'Content-Type': 'application/json'}
    body = {
        "document": {
            "type": "PLAIN_TEXT",
            "language": "JA",
            "content": content
        },
        "encodingType": "UTF8"
    }
    return requests.post(ANALYZE_SENTIMENT_URL, headers=header, json=body).json()


def get_sentiment_score(response):
    return response['documentSentiment']['score']


# Slackに投稿する
def post_text_with_icon(channel, text, name, icon):
    slack_post_params = json.dumps({
        'channel': channel,  # 投稿先のチャンネル名
        'text': text,  # 投稿するテキスト
        'username': name,  # 投稿のユーザー名
        'icon_emoji': icon,  # 投稿のプロフィール画像に入れる絵文字
        'link_names': 1,  # メンションを有効にする
    })
    requests.post(WEBHOOK_URL, data=slack_post_params)


# Twitter APIの認証
auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
api = tweepy.API(auth)

# ツイート検索する文章（ここを書き換えれば、検索する単語変えられる）
search_text = '緊急事態宣言'

# ツイートを検索する（リプライは対象外とする）
search_results = api.search(q=search_text, count=100, lang='ja', result_type='mixed', exclude_replies=True)

# ツイートを感情分析して感情スコアが-0.7以下のものは、Slack投稿する文章に加えていく。
tweet_dict = {}
max_analysis_count = 7
analysis_count = 0
for status in search_results:
    # 感情分析の回数上限になったら感情分析処理をやめる
    if analysis_count > max_analysis_count:
        break
    user = status.user
    lowered_name = user.name.lower()
    lowered_account_name = user.screen_name.lower()
    lowered_q = search_text.lower()
    follower_count = user.followers_count
    text = status.text
    # ※以下のツイートは感情分析対象外とする。
    # ・フォロワー10人以下
    # ・引用なしリツイート
    # ・アカウント名 or ユーザー名に検索単語（PayPay）が含まれているため検索結果に含まれてしまったツイート
    if 'RT @' in text or lowered_q in lowered_account_name or lowered_q in lowered_name or follower_count <= 10:
        continue

    # 感情分析して感情スコアを取得する。
    analysis_count += 1
    # URLは感情分析に不要なデータなので、分析対象から除く。
    formatted_text = re.sub(r'https?://[\w/:%#\$&\?\(\)~\.=\+\-…]+', "", text)
    analyse_response = analyse_sentiment(formatted_text)
    sentiment_score = get_sentiment_score(analyse_response)

    # 感情スコアが-0.7以下の場合にはSlack投稿文章用の辞書に追加する。
    if sentiment_score <= 0.7:
        tweet_link = 'https://twitter.com/{}/status/{}'.format(user.screen_name, str(status.id))
        tweet_dict[tweet_link] = sentiment_score

# Slack投稿用の文章を作成する。
if len(tweet_dict) > 0:
    text = '「{}」に関してポジティブなツイート一覧です！'.format(search_text)
    for link, score in tweet_dict.items():
        text += '\n\n{}'.format(link)
        print('感情スコア:{}, URL:{}'.format(score, link))
else:
    text = '「{}」に関してポジティブなツイートは見つかりませんでした。'

# Slack投稿する
channel_name = '89_短期転職_齋藤裕一郎'
user_name = 'テストBot'
icon = ':sunglasses:'
post_text_with_icon(channel_name, text, user_name, icon)