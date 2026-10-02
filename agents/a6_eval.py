"""a6_eval.py - Tác nhân A6: chấm độ giống phong cách của audio sinh ra."""
import json
import sys
from pathlib import Path

import numpy as np

from agents.a3_style import analyze_file
from schemas import Job, Status

HOLDOUT_PREFIX = ("11", "12", "13", "14")      # tập kiểm tra, không dùng để rút style
# chỉ số: (khóa trong analyze_file, độ lệch tối thiểu để tránh chia cho số quá nhỏ)
METRICS = {
    "pause_short_ms_mean": 40.0,
    "pause_long_ms_mean": 400.0,
    "speech_ratio": 0.02,
    "energy_db_mean": 1.0,
    "pitch_hz_std": 8.0,
}
SCORED = ("pause_short_ms_mean", "pause_long_ms_mean", "pitch_hz_std")   # tính vào điểm

def _is_holdout(name: str) -> bool:
    return name.startswith(HOLDOUT_PREFIX)


def reference_stats() -> dict:
    feats = json.loads(Path("profiles/style_features.json").read_text(encoding="utf-8"))
    ref = [f for f in feats if not _is_holdout(f["file"])]
    stats = {}
    for key, floor in METRICS.items():
        rows = ref
        if key.startswith("pause"):                 # file ít nghỉ thì số đo nghỉ không đáng tin
            rows = [f for f in ref if f["n_short_pauses"] >= 5]
        vals = [f[key] for f in rows if f.get(key) is not None]
        stats[key] = {"target": float(np.median(vals)),
                      "scale": max(float(np.std(vals)), floor)}
    return stats


def score_features(feat: dict, stats: dict | None = None) -> tuple[float, dict]:
    """Điểm 0-1 (1 = giống mẫu). Chỉ các chỉ số trong SCORED được tính vào điểm,
    các chỉ số còn lại vẫn in ra trong detail để quan sát."""
    stats = stats or reference_stats()
    detail, scores = {}, []
    for key, st in stats.items():
        counted = key in SCORED
        val = feat.get(key)
        if val is None:
            if key == "pause_short_ms_mean":         # không có nghỉ giữa dòng là lỗi
                detail[key] = {"value": None, "target": st["target"], "score": 0.0}
                scores.append(0.0)
            else:                                    # bài 1 khổ thì không có nghỉ giữa khổ
                detail[key] = {"value": None, "target": st["target"], "score": None}
            continue
        z = abs(val - st["target"]) / st["scale"]
        s = 1.0 / (1.0 + z)                          # liên tục, không bao giờ về 0 hẳn
        detail[key] = {"value": val, "target": round(st["target"], 1),
                       "delta": round(val - st["target"], 1),
                       "score": round(s, 3), "counted": counted}
        if counted:
            scores.append(s)
    return (round(float(np.mean(scores)), 3) if scores else 0.0), detail


def evaluate_file(path: str) -> tuple[float, dict]:
    return score_features(analyze_file(path))


def run(job: Job) -> Job:
    try:
        job.style_score, job.eval_detail = evaluate_file(job.audio_path)
        job.eval_rounds += 1
        job.status = Status.EVALUATED
    except Exception as e:
        job.errors.append(f"A6: {type(e).__name__}: {e}")
        job.status = Status.FAILED
    return job


if __name__ == "__main__":
    score, detail = evaluate_file(sys.argv[1])
    print("Điểm:", score)
    for k, v in detail.items():
        print(" ", k, v)