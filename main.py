import sys
from datetime import datetime
from pathlib import Path

from agents import a1_vision, a2_verifier, a5_run, a7_drive
from schemas import Job, Status

STEPS = [a1_vision.run, a2_verifier.run, a5_run.run, a7_drive.run]


def run_pipeline(image_path: str, speaker: str = "A") -> Job:
    job_id = f"{datetime.now():%Y%m%d_%H%M%S}_{Path(image_path).stem}"
    job = Job(job_id=job_id, image_path=image_path, speaker_id=speaker)
    for step in STEPS:
        print(f"-> {step.__module__}", flush=True)
        job = step(job)
        job.save()                       # lưu state sau mỗi bước
        if job.status == Status.FAILED:
            break
    return job


if __name__ == "__main__":
    img = sys.argv[1]
    spk = sys.argv[2] if len(sys.argv) > 2 else "A"
    job = run_pipeline(img, spk)
    print("Trạng thái:", job.status.value)
    print("Thể thơ:", job.poem_type.value, "| Cờ:", len(job.flags))
    print("Audio:", job.audio_path)
    for e in job.errors:
        print("LỖI:", e)