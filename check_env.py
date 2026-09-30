import sys, shutil

print("Python:", sys.version.split()[0])

import cv2, librosa, pydub, jiwer, pydantic, tenacity
print("OpenCV:", cv2.__version__)
print("librosa:", librosa.__version__)
print("pydantic:", pydantic.__version__)
print("jiwer OK, pydub OK, tenacity OK")

print("ffmpeg:", "OK -> " + shutil.which("ffmpeg") if shutil.which("ffmpeg") else "KHÔNG TÌM THẤY")