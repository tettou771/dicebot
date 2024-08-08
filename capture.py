import time
import random
import os
import subprocess
from datetime import datetime
from picamera2 import Picamera2
import numpy as np
import cv2
from concurrent.futures import ThreadPoolExecutor, as_completed

class TimestampOverlay:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.font_scale = 0.7
        self.font_thickness = 2

    def apply_timestamp(self, frame, timestamp):
        timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
        
        # フレームがRGBAの場合、RGBに変換
        if frame.shape[2] == 4:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2RGB)
        
        # タイムスタンプのサイズを取得
        (text_width, text_height), _ = cv2.getTextSize(timestamp_str, self.font, self.font_scale, self.font_thickness)
        
        # 背景の矩形を描画
        cv2.rectangle(frame, (10, 10), (10 + text_width, 10 + text_height + 10), (0, 0, 0), -1)
        
        # タイムスタンプを描画
        cv2.putText(frame, timestamp_str, (10, 30), self.font, self.font_scale, (255, 255, 255), self.font_thickness, cv2.LINE_AA)
        
        return frame

def process_and_save_frame(frame, timestamp, filename, timestamp_overlay):
    timestamped_frame = timestamp_overlay.apply_timestamp(frame, timestamp)
    cv2.imwrite(filename, cv2.cvtColor(timestamped_frame, cv2.COLOR_RGB2BGR))

def take(debug=False, save_frames=False):
    print('ビデオ撮影開始')
    
    picam2 = Picamera2()
    video_config = picam2.create_video_configuration(main={"size": (480, 480), "format": "RGB888"})
    picam2.configure(video_config)

    timestamp_overlay = TimestampOverlay(480, 480)

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
    cv2.imwrite(image_path, cv2.cvtColor(timestamped_frame, cv2.COLOR_RGB2BGR))

    if debug:
        print(f"カメラのフル解像度: {picam2.camera_properties['PixelArraySize']}")
        print(f"ビデオ設定: {video_config}")

    start_time = time.time()
    frame_count = 0
    total_frames = duration * fps

    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_frame = {}
        
        while frame_count < total_frames:
            frame_time = start_time + (frame_count / fps)
            current_time = time.time()
            
            if current_time < frame_time:
                time.sleep(frame_time - current_time)
            
            frame = picam2.capture_array()
            timestamp = datetime.fromtimestamp(frame_time)
            
            frame_filename = os.path.join(temp_frames_dir, f"frame_{frame_count:04d}.jpg")
            future = executor.submit(process_and_save_frame, frame, timestamp, frame_filename, timestamp_overlay)
            future_to_frame[future] = frame_count

            if debug or save_frames:
                debug_frame_filename = f"debug/debug_frame_{frame_count:04d}.jpg"
                executor.submit(process_and_save_frame, frame, timestamp, debug_frame_filename, timestamp_overlay)
            
            frame_count += 1

        # すべてのフレーム処理が完了するのを待つ
        for future in as_completed(future_to_frame):
            frame_num = future_to_frame[future]
            try:
                future.result()
            except Exception as exc:
                print(f'{frame_num}番目のフレーム処理中にエラーが発生しました: {exc}')

    picam2.stop()
    picam2.close()

    # FFmpegを使用してフレームから動画を作成
    ffmpeg_cmd = [
        'ffmpeg',
        '-framerate', str(fps),
        '-i', f'{temp_frames_dir}/frame_%04d.jpg',
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-crf', '23',
        '-pix_fmt', 'yuv420p',
        '-y',
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
    data = take(debug=True, save_frames=True)
