"""a4_planner.py - Tác nhân A4: quyết định cảm xúc và điều chỉnh tham số trình diễn."""
import os
import json
import hashlib
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

from agents.a6_eval import reference_stats
from schemas import Job, Status

load_dotenv()
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
CACHE_DIR = Path("cache/planner")
TOL_MS = 30          # sai lệch quãng nghỉ chấp nhận được


class EmotionAnalysis(BaseModel):
    emotion: str = Field(description="Sắc thái cảm xúc chính (ví dụ: 'Trầm lắng, u hoài', 'Hào sảng, hào hùng', 'Trữ tình, tha thiết', 'Thanh tịnh, an yên')")
    reasoning: str = Field(description="Giải thích ngắn gọn lý do phân tích từ tứ thơ, từ ngữ")
    speech_rate: float = Field(default=1.0, description="Hệ số tốc độ ngâm thơ: buồn/trầm thường 0.90 - 0.95; hào sảng 1.05; tha thiết 0.95; bình thường 1.0")
    pitch_shift: float = Field(default=0.0, description="Dịch cao độ semitones: trầm buồn thường -1.0 đến -0.5st; hào sảng +0.5st; bình thường 0.0st")


EMOTION_PROMPT = """Bạn là chuyên gia thẩm bình và ngâm thơ Việt Nam.
Hãy đọc bài thơ sau đây và xác định sắc thái cảm xúc chủ đạo để điều phối giọng ngâm thơ:
- Thơ u buồn, hoài niệm, chia ly: giọng trầm lắng, tốc độ chậm rãi (speech_rate: 0.90 - 0.95, pitch_shift: -1.0 đến -0.5).
- Thơ tự hào, hào hùng, khí thế: giọng hào sảng, tốc độ nhanh hơn chút (speech_rate: 1.02 - 1.05, pitch_shift: +0.5).
- Thơ phong cảnh, trữ tình lãng mạn: giọng tha thiết, êm dịu (speech_rate: 0.95 - 0.98, pitch_shift: -0.3).
- Thơ trào phúng, tự nhiên: giọng trung tính (speech_rate: 1.0, pitch_shift: 0.0).

Văn bản bài thơ:
{text}
"""


def analyze_emotion(text: str) -> EmotionAnalysis:
    """Phân tích cảm xúc bài thơ qua LLM (có cache)."""
    key = hashlib.sha256((text + MODEL).encode("utf-8")).hexdigest()[:24]
    cache_file = CACHE_DIR / f"emotion_{key}.json"
    if cache_file.exists():
        return EmotionAnalysis.model_validate_json(cache_file.read_text(encoding="utf-8"))

    try:
        llm = ChatGoogleGenerativeAI(
            model=MODEL,
            temperature=0.2,
            api_key=os.getenv("GEMINI_API_KEY"),
        )
        structured_llm = llm.with_structured_output(EmotionAnalysis)
        prompt_tmpl = ChatPromptTemplate.from_template(EMOTION_PROMPT)
        chain = prompt_tmpl | structured_llm
        result: EmotionAnalysis = chain.invoke({"text": text})
    except Exception as e:
        # Dự phòng khi lỗi mạng/quota: trả về phong cách trữ tình chuẩn
        result = EmotionAnalysis(
            emotion="Trữ tình, êm đềm",
            reasoning="Mặc định do dự phòng",
            speech_rate=0.96,
            pitch_shift=-0.5
        )

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return result


def initial_plan(job: Job) -> Job:
    """Khởi tạo tham số nhịp điệu + cảm xúc bài thơ."""
    st = reference_stats()
    job.plan_params = {
        "pause_line_ms": st["pause_short_ms_mean"]["target"],
        "pause_stanza_ms": st["pause_long_ms_mean"]["target"],
    }

    # Phân tích cảm xúc nếu chưa có
    if not job.emotion and job.verified_text:
        emo_res = analyze_emotion(job.verified_text)
        job.emotion = emo_res.emotion
        job.emotion_reasoning = emo_res.reasoning
        job.speech_rate = emo_res.speech_rate
        job.pitch_shift = emo_res.pitch_shift

    job.status = Status.PLANNED
    return job


def converged(job: Job) -> bool:
    """Dừng khi các quãng nghỉ đo được đã nằm trong dung sai."""
    for key in ("pause_short_ms_mean", "pause_long_ms_mean"):
        d = job.eval_detail.get(key, {})
        if d.get("delta") is not None and abs(d["delta"]) > TOL_MS:
            return False
    return True


BOUNDS = {"pause_line_ms": (150, 700), "pause_stanza_ms": (800, 3500)}


def revise(job: Job) -> Job:
    p = job.plan_params
    for key, pkey in (("pause_short_ms_mean", "pause_line_ms"),
                      ("pause_long_ms_mean", "pause_stanza_ms")):
        d = job.eval_detail.get(key, {})
        if d.get("delta") is not None:
            lo, hi = BOUNDS[pkey]
            p[pkey] = min(max(p[pkey] - 0.8 * d["delta"], lo), hi)
    return job
