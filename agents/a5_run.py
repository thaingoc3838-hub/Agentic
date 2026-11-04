"""a5_run.py - Cầu nối: gọi a5_synth.py bằng Python của venv_tts và áp dụng điều chỉnh cảm xúc & clone giọng tùy ý."""
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


def _resolve_ref_audio(job: Job) -> str:
    """Xác định file âm thanh mẫu: hỗ trợ Zero-shot Voice Cloning từ file tải lên hoặc ghi âm."""
    if job.custom_ref_audio and Path(job.custom_ref_audio).exists():
        custom_path = Path(job.custom_ref_audio)
        # Chuẩn hóa về file .wav 48kHz nếu là định dạng khác (mp3, ogg, m4a)
        if not custom_path.suffix.lower() == ".wav":
            import librosa
            import soundfile as sf
            wav_path = Path("outputs") / f"{job.job_id}_custom_ref.wav"
            y, sr = librosa.load(str(custom_path), sr=48000)
            sf.write(str(wav_path), y, sr)
            return str(wav_path)
        return str(custom_path)
    return REF.get(job.speaker_id, REF["A"])


def run(job: Job) -> Job:
    try:
        Path("outputs").mkdir(exist_ok=True)
        poem_file = Path("outputs") / f"{job.job_id}_poem.txt"
        poem_file.write_text(job.verified_text or "", encoding="utf-8")
        out = Path("outputs") / f"{job.job_id}.wav"

        ref_audio = _resolve_ref_audio(job)
        print(f"[A5 Synthesis] Sử dụng mẫu giọng: {ref_audio}", flush=True)

        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}   # tránh lỗi tiếng Việt khi in
        r = subprocess.run(
            [str(TTS_PYTHON), "agents/a5_synth.py", str(poem_file),
             ref_audio, str(out),
             _pause(job, "pause_line_ms"),
             _pause(job, "pause_stanza_ms"),
             _pause(job, "pause_clause_ms"),
             _pause(job, "pause_couplet_ms"),
             _pause(job, "pause_half_ms")],
            capture_output=True, text=True, encoding="utf-8", env=env,
        )
        if r.returncode != 0:
            raise RuntimeError(r.stderr[-500:])

        # Áp dụng hậu xử lý âm học theo sắc thái cảm xúc từ A4 (Pitch Shift & Speech Rate)
        if (job.pitch_shift != 0.0 or job.speech_rate != 1.0) and out.exists():
            try:
                import librosa
                import soundfile as sf
                y, sr = librosa.load(str(out), sr=None)
                if job.pitch_shift != 0.0:
                    y = librosa.effects.pitch_shift(y, sr=sr, n_steps=job.pitch_shift)
                if job.speech_rate != 1.0 and 0.5 <= job.speech_rate <= 2.0:
                    y = librosa.effects.time_stretch(y, rate=job.speech_rate)
                sf.write(str(out), y, sr)
            except Exception as pe:
                print(f"[A5 Warning] Lỗi điều chỉnh cao độ/tốc độ: {pe}", flush=True)

        job.audio_path = str(out)
        job.status = Status.SYNTHESIZED
    except Exception as e:
        job.errors.append(f"A5: {type(e).__name__}: {e}")
        job.status = Status.FAILED
    return job
