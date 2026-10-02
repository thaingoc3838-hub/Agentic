import sys
import librosa
import numpy as np

y, sr = librosa.load(sys.argv[1], sr=22050, mono=True)
rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
db = librosa.amplitude_to_db(rms + 1e-9, ref=np.median(rms))
active = db > -12
segs, start = [], None
for i, a in enumerate(active):
    if a and start is None:
        start = i
    elif not a and start is not None:
        segs.append((start, i)); start = None
if start is not None:
    segs.append((start, len(active)))
gaps = [round((segs[i + 1][0] - segs[i][1]) * 512 / sr * 1000) for i in range(len(segs) - 1)]
print("Thời lượng:", round(len(y) / sr, 1), "s | số đoạn có tiếng:", len(segs))
print("Các khoảng nghỉ (ms), lớn đến nhỏ:", sorted(gaps, reverse=True))