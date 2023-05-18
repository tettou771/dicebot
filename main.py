# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import os, sys, subprocess
from argparse import ArgumentParser
import time, datetime
from pathlib import Path
from flask import Flask, request, abort, send_from_directory, jsonify
import string, random # use in generate_random_string()

from nextcloud import (
    upload_to_nextcloud, 
    create_public_link
)
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

# ChatGPT responses
chatGptResponse = []

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

# テキストメッセージを返すメソッド
# エラー時にも使う
def send_line_message(target, error_message):
    text_message = TextSendMessage(text=error_message)
    line_bot_api.push_message(target, [text_message])

@app.route('/')
def hello_world():
    return 'DiceBot is running.'

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
        if isinstance(event.source, SourceGroup):
            sendTarget = event.source.group_id
            messageFrom = 'group'
            print('message from group')
        elif isinstance(event.source, SourceRoom):
            sendTarget = event.source.room_id
            messageFrom = 'room'
            print('message from room')
        else:
            sendTarget = event.source.user_id
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

            protocol = 'LINE'
            queue = (protocol, sendTarget)
            diceQueue.put(queue)
            queueAdded = True

        # log to csv
        csvPath = 'csv/dicebot_statistics_' + datetime.datetime.now().strftime('%Y-%m-%d') + '.csv'
        with open(csvPath, 'a') as f:
            l = datetime.datetime.now().strftime('%Y/%m/%d') + ',' + datetime.datetime.now().strftime('%H:%M:%S') + ',' + str(time.time()) + ','+ messageFrom + ',' + containKeyword + ',' + str(queueAdded)
            print(l, file = f)

    return 'OK'

def dice_rolling_thread():
    print('Start loop')
    
    while True:
        # if it has queue, take video and reply
        while not diceQueue.empty():
            
            # begin roll the dice
            solenoid.renda_threaded()

            # take capture
            captured = capture.take()

            # upload to nextcloud
            date_str = datetime.datetime.now().strftime('%Y-%m-%d')
            remote_folder_path = f'/dicebot/videos/video_{date_str}'
            remote_video_file_path = f'{remote_folder_path}/{Path(captured[0]).name}'
            remote_thumb_img_path = ''
            remote_result_img_path = ''
            direct_video_link = ''
            success, error_message = upload_to_nextcloud(captured[0], remote_video_file_path)

            if success:
                remote_thumb_img_path = f'{remote_folder_path}/{Path(captured[1]).name}'
                success, error_message = upload_to_nextcloud(captured[1], remote_thumb_img_path)
            
            if success:
                remote_result_img_path = f'{remote_folder_path}/{Path(captured[2]).name}'
                success, error_message = upload_to_nextcloud(captured[2], remote_result_img_path)

            if success:
                direct_video_link, error_message = create_public_link(remote_video_file_path)
                direct_thumb_link, error_message = create_public_link(remote_thumb_img_path)
                direct_result_link, error_message = create_public_link(remote_result_img_path)

            # check queue
            queue = diceQueue.get()
            protocol = queue[0]
            target = queue[1]

            # send to LINE
            if protocol == 'LINE':
                if not success:
                    send_line_message(target, error_message)
                else:
                    # make LINE message
                    videoMessage = VideoSendMessage(
                        original_content_url = direct_video_link,
                        preview_image_url = direct_thumb_link
                    )

                    line_bot_api.push_message(
                        target, 
                        [videoMessage]
                    )

            # send to ChatGPT
            elif protocol == 'ChatGPT':
                response = {'target':target}
                data = {}

                if not success:
                    response['status'] = 429
                    data['error'] = 'Video generation error.'
                else:
                    response['status'] = 200
                    data['video_url'] = direct_video_link
                    data['thumb_url'] = direct_thumb_link
                    data['result_url'] = direct_result_link

                response ['data'] = data
                
                chatGptResponse.append(response)
        
        time.sleep(0.5)

# ChatGPT対応

@app.route('/static/<path:filename>')
def serve_static_files():
    return send_from_directory(app.static_folder, filename)

@app.route('/.well-known/<path:path>')
def send_well_known(path):
    return send_from_directory('.well-known', path)
    
# @app.route('/manifest.json')
# def serve_manifest():
#     return send_from_directory(app.static_folder, 'manifest.json')

# @app.route('/openapi.yaml')
# def serve_openapi():
#     return send_from_directory(app.static_folder, 'openapi.yaml')

@app.route('/rollthedice', methods=['GET'])
def roll_the_dice():
    # append roll task
    protocol = 'ChatGPT'
    random_string = generate_random_string(16)
    queue = (protocol, random_string)
    diceQueue.put(queue)

    data = {}

    # サイコロを待ち、結果が来たら返す
    # 一方で、Timeoutしたら 429 というステータスコードで
    startTime = time.time()
    timeoutTime = 60
    while True:
        for response in chatGptResponse:
            if response['target'] == random_string:
                data = response['data']
                chatGptResponse.remove(response)
                if response['status'] == 200:
                    # JSON形式でリンクを返します。
                    return jsonify(data)
                else:
                    abort(429, description=jsonify(data))
        
        if time.time() - startTime > timeoutTime:
            data = { 'error' : 'Timeout' }
            abort(408, description=jsonify(data))

        time.sleep(0.5)

def generate_random_string(length):
    # 大文字、小文字のアルファベットと数字からなる文字列を生成します。
    characters = string.ascii_letters + string.digits
    random_string = ''.join(random.choice(characters) for _ in range(length))
    return random_string

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
