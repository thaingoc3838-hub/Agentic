import sys
from pathlib import Path
from pydub import AudioSegment

# Cách dùng: python cut_ref.py "<file mp3>" <giây bắt đầu> <giây kết thúc> <tên A hoặc B>
src, start, end, name = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]

Path("data/ref").mkdir(parents=True, exist_ok=True)
clip = AudioSegment.from_file(src)[start * 1000: end * 1000].set_channels(1)
out = f"data/ref/ref_{name}.wav"
clip.export(out, format="wav")
print(f"Đã lưu {out}: {len(clip) / 1000} giây")