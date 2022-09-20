# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import os, sys, subprocess
from argparse import ArgumentParser
import time, datetime

from flask import Flask, request, abort
from linebot import (
    LineBotApi, WebhookParser
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, VideoSendMessage,
    SourceUser, SourceGroup, SourceRoom,
    TemplateSendMessage, ConfirmTemplate, MessageAction,
    ButtonsTemplate, ImageCarouselTemplate, ImageCarouselColumn, URIAction,
    PostbackAction, DatetimePickerAction,
    CameraAction, CameraRollAction, LocationAction,
    CarouselTemplate, CarouselColumn, PostbackEvent,
    StickerMessage, StickerSendMessage, LocationMessage, LocationSendMessage,
    ImageMessage, VideoMessage, AudioMessage, FileMessage,
    UnfollowEvent, FollowEvent, JoinEvent, LeaveEvent, BeaconEvent,
    MemberJoinedEvent, MemberLeftEvent,
    FlexSendMessage, BubbleContainer, ImageComponent, BoxComponent,
    TextComponent, IconComponent, ButtonComponent,
    SeparatorComponent, QuickReply, QuickReplyButton,
    ImageSendMessage)
import configparser, time, queue, threading

# twitter
import tweepy

# original
import capture, solenoid

app = Flask(__name__)

# get credentials information and more
config_ini = configparser.ConfigParser()
config_ini.read('config.ini', encoding='utf-8')

# LINE keys
channel_secret = config_ini['linebot'].get('LINE_CHANNEL_SECRET')
channel_access_token = config_ini['linebot'].get('LINE_CHANNEL_ACCESS_TOKEN')
server_url = config_ini['linebot'].get('SERVER_URL')

# Twitter keys
twitter_id = config_ini['twitter'].get('ID')
twitter_ck = config_ini['twitter'].get('CONSUMER_KEY')
twitter_cs = config_ini['twitter'].get('CONSUMER_SECRET')
twitter_at = config_ini['twitter'].get('ACCESS_TOKEN')
twitter_ats = config_ini['twitter'].get('ACCESS_TOKEN_SECRET')
twitter_bt = config_ini['twitter'].get('BEABER_TOKEN')

# request queue
# it can't roll dice in multi thread, but callback is multithread
# then separate dice rolling thread from callback
maxQueueNum = 10
diceQueue = queue.LifoQueue(maxQueueNum)

if channel_secret is None:
    print('Specify LINE_CHANNEL_SECRET as environment variable.')
    sys.exit(1)
if channel_access_token is None:
    print('Specify LINE_CHANNEL_ACCESS_TOKEN as environment variable.')
    sys.exit(1)
if server_url is None:
    print('Specify SERVER_URL as environment variable.')
    sys.exit(1)

line_bot_api = LineBotApi(channel_access_token)
parser = WebhookParser(channel_secret)

@app.route('/')
def hello_world():
    return 'DiceBot is running.';

@app.route('/callback', methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # parse webhook body
    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        abort(400)

    # if event is MessageEvent and message is TextMessage, then echo text
    for event in events:
        if not isinstance(event, MessageEvent):
            continue
        if not isinstance(event.message, TextMessage):
            continue

        # check message in keyword
        keywords = ['dice', 'Dice', 'DICE', 'ダイス', 'サイコロ', 'さいころ', '賽', '乱数', '🎲', 'random', 'Random', 'RANDOM']
        isDiceRequest = False
        containKeyword = ''
        for keyword in keywords:
            if keyword in event.message.text:
                isDiceRequest = True
                containKeyword = keyword
                break

        if not isDiceRequest:
            return

        messageFrom = ''
        queue = []
        queue['platform'] = 'line'
        if isinstance(event.source, SourceGroup):
            queue['sendTarget'] = event.source.group_id
            messageFrom = 'group'
            print('message from group')
        elif isinstance(event.source, SourceRoom):
            queue['sendTarget'] = event.source.room_id
            messageFrom = 'room'
            print('message from room')
        else:
            queue['sendTarget'] = event.source.user_id
            messageFrom = 'user'
            print('message from user')

        queueAdded = False
        if diceQueue.full():
            print('queue queueAdded')
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text = 'ごめんなさい、混み合って生産が追いつかないので少し待ってから試してみてくだい')
            )
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text = '新鮮な乱数を生産しています')
            )

            diceQueue.put(queue)
            queueAdded = True
            
            print('add to queue: ' + sendTarget)

        # log to csv
        csvPath = 'csv/dicebot_statistics_' + datetime.datetime.now().strftime('%Y-%m-%d') + '.csv'
        with open(csvPath, 'a') as f:
            l = datetime.datetime.now().strftime('%Y/%m/%d') + ',' + datetime.datetime.now().strftime('%H:%M:%S') + ',' + str(time.time()) + ','+ messageFrom + ',' + containKeyword + ',' + str(queueAdded)
            print(l, file = f)

    return 'OK'

# Twitter
def on_twitter():
    pass

Client = tweepy.Client(twitter_bt, twitter_ck, twitter_cs, twitter_at, twitter_ats)

class ClientProcess(tweepy.StreamingClient):
    def on_data(self, raw_data):
        response = json.loads(raw_data)
        # ツイートidを取得する
        tweet_id = response["data"]["id"]
        # ツイートの文章を取得する
        reply_text: str = response["data"]["text"]

        print('Get Twitter message')
        print(reply_text)
        
        Client.create_tweet(
            text='test',
            in_reply_to_tweet_id=tweet_id
        )


def dice_rolling_thread():
    print('Start dicebot machine')
    
    while True:
        # if it has queue, take video and reply
        while not diceQueue.empty():
            queue = diceQueue.get()

            # begin roll the dice
            solenoid.renda_threaded()

            # take capture and make video message
            captured = capture.take()
            videoMessage = VideoSendMessage(
                original_content_url = server_url + '/' + captured[0],
                preview_image_url = server_url + '/' + captured[1]
            )

            if target['platform'] == 'line':
                # post to LINE
                line_bot_api.push_message(
                    queue['sendTarget'], 
                    [videoMessage]
                )

            elif target['platform'] == 'twitter':
                # post to Twitter (TODO)
                pass

        
        time.sleep(0.5)
        
if __name__ == "__main__":
    # run dice rolling thread
    thread = threading.Thread(target=dice_rolling_thread)
    thread.start()

    # Twitter thresd
    print('begin Twitter')
    twitterClient = ClientProcess(twitter_bt)
    twitterClient.add_rules(tweepy.StreamRule(twitter_id))
    twitterClient.filter()

    # FLASK thread for LINE webhook
    arg_parser = ArgumentParser(
        usage='Usage: python ' + __file__ + ' [--port <port>] [--help]'
    )
    arg_parser.add_argument('-p', '--port', type=int, default=80, help='port')
    arg_parser.add_argument('-d', '--debug', default=False, help='debug')
    options = arg_parser.parse_args()
    #app.run(debug=options.debug, port=options.port)
    app.run(debug=options.debug, host="0.0.0.0", port=options.port)
    
