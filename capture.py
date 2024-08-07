import time
import random
import os
import subprocess
from datetime import datetime
from picamera2 import Picamera2
from PIL import Image, ImageDraw, ImageFont
import numpy as np

class TimestampOverlay:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        try:
            self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        except IOError:
            print("カスタムフォントの読み込みに失敗しました。デフォルトを使用します。")
            self.font = ImageFont.load_default()

    def create_overlay(self, text):
        overlay = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        position = (10, 10)
        for offset in [(1,1), (-1,1), (1,-1), (-1,-1)]:
            draw.text((position[0]+offset[0], position[1]+offset[1]), text, font=self.font, fill=(0, 0, 0, 255))
        draw.text(position, text, font=self.font, fill=(255, 255, 255, 255))
        return np.array(overlay)

    def apply_timestamp(self, frame, timestamp):
        overlay = self.create_overlay(timestamp.strftime('%Y-%m-%d %H:%M:%S'))
        
        # フレームが2次元（グレースケール）の場合、3次元（RGB）に変換
        if len(frame.shape) == 2:
            frame = np.stack((frame,) * 3, axis=-1)
        elif frame.shape[2] == 4:  # RGBAの場合、RGBに変換
            frame = frame[:,:,:3]
        
        # オーバーレイのアルファチャンネルを使用してフレームと結合
        alpha = overlay[:,:,3].astype(float) / 255.0
        alpha = np.expand_dims(alpha, axis=2)
        rgb = overlay[:,:,:3]
        
        blended = (rgb * alpha + frame * (1 - alpha)).astype(np.uint8)
        return blended

def take(debug=False, save_frames=False):
    print('ビデオ撮影開始')
    
    picam2 = Picamera2()
    video_config = picam2.create_video_configuration(main={"size": (480, 480), "format": "RGB888"})
    picam2.configure(video_config)

    # TimestampOverlayインスタンスを作成
    timestamp_overlay = TimestampOverlay(480, 480)

    # デバッグディレクトリが存在することを確認
    os.makedirs("debug", exist_ok=True)
    os.makedirs("static/videos", exist_ok=True)

    name = f"{time.time()}_{random.randint(0, 1000000)}"
    video_path = f"static/videos/{name}.mp4"
    image_path = f"static/videos/{name}.jpg"
    temp_frames_dir = f"temp_frames_{name}"
    os.makedirs(temp_frames_dir, exist_ok=True)
    duration = 5
    fps = 30

    picam2.start()
    
    # タイムスタンプ付きの静止画を撮影
    frame = picam2.capture_array()
    timestamped_frame = timestamp_overlay.apply_timestamp(frame, datetime.now())
    Image.fromarray(timestamped_frame).save(image_path)

    if debug:
        print(f"カメラのフル解像度: {picam2.camera_properties['PixelArraySize']}")
        print(f"ビデオ設定: {video_config}")

    start_time = time.time()
    frame_count = 0
    total_frames = duration * fps

    while frame_count < total_frames:
        frame_time = start_time + (frame_count / fps)
        current_time = time.time()
        
        if current_time < frame_time:
            time.sleep(frame_time - current_time)
        
        frame = picam2.capture_array()
        timestamp = datetime.fromtimestamp(frame_time)
        timestamped_frame = timestamp_overlay.apply_timestamp(frame, timestamp)
        
        # フレームを一時的に保存
        frame_filename = os.path.join(temp_frames_dir, f"frame_{frame_count:04d}.jpg")
        Image.fromarray(timestamped_frame).save(frame_filename)

        if debug or save_frames:
            debug_frame_filename = f"debug/debug_frame_{frame_count:04d}.jpg"
            Image.fromarray(timestamped_frame).save(debug_frame_filename)
            if debug:
                print(f"デバッグフレームを保存しました: {debug_frame_filename}")
        
        frame_count += 1

    picam2.stop()

    # FFmpegを使用してフレームから動画を作成
    ffmpeg_cmd = [
        'ffmpeg',
        '-framerate', str(fps),
        '-i', f'{temp_frames_dir}/frame_%04d.jpg',
        '-c:v', 'libx264',
        '-pix_fmt', 'yuv420p',
        '-y',  # 既存のファイルを上書き
        video_path
    ]
    subprocess.run(ffmpeg_cmd, check=True)

    # 一時フレームディレクトリを削除
    for file in os.listdir(temp_frames_dir):
        os.remove(os.path.join(temp_frames_dir, file))
    os.rmdir(temp_frames_dir)

    print(f'ビデオ: {video_path} 画像: {image_path}')

    return (video_path, image_path)

if __name__ == '__main__':
    # デバッグ出力を全て表示する場合はdebug=True、フレームを保存するだけの場合はsave_frames=Trueを設定してください
    data = take(debug=True, save_frames=False)