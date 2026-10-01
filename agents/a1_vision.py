"""a1_vision.py - Tác nhân A1: tiền xử lý ảnh (M1) + đọc chữ viết tay (M2)."""
import json
import os
from pathlib import Path

import cv2
import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import types
import hashlib

from google.genai import errors as genai_errors
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential
from schemas import Job, Status

load_dotenv()
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

PROMPT = """Bạn là chuyên gia đọc chữ viết tay tiếng Việt. Ảnh là một bài thơ viết tay.
Hãy chép lại nội dung ảnh thành văn bản, tuân thủ nghiêm ngặt:
1. Giữ NGUYÊN cách xuống dòng như bản gốc, mỗi dòng thơ một dòng. Không gộp câu.
2. Giữa hai khổ thơ (nếu có) để một dòng trống.
3. Giữ đúng dấu thanh tiếng Việt. KHÔNG sửa lỗi chính tả, KHÔNG sáng tác, KHÔNG thêm bớt chữ.
4. Chữ nào không đọc chắc chắn thì viết đúng phần đọc được và đánh dấu [?] ngay sau chữ đó, không đoán bừa.
5. Nếu có tiêu đề, tách riêng ra trường "title"; nếu không có thì để chuỗi rỗng.

Chỉ trả về JSON đúng dạng:
{"title": "...", "text": "các dòng thơ, ngăn cách bằng \\n", "uncertain_words": ["..."]}
"""


# ---------------- M1: tiền xử lý ảnh ----------------
def _read(path: str) -> np.ndarray:
    """Đọc ảnh an toàn với đường dẫn có dấu/khoảng trắng trên Windows."""
    data = np.fromfile(path, dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Không đọc được ảnh: {path}")
    return img


def _write(path: str, img: np.ndarray) -> None:
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise ValueError("Không ghi được ảnh")
    buf.tofile(path)


def _estimate_skew(gray: np.ndarray) -> float:
    """Ước lượng góc nghiêng (độ) bằng cách tìm góc làm các dòng chữ 'thẳng' nhất."""
    small = cv2.resize(gray, None, fx=0.25, fy=0.25) if max(gray.shape) > 1500 else gray
    inv = cv2.threshold(small, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    h, w = inv.shape
    best_angle, best_score = 0.0, -1.0
    for angle in np.arange(-8, 8.5, 0.5):
        m = cv2.getRotationMatrix2D((w / 2, h / 2), float(angle), 1.0)
        rotated = cv2.warpAffine(inv, m, (w, h))
        score = float(np.var(rotated.sum(axis=1)))
        if score > best_score:
            best_angle, best_score = float(angle), score
    return best_angle


def preprocess(image_path: str, out_dir: str = "outputs") -> str:
    """Xám -> xoay thẳng -> giảm nhiễu -> tăng tương phản (CLAHE) -> cắt lề."""
    img = _read(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 1) Xoay thẳng (chỉ xoay khi nghiêng đáng kể)
    angle = _estimate_skew(gray)
    if abs(angle) >= 1.0:
        h, w = gray.shape
        m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        gray = cv2.warpAffine(gray, m, (w, h), flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_REPLICATE)

    # 2) Giảm nhiễu nhẹ
    gray = cv2.fastNlMeansDenoising(gray, None, h=8)

    # 3) Tăng tương phản cục bộ (không nhị phân hóa để giữ nét mảnh và dấu thanh)
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)

    # 4) Cắt lề dựa trên vùng có chữ
    inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    inv = cv2.morphologyEx(inv, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    ys, xs = np.where(inv > 0)
    if len(xs) > 500:
        pad = 30
        h, w = gray.shape
        x0, x1 = max(xs.min() - pad, 0), min(xs.max() + pad, w)
        y0, y1 = max(ys.min() - pad, 0), min(ys.max() + pad, h)
        gray = gray[y0:y1, x0:x1]

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    out_path = str(Path(out_dir) / f"{Path(image_path).stem}_clean.png")
    _write(out_path, gray)
    return out_path


# ---------------- M2: OCR bằng Gemini (có cache, không retry 429) ----------------
CACHE_DIR = Path("cache/ocr")


class QuotaExceeded(Exception):
    """Hết hạn mức API: thử lại cũng vô ích, dừng ngay để khỏi tốn thêm lượt."""


def _is_transient(exc: BaseException) -> bool:
    """Chỉ thử lại lỗi tạm thời (server quá tải, mạng). KHÔNG thử lại 429."""
    if isinstance(exc, QuotaExceeded):
        return False
    if isinstance(exc, genai_errors.APIError):
        return exc.code in (500, 502, 503, 504)
    return isinstance(exc, (ConnectionError, TimeoutError))


def _cache_path(image_bytes: bytes) -> Path:
    # Khóa cache gồm: nội dung ảnh + tên model + prompt.
    # Đổi ảnh, model hoặc prompt thì tự gọi lại API.
    key = hashlib.sha256(image_bytes + MODEL.encode() + PROMPT.encode()).hexdigest()[:24]
    return CACHE_DIR / f"{key}.json"


@retry(retry=retry_if_exception(_is_transient), stop=stop_after_attempt(3),
       wait=wait_exponential(min=2, max=20), reraise=True)
def _call_gemini(image_path: str, image_bytes: bytes) -> dict:
    client = genai.Client(
        api_key=os.getenv("GEMINI_API_KEY"),
        # Tắt retry ngầm của thư viện, vì nó cũng đốt thêm lượt hạn mức
        http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1)),
    )
    mime = "image/png" if image_path.lower().endswith(".png") else "image/jpeg"
    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=[types.Part.from_bytes(data=image_bytes, mime_type=mime), PROMPT],
            config=types.GenerateContentConfig(
                response_mime_type="application/json", temperature=0
            ),
        )
    except genai_errors.APIError as e:
        if e.code == 429:
            raise QuotaExceeded(
                "Hết hạn mức Gemini (429). Đổi GEMINI_MODEL hoặc chờ sang ngày mới."
            ) from e
        raise
    return json.loads(resp.text)


def ocr(image_path: str, use_cache: bool = True) -> dict:
    image_bytes = Path(image_path).read_bytes()
    cache_file = _cache_path(image_bytes)

    if use_cache and cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))   # 0 lượt API

    result = _call_gemini(image_path, image_bytes)                   # 1 lượt API
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                          encoding="utf-8")
    return result

# ---------------- Hàm chạy trong pipeline ----------------
def run(job: Job, use_preprocessed: bool = True) -> Job:
    """Nhận Job, điền preprocessed_path + kết quả OCR, trả Job."""
    try:
        source = job.image_path
        if use_preprocessed:
            job.preprocessed_path = preprocess(job.image_path)
            job.status = Status.PREPROCESSED
            source = job.preprocessed_path

        result = ocr(source)
        job.title = result.get("title", "") or None
        job.raw_text = result.get("text", "")
        job.uncertain_words = result.get("uncertain_words", [])

        words = max(len(job.raw_text.split()), 1)
        job.ocr_confidence = round(1 - len(job.uncertain_words) / words, 3)
        job.status = Status.OCR_DONE
    except Exception as e:  # Orchestrator sẽ quyết định retry hay dừng
        job.errors.append(f"A1: {type(e).__name__}: {e}")
        job.status = Status.FAILED
    return job