"""a5_run.py - Cầu nối: gọi a5_synth.py bằng Python của venv_tts."""
import os
import subprocess
from pathlib import Path

from schemas import Job, Status

TTS_PYTHON = Path("venv_tts/Scripts/python.exe")
REF = {"A": "data/ref/ref_A.wav", "B": "data/ref/ref_B.wav"}


def run(job: Job) -> Job:
    try:
        Path("outputs").mkdir(exist_ok=True)
        poem_file = Path("outputs") / f"{job.job_id}_poem.txt"
        poem_file.write_text(job.verified_text or "", encoding="utf-8")
        out = Path("outputs") / f"{job.job_id}.wav"

        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}   # tránh lỗi tiếng Việt khi in
        r = subprocess.run(
            [str(TTS_PYTHON), "agents/a5_synth.py", str(poem_file),
             REF[job.speaker_id], str(out)],
            capture_output=True, text=True, encoding="utf-8", env=env,
        )
        if r.returncode != 0:
            raise RuntimeError(r.stderr[-500:])
        job.audio_path = str(out)
        job.status = Status.SYNTHESIZED
    except Exception as e:
        job.errors.append(f"A5: {type(e).__name__}: {e}")
        job.status = Status.FAILED
    return job