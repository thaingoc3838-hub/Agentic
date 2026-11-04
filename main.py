"""main.py - Điểm khởi chạy pipeline Multi-Agent xử lý và trình diễn thơ Việt."""
import sys
from pathlib import Path
from dotenv import load_dotenv

# Luôn load biến môi trường đầu tiên để bật LangSmith Tracing
load_dotenv()

from schemas import Job, Status
from workflow import run_pipeline


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Sử dụng: python main.py <đường_dẫn_ảnh> [speaker_id: A hoặc B] [--interactive]")
        print("Ví dụ  : python main.py data/samples/tho01.png A")
        print("Ví dụ  : python main.py data/samples/tho01.png A --interactive")
        sys.exit(1)

    img = sys.argv[1]
    spk = "A"
    interactive = False

    for arg in sys.argv[2:]:
        if arg in ("--interactive", "-i"):
            interactive = True
        elif arg in ("A", "B"):
            spk = arg

    print("=" * 60)
    print(" BẮT ĐẦU PIPELINE MULTI-AGENT (LANGGRAPH + LANGCHAIN)")
    print(f" Ảnh đầu vào      : {img}")
    print(f" Người ngâm       : {spk}")
    print(f" Human-in-the-Loop: {'BẬT (sẽ dừng duyệt bài thơ)' if interactive else 'TẮT (tự động 100%)'}")
    print("=" * 60)

    job = run_pipeline(img, spk, interactive=interactive)

    print("\n" + "=" * 60)
    print(" KẾT QUẢ THỰC THI PIPELINE")
    print("=" * 60)
    print(f" Trạng thái cuối: {job.status.value}")
    print(f" Thể thơ        : {job.poem_type.value}")
    print(f" Cảm xúc bài thơ: {job.emotion}")
    print(f" Tốc độ ngâm    : {job.speech_rate}x | Cao độ: {job.pitch_shift:+0.1f}st")
    print(f" Số dòng nghi ngờ: {len(job.flags)}")
    print(f" Số vòng lặp A4  : {job.retries}")
    print(f" Điểm phong cách : {job.style_score}")
    print(f" File audio sinh : {job.audio_path}")
    if job.drive_links:
        print(f" Google Drive    : {job.drive_links}")
    if job.errors:
        print(" Danh sách lỗi   :")
        for e in job.errors:
            print(f"   [!] {e}")
    print("=" * 60)
