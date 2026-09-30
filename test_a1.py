import glob
from pathlib import Path

import jiwer

from agents import a1_vision
from schemas import Job


def norm(text: str) -> str:
    lines = [ln.strip() for ln in text.strip().splitlines()]
    return "\n".join(ln for ln in lines if ln)


images = sorted(glob.glob("data/samples/*.png") + glob.glob("data/samples/*.jpg"))
print(f"{'Ảnh':<10}{'CER gốc':>10}{'CER xử lý':>12}")

for img in images:
    stem = Path(img).stem
    ref = norm(Path(f"data/ground_truth/{stem}.txt").read_text(encoding="utf-8"))
    row = []
    for use_pre in (False, True):
        tag = "xu_ly" if use_pre else "goc"
        print(f"... đang chạy {stem} ({tag})", flush=True)
        job = a1_vision.run(Job(job_id=f"{stem}_{tag}", image_path=img),
                            use_preprocessed=use_pre)
        job.save("experiments")              # lưu cả khi lỗi để còn xem errors
        if job.raw_text is None:
            row.append("LỖI")
            print("   ", job.errors, flush=True)
            continue
        row.append(f"{jiwer.cer(ref, norm(job.raw_text)):.3f}")
    print(f"{stem:<10}{row[0]:>10}{row[1]:>12}", flush=True)