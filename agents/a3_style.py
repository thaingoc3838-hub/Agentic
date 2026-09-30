"""a3_style.py - Tác nhân A3: rút đặc trưng phong cách từ các file ngâm thơ mẫu."""
import glob
import json
from pathlib import Path

import librosa
import numpy as np

SR = 22050


def analyze_file(path: str) -> dict:
    y, sr = librosa.load(path, sr=SR, mono=True)
    duration = len(y) / sr

    # Đoạn có tiếng (bỏ khoảng lặng dưới 35 dB so với đỉnh)
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
    voiced = [(int(s * 512), int(e * 512)) for s, e in segs] 
    speech_time = sum(e - s for s, e in voiced) / sr

    # Quãng nghỉ = khoảng trống giữa các đoạn có tiếng
    gaps = [(voiced[i + 1][0] - voiced[i][1]) / sr * 1000 for i in range(len(voiced) - 1)]
    short_pauses = [g for g in gaps if 150 <= g < 900]    # nghỉ giữa dòng
    long_pauses = [g for g in gaps if g >= 900]           # nghỉ giữa khổ

    # Cao độ F0 (Hz), chỉ lấy khung có giọng
    f0, flag, _ = librosa.pyin(y, fmin=70, fmax=400, sr=sr)
    f0 = f0[~np.isnan(f0)]

    rms = librosa.feature.rms(y=y)[0]
    db = librosa.amplitude_to_db(rms + 1e-9)

    return {
        "file": Path(path).name,
        "duration_s": round(duration, 1),
        "speech_ratio": round(speech_time / duration, 3),
        "pause_short_ms_mean": round(float(np.mean(short_pauses)), 0) if short_pauses else None,
        "pause_long_ms_mean": round(float(np.mean(long_pauses)), 0) if long_pauses else None,
        "n_short_pauses": len(short_pauses),
        "n_long_pauses": len(long_pauses),
        "pitch_hz_mean": round(float(np.mean(f0)), 1) if len(f0) else None,
        "pitch_hz_std": round(float(np.std(f0)), 1) if len(f0) else None,
        "energy_db_mean": round(float(np.mean(db[db > db.max() - 40])), 1),
    }


if __name__ == "__main__":
    files = sorted(glob.glob("data/style_refs/*.mp3"))   # 10 file đầu để rút style
    results = []
    for f in files:
        print("Đang đo", Path(f).name, flush=True)
        results.append(analyze_file(f))
    Path("profiles").mkdir(exist_ok=True)
    Path("profiles/style_features.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    for r in results:
        print(r)