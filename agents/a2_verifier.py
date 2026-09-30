"""a2_verifier.py - Tác nhân A2: kiểm lỗi, nhận diện thể thơ (M3)."""
import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from schemas import Job, PoemType, Status

load_dotenv()
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
CACHE_DIR = Path("cache/verify")


# ---------------- Lớp 1: luật bằng code ----------------
def split_stanzas(text: str) -> list[list[str]]:
    """Tách văn bản thành các khổ (ngăn cách bằng dòng trống)."""
    stanzas, cur = [], []
    for ln in text.splitlines():
        ln = ln.strip()
        if ln:
            cur.append(ln)
        elif cur:
            stanzas.append(cur)
            cur = []
    if cur:
        stanzas.append(cur)
    return stanzas


def count_syllables(line: str) -> int:
    """Tiếng Việt: mỗi tiếng cách nhau bằng dấu cách. Bỏ dấu câu và ký hiệu [?]."""
    clean = line.replace("[?]", " ")
    clean = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in clean)
    return len(clean.split())


def detect_poem_type(lines: list[str]) -> PoemType:
    counts = [count_syllables(ln) for ln in lines]
    if not counts:
        return PoemType.UNKNOWN
    n = len(counts)
    # Lục bát: các dòng xen kẽ 6 - 8
    if n >= 2 and all(c == (6 if i % 2 == 0 else 8) for i, c in enumerate(counts)):
        return PoemType.LUC_BAT
    # Thất ngôn: mọi dòng 7 tiếng (tứ tuyệt 4 dòng, bát cú 8 dòng)
    if all(c == 7 for c in counts) and n in (4, 8):
        return PoemType.THAT_NGON
    # Gần đúng: đa số dòng khớp thì vẫn nhận, dòng lệch sẽ bị gắn cờ
    if sum(c == 7 for c in counts) / n >= 0.75:
        return PoemType.THAT_NGON
    if n >= 2 and sum(c == (6 if i % 2 == 0 else 8) for i, c in enumerate(counts)) / n >= 0.75:
        return PoemType.LUC_BAT
    return PoemType.TU_DO


def flag_lines(lines: list[str], poem_type: PoemType) -> list[str]:
    """Gắn cờ dòng nghi OCR sai: lệch số tiếng hoặc còn dấu [?]."""
    flags = []
    for i, ln in enumerate(lines):
        c = count_syllables(ln)
        if "[?]" in ln:
            flags.append(f"Dòng {i+1}: có chữ chưa chắc chắn: {ln}")
        if poem_type == PoemType.THAT_NGON and c != 7:
            flags.append(f"Dòng {i+1}: {c} tiếng (thất ngôn cần 7): {ln}")
        if poem_type == PoemType.LUC_BAT:
            want = 6 if i % 2 == 0 else 8
            if c != want:
                flags.append(f"Dòng {i+1}: {c} tiếng (cần {want}): {ln}")
    return flags


# ---------------- Lớp 2: LLM sửa có kiểm soát ----------------
PROMPT = """Bạn là biên tập viên thơ Việt. Dưới đây là văn bản OCR từ bài thơ viết tay,
kèm danh sách dòng nghi ngờ. Nhiệm vụ: chỉ sửa các dòng nghi ngờ, và CHỈ khi chắc chắn
đó là lỗi nhận dạng (chữ bị đọc nhầm, thiếu dấu, dòng lệch số tiếng do đọc sót chữ).
Quy tắc:
1. KHÔNG sáng tác, KHÔNG viết lại cho hay hơn, KHÔNG đụng tới dòng không bị nghi ngờ.
2. Giữ nguyên số dòng, thứ tự dòng và các dòng trống giữa khổ.
3. Nếu không chắc, giữ nguyên dòng đó.
4. Với mỗi dòng đã sửa, ghi lại bản gốc và bản sửa.

Thể thơ dự đoán: {poem_type}

Văn bản OCR:
{text}

Dòng nghi ngờ:
{flags}

Chỉ trả về JSON:
{{"text": "văn bản sau khi sửa", "changes": [{{"before": "...", "after": "..."}}]}}
"""


class QuotaExceeded(Exception):
    pass


def _call_llm(text: str, flags: list[str], poem_type: PoemType) -> dict:
    prompt = PROMPT.format(poem_type=poem_type.value, text=text, flags="\n".join(flags))
    key = hashlib.sha256((prompt + MODEL).encode()).hexdigest()[:24]
    cache_file = CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))   # 0 lượt API

    client = genai.Client(
        api_key=os.getenv("GEMINI_API_KEY"),
        http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1)),
    )
    try:
        resp = client.models.generate_content(
            model=MODEL, contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json", temperature=0),
        )
    except genai_errors.APIError as e:
        if e.code == 429:
            raise QuotaExceeded("Hết hạn mức Gemini (429).") from e
        raise
    result = json.loads(resp.text)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


# ---------------- Hàm chạy trong pipeline ----------------
def run(job: Job, use_llm: bool = True) -> Job:
    try:
        text = job.raw_text or ""
        stanzas = split_stanzas(text)
        lines = [ln for st in stanzas for ln in st]

        job.poem_type = detect_poem_type(lines)
        job.flags = flag_lines(lines, job.poem_type)

        verified = text
        if use_llm and job.flags:               # không có dòng nghi ngờ thì khỏi gọi API
            result = _call_llm(text, job.flags, job.poem_type)
            verified = result.get("text", text)
            # Kiểm tra an toàn: số dòng phải giữ nguyên, nếu không thì bỏ kết quả LLM
            if len([l for l in verified.splitlines() if l.strip()]) != len(lines):
                job.errors.append("A2: LLM làm đổi số dòng, giữ nguyên bản OCR")
                verified = text

        job.verified_text = verified
        job.status = Status.VERIFIED
    except Exception as e:
        job.errors.append(f"A2: {type(e).__name__}: {e}")
        job.status = Status.FAILED
    return job