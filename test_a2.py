import json
from pathlib import Path

import jiwer

from agents import a2_verifier
from schemas import Job


def norm(text: str) -> str:
    lines = [ln.strip() for ln in text.strip().splitlines()]
    return "\n".join(ln for ln in lines if ln)


print(f"{'Ảnh':<8}{'Thể thơ':<12}{'Cờ':>4}{'CER trước':>11}{'CER sau':>9}")
for stem in ["tho01", "tho02", "tho03"]:
    path = Path(f"experiments/{stem}_goc.json")   # kết quả OCR đã lưu từ test_a1
    job = Job.load(str(path))
    ref = norm(Path(f"data/ground_truth/{stem}.txt").read_text(encoding="utf-8"))

    before = jiwer.cer(ref, norm(job.raw_text))
    job = a2_verifier.run(job)
    after = jiwer.cer(ref, norm(job.verified_text))

    print(f"{stem:<8}{job.poem_type.value:<12}{len(job.flags):>4}{before:>11.3f}{after:>9.3f}")
    for f in job.flags:
        print("   cờ:", f)
    for e in job.errors:
        print("   lỗi:", e)
    job.save("experiments/a2")