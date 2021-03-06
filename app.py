import streamlit as st
from scenedetect import VideoManager
from scenedetect import SceneManager
from custom_detector import BlackWhiteThresholdDetector
import tempfile
import subprocess
import numpy as np
import os

def chapter_detect(video):
	'''動画内の真っ黒/真っ白シーンを区切りとしてチャプターを検出する'''
	video_manager = VideoManager([video])
	scene_manager = SceneManager()
	scene_manager.add_detector(BlackWhiteThresholdDetector(min_percent=0.98))

	# Improve processing speed by downscaling before processing.
	video_manager.set_downscale_factor()

	# Start the video manager and perform the scene detection.
	video_manager.start()
	scene_manager.detect_scenes(frame_source=video_manager)

	# Each returned scene is a tuple of the (start, end) timecode.
	scene_list = scene_manager.get_scene_list()
	return scene_list

def cut_video(input_video_path, output_video_path, start_time, end_time):
	'''動画の一部を無劣化で切り出して保存する'''
	cmd = f"ffmpeg -y -i {input_video_path} -ss {start_time} -to {end_time} -c:v copy -c:a copy {output_video_path}"
	subprocess.run(cmd, shell=True)

def merge_video(merge_list_path, output_video_path):
	'''チェックされた動画を結合して保存する'''
	cmd = f"ffmpeg -y -f concat -safe 0 -i {merge_list_path} -c copy {output_video_path}"
	subprocess.run(cmd, shell=True)


st.title("Video Chapter Detector")
st.write("動画内の暗転/明転を検出して分割します")
st.markdown('''
```
Step1: 動画をアップロードして、チャプターが検出されるのを待つ（目安: 10分の動画 -> 約1分で完了）
Step2: 好きなチャプターを選んで「結合」ボタンをクリック
Step3: 少し待てば選んだチャプターだけの動画が完成！（PCの方はそのままDLもできるはずです）
```
''')

content = st.empty()

video_file = content.file_uploader("Choose a file")
if video_file is not None:

	video_bytes = video_file.read()

	# OpenCVで読めるように一時ファイルとして保存
	temp_dir = tempfile.TemporaryDirectory()
	temp_video_full = os.path.join(temp_dir.name, "full.mp4")
	with open(temp_video_full, "wb") as f:
		f.write(video_bytes)

	# 編集前の動画を表示
	with content.container():
		st.video(temp_video_full)

	### チャプター検出
	with st.spinner("チャプター検出中・・・"):
		# チャプター検出
		detected_chapters = chapter_detect(temp_video_full)

	### チャプターごとの動画作成
	chapter_files = []
	for i, scene in enumerate(detected_chapters):
		tmp_chapter_file = os.path.join(temp_dir.name, f"chap_{i+1}.mp4")
		cut_video(temp_video_full, tmp_chapter_file, scene[0].get_seconds(), scene[1].get_seconds())
		chapter_files.append(tmp_chapter_file)


	### 結果表示
	with content.container():
		st.success(f"{len(chapter_files)}つのチャプターが検出されました！")
		with st.form("chapter_select"):
			### チャプターリストを2カラムで表示
			col1, col2 = st.columns(2)
			checks = [0] * len(chapter_files)   # 残すチャプターを決めるチェックボックス用のリスト
			for i, (f, c) in enumerate(zip(chapter_files, detected_chapters)):
				text = f"Chapter {i+1}:\n{c[0].get_timecode()[3:]} - {c[1].get_timecode()[3:]}"
				if i % 2 == 0:
					with col1:
						checks[i] = st.checkbox(text)
						st.video(f)
				elif i % 2 == 1:
					with col2:
						checks[i] = st.checkbox(text)
						st.video(f)

			### チェックされた動画のみを結合
			submit_btn = st.form_submit_button("チェックしたチャプターを結合")
			if submit_btn:
				with st.spinner("結合中・・・"):
					# チェックされた動画パスをtxtに書き込む
					checked_chapters = [f for f, c in zip(chapter_files, checks) if c]
					checked_chapter_file = os.path.join(temp_dir.name, "chapter_list.txt")
					with open(checked_chapter_file, "w") as f:
						for c in checked_chapters:
							f.write(f"file {c}\n")

					# 結合
					merged_video = os.path.join(temp_dir.name, "merged.mp4")
					merge_video(checked_chapter_file, merged_video)

				# 結合した動画を表示
				with content.container():
					st.success(f"{len(checked_chapters)}つのチャプターを結合しました！")
					st.video(merged_video)

	### 動画を削除
	temp_dir.cleanup()
