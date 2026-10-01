"""a3_profile.py - Tổng hợp style_features.json thành hồ sơ riêng cho từng người ngâm."""
import json
from pathlib import Path

import numpy as np

from schemas import Stat, StyleProfile

feats = json.loads(Path("profiles/style_features.json").read_text(encoding="utf-8"))
speakers = json.loads(Path("profiles/speakers.json").read_text(encoding="utf-8"))

# Giữ lại 1 file mỗi người làm tập kiểm tra cho A6 (không dùng để rút style)
HOLDOUT = {}          # ví dụ: {0: "13 Track 13.mp3", 1: "14 Track 14.mp3"} - điền sau khi nghe


def stat(rows: list[dict], key: str) -> Stat | None:
    vals = [r[key] for r in rows if r.get(key) is not None]
    if not vals:
        return None
    return Stat(mean=float(np.median(vals)), std=float(np.std(vals)))   # mean = trung vị


for label, sid in ((0, "A"), (1, "B")):
    rows = [f for f in feats
            if speakers.get(f["file"]) == label and f["file"] != HOLDOUT.get(label)]
    # File có quá ít lần nghỉ thì số đo nghỉ không đáng tin
    pause_rows = [r for r in rows if r["n_short_pauses"] >= 5]

    profile = StyleProfile(
        speaker_id=sid,
        source_files=[r["file"] for r in rows],
        pitch_hz=stat(rows, "pitch_hz_mean"),
        pause_line_ms=stat(pause_rows, "pause_short_ms_mean"),
        pause_stanza_ms=stat(pause_rows, "pause_long_ms_mean"),
        energy_db=stat(rows, "energy_db_mean"),
        description_vi="(điền sau khi Gemini nghe và mô tả)",
    )
    out = Path(f"profiles/style_profile_{sid}.json")
    out.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
    print(f"Người {sid}: {len(rows)} file ->", out)
    print(profile.model_dump_json(indent=2))