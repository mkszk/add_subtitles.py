#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import cv2
from PIL import Image, ImageFont, ImageDraw
import numpy as np
import moviepy.editor as mp
import sys
import csv
import os
from pydub import AudioSegment
import copy


def add_subtitle_to_image(image, output_x, output_y, text, font_object, font_color):
    pil = Image.fromarray(image)
    draw = ImageDraw.Draw(pil)
    draw.text((output_x,output_y), text, font=font_object, fill=font_color)
    return np.array(pil)


def add_subtitles_to_video(input_file, 
                           bg_file, bg_offset_x, bg_offset_y, 
                           output_file, output_width, output_height,
                           subtitles, font_object, font_color):
    try:
        capture = None
        writer = None
        
        output_x1 = 0
        output_y1 = 0
        output_w1 = output_height//2
        output_h1 = output_height
        output_x2 = 0
        output_y2 = 0
        output_w2 = output_width
        output_h2 = output_height
        output_x3 = output_w1+bg_offset_x
        output_y3 = bg_offset_y
        output_w3 = output_width
        output_h3 = output_height
        
        #print(output_x1, output_y1, output_w1, output_h1)
        #print(output_x2, output_y2, output_w2, output_h2)
        
        capture = cv2.VideoCapture(input_file)
        input_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        input_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        input_fps = int(capture.get(cv2.CAP_PROP_FPS))
        num_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        
        if input_height < input_width*2:
            input_w1 = input_width
            input_h1 = input_width*2
            input_x1 = 0
            input_y1 = (input_height-input_h1)//2
        else:
            input_w1 = input_width
            input_h1 = input_height
            input_x1 = 0
            input_y1 = 0
        input_w2 = input_width
        input_h2 = (output_h2*input_w2)//output_w2
        input_x2 = 0
        input_y2 = input_height//2
        
        #print(input_x1, input_y1, input_w1, input_h1)
        #print(input_x2, input_y2, input_w2, input_h2)
        
        fourcc = cv2.VideoWriter_fourcc('m', 'p', '4', 'v')
        writer = cv2.VideoWriter(output_file, fourcc, input_fps, (output_width, output_height))
        
        background = cv2.imread(bg_file,cv2.IMREAD_COLOR)
        
        for index_frames in range(num_frames):
            ret, input_frame = capture.read()
            if input_frame is None:
                break
            
            output_frame = np.zeros((output_height, output_width, 3), dtype=np.uint8)
            
            output_frame[output_y2:output_y2+output_h2,
                         output_x2:output_x2+output_w2] = cv2.resize(
                                                              background,
                                                              dsize=(output_w2,output_h2))
            output_frame[output_y1:output_y1+output_h1,
                         output_x1:output_x1+output_w1] = cv2.resize(
                                                              input_frame[input_y1:input_y1+input_h1,
                                                                          input_x1:input_x1+input_w1],
                                                              dsize=(output_w1,output_h1))
                                                          
            
            lst = [text for (tim,text) in subtitles if tim <= index_frames/input_fps]
            if lst:
                output_frame = add_subtitle_to_image(output_frame, output_x3, output_y3,
                                                     lst[-1], font_object, font_color)
            writer.write(output_frame)
    finally:
        if writer is not None:
            writer.release()
        if capture is not None:
            capture.release()

def create_jtalk(text, limit):
    speed = 1.0
    temp_wav = "temp.wav"
    while True:
        try:
            # pyopenjtalkを使えるなら実行
            import pyopenjtalk
            from scipy.io import wavfile
            x, sr = pyopenjtalk.tts(text, speed=speed)
            wavfile.write(temp_wav, sr, x.astype(np.int16))
        except:
            # VOICEVOXを使えるなら実行
            import requests
            import urllib.parse
            import json
            quoted = urllib.parse.quote(text)
            headers = {
                "accept": "audio/wav",
                "Content-Type": "application/json",
            }
            audio_query = requests.post("http://localhost:50021/"+
                f"audio_query?speaker=0&text={quoted}")
            audio_json = json.loads(audio_query.content)
            audio_json["speedScale"] = speed
            audio_data = requests.post("http://localhost:50021/"+
                "synthesis?speaker=0",
                data=json.dumps(audio_json),
                headers=headers)
            with open(temp_wav, "wb") as f:
                f.write(audio_data.content)
        voice = AudioSegment.from_wav(temp_wav)
        if os.path.exists(temp_wav):
            os.remove(temp_wav)
        if voice.duration_seconds < limit:
            return voice
        else:
            speed += 0.2

def copy_audio(input_file, subtitled_file, output_file, audio_file, subtitles):
    clip_in = mp.VideoFileClip(input_file)
    clip_in.audio.write_audiofile(audio_file)
    
    # BGMを読み込む、ついでに音量を下げる
    sound = AudioSegment.from_mp3(audio_file) - 10
    
    subtitles = copy.deepcopy(subtitles)
    subtitles.append((sound.duration_seconds, ""))
    for ((start,text),(end,_)) in zip(subtitles[:-1],subtitles[1:]):
        voice = create_jtalk(text.replace("\n", ""), end-start)
        sound = sound.overlay(voice, int(start*1000))
    sound.export(audio_file, format="mp3") 
    
    clip_out = mp.VideoFileClip(subtitled_file)
    clip_out.write_videofile(output_file, audio=audio_file)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("USAGE: python subtitles.py input_movie.mp4 subtitles.csv")
    else:
        input_file = sys.argv[1]
        subtitles_csv = sys.argv[2]
        subtitled_file = sys.argv[1]+".subtitled.mp4"
        output_file = sys.argv[1]+".output.mp4"
        audio_file = sys.argv[1]+".audio.mp3"
        
        # この辺りは自分の環境に合わせて調整が必要
        bg_file = '60d19a15f1ac2ed842000000.png'
        output_width = 1280
        output_height = 720
        font_path = r"C:\Windows\Fonts\meiryo.ttc"
        font_size = 54
        font_color = (0, 0, 0, 0)
        
        with open(subtitles_csv, encoding="utf_8") as fin:
            subtitles = []
            for row in csv.reader(fin):
                if row[0] == "font_path":
                    font_path = row[1]
                elif row[0] == "font_size":
                    font_size = int(row[1])
                elif row[0] == "font_color":
                    font_color = (int(row[1]), int(row[2]), int(row[3]), 0)
                else:
                    subtitles.append([float(row[0]), row[1]])
        
        try:
            font_object = ImageFont.truetype(font_path, font_size)
        except:
            font_object = ImageFont.truetype("/usr/share/fonts/truetype/takao-mincho/TakaoPMincho.ttf", font_size)
        
        add_subtitles_to_video(input_file,
                               bg_file, 20, 130,
                               subtitled_file, output_width, output_height,
                               subtitles, font_object, font_color)
        copy_audio(input_file, subtitled_file, output_file, audio_file, subtitles)
        
        if os.path.exists(subtitled_file):
            os.remove(subtitled_file)
        if os.path.exists(audio_file):
            os.remove(audio_file)

