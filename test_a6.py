import glob
import json
from pathlib import Path

from agents.a6_eval import HOLDOUT_PREFIX, evaluate_file, reference_stats, score_features

stats = reference_stats()
print(f"{'Mẫu':<28}{'Điểm':>7}")

# 1) Giọng ngâm thật trong tập kiểm tra (đã đo sẵn, không tốn thời gian)
feats = json.loads(Path("profiles/style_features.json").read_text(encoding="utf-8"))
for f in feats:
    if f["file"].startswith(HOLDOUT_PREFIX):
        s, _ = score_features(f, stats)
        print(f"{'[thật] ' + f['file']:<28}{s:>7}")

# 2) Audio sinh ra
for wav in sorted(glob.glob("outputs/*.wav")):
    s, detail = evaluate_file(wav)
    print(f"{'[sinh] ' + Path(wav).name:<28}{s:>7}")
    for k, v in detail.items():
        print(f"      {k:<22}{v}")