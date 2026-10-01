from pathlib import Path
from pydub import AudioSegment

SRC = "data/style_refs/04 Track 04.mp3"   # đổi sang file bạn chọn
START, END = 20, 27                        # giây: đoạn 5-8s, có tiếng đều, không có khoảng lặng dài

Path("data/ref").mkdir(parents=True, exist_ok=True)
clip = AudioSegment.from_file(SRC)[START * 1000: END * 1000]
clip = clip.set_channels(1)
clip.export("data/ref/ref_A.wav", format="wav")
print("Đã cắt:", len(clip) / 1000, "giây")