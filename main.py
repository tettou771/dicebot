# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import os, sys, subprocess
from argparse import ArgumentParser

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

# original
import capture, solenoid

app = Flask(__name__)

# get credentials information and more
config_ini = configparser.ConfigParser()
config_ini.read('config.ini', encoding='utf-8')
channel_secret = config_ini['linebot'].get('LINE_CHANNEL_SECRET')
channel_access_token = config_ini['linebot'].get('LINE_CHANNEL_ACCESS_TOKEN')
server_url = config_ini['linebot'].get('SERVER_URL')

# request queue
# it can't roll dice in multi thread, but callback is multithread
# then separate dice rolling thread from callback
maxQueueNum = 5
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
        for keyword in keywords:
            if keyword in event.message.text:
                isDiceRequest = True
                break

        if not isDiceRequest:
            return

        if diceQueue.full():
            print('queue overflow')
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text = 'ごめんなさい、混み合って生産が追いつかないので少し待ってから試してみてくだい')
            )
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text = '新鮮な乱数を生産しています')
            )

            if isinstance(event.source, SourceGroup):
                sendTarget = event.source.group_id
                print('message from group')
            elif isinstance(event.source, SourceRoom):
                sendTarget = event.source.room_id
                print('message from room')
            else:
                sendTarget = event.source.user_id
                print('message from user')

            diceQueue.put(sendTarget)
            
            print('add to queue: ' + sendTarget)

    return 'OK'

def dice_rolling_thread():
    print('Start loop')
    
    while True:
        # if it has queue, take video and reply
        while not diceQueue.empty():
            target = diceQueue.get()
            
            # begin roll the dice
            solenoid.renda_threaded()

            # take capture and make video message
            captured = capture.take()
            videoMessage = VideoSendMessage(
                original_content_url = server_url + '/' + captured[0],
                preview_image_url = server_url + '/' + captured[1]
            )

            line_bot_api.push_message(
                target, 
                [videoMessage]
            )
        
        time.sleep(0.5)
        
if __name__ == "__main__":
    # run dice rolling thread
    thread = threading.Thread(target=dice_rolling_thread)
    thread.start()

    arg_parser = ArgumentParser(
        usage='Usage: python ' + __file__ + ' [--port <port>] [--help]'
    )
    arg_parser.add_argument('-p', '--port', type=int, default=80, help='port')
    arg_parser.add_argument('-d', '--debug', default=False, help='debug')
    options = arg_parser.parse_args()

    #app.run(debug=options.debug, port=options.port)
    app.run(debug=options.debug, host="0.0.0.0", port=options.port)
