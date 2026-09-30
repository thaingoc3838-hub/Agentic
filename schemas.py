"""schemas.py - Cấu trúc dữ liệu trao đổi giữa các tác nhân trong pipeline."""
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class Status(str, Enum):
    """Trạng thái của job, đi theo thứ tự các bước."""
    NEW = "NEW"
    PREPROCESSED = "PREPROCESSED"    # A1 xong tiền xử lý ảnh
    OCR_DONE = "OCR_DONE"            # A1 xong đọc chữ
    VERIFIED = "VERIFIED"            # A2 xong kiểm lỗi
    PLANNED = "PLANNED"              # A4 xong kịch bản trình diễn
    SYNTHESIZED = "SYNTHESIZED"      # A5 xong sinh audio
    EVALUATED = "EVALUATED"          # A6 xong chấm style
    DONE = "DONE"                    # A7 xong upload Drive
    FAILED = "FAILED"


class PoemType(str, Enum):
    LUC_BAT = "luc_bat"
    THAT_NGON = "that_ngon"
    TU_DO = "tu_do"
    UNKNOWN = "unknown"


# ---------- Đường style (A3) ----------
class Stat(BaseModel):
    mean: float
    std: float = 0.0


class StyleProfile(BaseModel):
    """Phong cách rút ra từ các file mp3 mẫu, lưu vào profiles/style_profile.json."""
    speaker_id: str = "A" 
    source_files: list[str] = Field(default_factory=list)
    speech_rate_syll_per_sec: Optional[Stat] = None
    pitch_hz: Optional[Stat] = None
    pause_line_ms: Optional[Stat] = None
    pause_stanza_ms: Optional[Stat] = None
    energy_db: Optional[Stat] = None
    description_vi: str = ""          # mô tả bằng lời (từ Gemini nghe audio)


# ---------- Kịch bản trình diễn (A4) ----------
class PerformanceLine(BaseModel):
    text: str
    rate: str = "-15%"                # tốc độ so với mặc định
    pitch: str = "-2st"               # cao độ so với mặc định
    pause_after_ms: int = 500
    emphasis: list[str] = Field(default_factory=list)


class PerformancePlan(BaseModel):
    lines: list[PerformanceLine] = Field(default_factory=list)


# ---------- Job: dữ liệu chạy xuyên suốt pipeline ----------
class Job(BaseModel):
    job_id: str
    created_at: datetime = Field(default_factory=datetime.now)
    status: Status = Status.NEW

    # A1: ảnh
    image_path: str
    speaker_id: str = "A" 
    preprocessed_path: Optional[str] = None

    # A1: OCR
    raw_text: Optional[str] = None
    title: Optional[str] = None
    uncertain_words: list[str] = Field(default_factory=list)
    ocr_confidence: Optional[float] = None

    # A2: kiểm lỗi
    verified_text: Optional[str] = None
    poem_type: PoemType = PoemType.UNKNOWN
    flags: list[str] = Field(default_factory=list)   # các dòng nghi OCR sai

    # A4: kịch bản
    plan: Optional[PerformancePlan] = None

    # A5: audio
    audio_path: Optional[str] = None

    # A6: đánh giá
    style_score: Optional[float] = None
    eval_rounds: int = 0

    # A7: Drive
    drive_links: dict[str, str] = Field(default_factory=dict)

    # Theo dõi lỗi
    errors: list[str] = Field(default_factory=list)
    retries: int = 0

    def save(self, folder: str = "outputs") -> Path:
        """Ghi state ra file JSON để chạy lại từ bước lỗi."""
        path = Path(folder) / f"{self.job_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: str) -> "Job":
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))