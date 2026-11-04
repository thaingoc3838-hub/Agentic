"""a5_run.py - Cầu nối: gọi a5_synth.py bằng Python của venv_tts."""
import os
import subprocess
from pathlib import Path

from schemas import Job, Status

TTS_PYTHON = Path("venv_tts/Scripts/python.exe")
REF = {"A": "data/ref/ref_A.wav", "B": "data/ref/ref_B.wav"}

# Mặc định khi A4 chưa đặt tham số (chọn theo thí nghiệm ngày 04/11: A6 = 0,587)
DEFAULT_PAUSES = {
    "pause_line_ms": 400,      # giữa dòng 6 và dòng 8
    "pause_stanza_ms": 1800,   # giữa các khổ (dòng trống)
    "pause_clause_ms": 80,     # giữa các cụm trong một dòng (theo dấu phẩy)
    "pause_couplet_ms": 1200,  # cuối mỗi cặp lục bát
    "pause_half_ms": 200,      # giữa hai nửa 3-3 hoặc 4-4 trong một dòng
}


def _pause(job: Job, key: str) -> str:
    return str(job.plan_params.get(key, DEFAULT_PAUSES[key]))


def run(job: Job) -> Job:
    try:
        Path("outputs").mkdir(exist_ok=True)
        poem_file = Path("outputs") / f"{job.job_id}_poem.txt"
        poem_file.write_text(job.verified_text or "", encoding="utf-8")
        out = Path("outputs") / f"{job.job_id}.wav"

        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}   # tránh lỗi tiếng Việt khi in
        r = subprocess.run(
            [str(TTS_PYTHON), "agents/a5_synth.py", str(poem_file),
             REF[job.speaker_id], str(out),
             _pause(job, "pause_line_ms"),
             _pause(job, "pause_stanza_ms"),
             _pause(job, "pause_clause_ms"),
             _pause(job, "pause_couplet_ms"),
             _pause(job, "pause_half_ms")],
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