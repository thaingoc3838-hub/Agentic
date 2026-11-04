"""workflow.py - Điều phối quy trình Multi-Agent bằng LangGraph.

Kiến trúc bao gồm:
- Node A1: Vision & OCR (LangChain Multimodal)
- Node A2: Verifier & Sửa lỗi thơ (LangChain Structured Output)
- [Human-in-the-Loop]: Điểm dừng can thiệp duyệt/chỉnh sửa thơ trước khi sang TTS
- Node A4_init: Khởi tạo tham số nhịp điệu & phân tích cảm xúc (Speech Rate & Pitch)
- Node A5: Tổng hợp giọng đọc TTS (VieNeu + Librosa Post-processing)
- Node A6: Đánh giá độ tương đồng phong cách
- Node A4_revise: Tự động phản biện & tinh chỉnh tham số (Agentic Loop)
- Node A7: Tải lên Google Drive
"""
import os
from datetime import datetime
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

# Load biến môi trường ngay từ đầu để LangSmith Tracing được kích hoạt
load_dotenv()

from langgraph.graph import StateGraph, START, END

from agents import a1_vision, a2_verifier, a4_planner, a5_run, a6_eval, a7_drive
from schemas import Job, Status

MAX_RETRIES = int(os.getenv("MAX_STYLE_RETRIES", "3"))


# ---------------- Các Nodes trong đồ thị ----------------
def node_a1_vision(job: Job) -> Job:
    print(f"\n[A1 Vision] Tiền xử lý ảnh & OCR chữ viết tay ({job.image_path})...", flush=True)
    job = a1_vision.run(job)
    job.save()
    return job


def node_a2_verifier(job: Job) -> Job:
    print(f"[A2 Verifier] Kiểm luật thơ ({job.poem_type.value}) & kiểm tra lỗi OCR...", flush=True)
    job = a2_verifier.run(job)
    job.save()
    return job


def node_human_review_cli(job: Job) -> Job:
    """Điểm dừng can thiệp duyệt thơ (Human-in-the-Loop) trên giao diện CLI."""
    if os.getenv("ENABLE_CLI_HUMAN_INTERRUPT", "0") == "1":
        print("\n" + "=" * 50)
        print(" [HUMAN-IN-THE-LOOP] DUYỆT VĂN BẢN TRƯỚC KHI NGÂM THƠ")
        print(f" Thể thơ nhận diện: {job.poem_type.value}")
        if job.flags:
            print(" Cảnh báo lỗi:", job.flags)
        print("-" * 50)
        print(job.verified_text)
        print("=" * 50)
        choice = input("Bạn có muốn chỉnh sửa lại bài thơ? (Nhấn Enter để đồng ý, hoặc gõ 'e' để sửa): ").strip().lower()
        if choice == 'e':
            print("Nhập toàn bộ bài thơ (kết thúc bằng dòng chữ 'END'):")
            lines = []
            while True:
                line = input()
                if line.strip() == "END":
                    break
                lines.append(line)
            job.verified_text = "\n".join(lines)
            print("[Human-in-the-Loop] Đã cập nhật văn bản bài thơ.")
        job.status = Status.VERIFIED
        job.save()
    return job


def node_a4_initial(job: Job) -> Job:
    print("[A4 Planner] Khởi tạo nhịp điệu & phân tích cảm xúc bài thơ...", flush=True)
    job = a4_planner.initial_plan(job)
    print(f"    -> Cảm xúc chủ đạo: {job.emotion} (Tốc độ: {job.speech_rate}x, Cao độ: {job.pitch_shift:+0.1f}st)", flush=True)
    job.save()
    return job


def node_a5_synth(job: Job) -> Job:
    round_info = f"(Vòng chỉnh sửa {job.retries})" if job.retries > 0 else ""
    print(f"[A5 Synthesis] Tổng hợp giọng đọc TTS {round_info}...", flush=True)
    job = a5_run.run(job)
    job.save()
    return job


def node_a6_eval(job: Job) -> Job:
    print("[A6 Evaluation] Đánh giá phong cách âm thanh...", flush=True)
    job = a6_eval.run(job)
    print(f"    -> Điểm phong cách (style_score): {job.style_score}", flush=True)
    for k in ("pause_short_ms_mean", "pause_long_ms_mean"):
        d = job.eval_detail.get(k, {})
        print(f"       + {k}: giá trị = {d.get('value')}ms | lệch target = {d.get('delta')}ms", flush=True)
    job.save()
    return job


def node_a4_revise(job: Job) -> Job:
    job.retries += 1
    print(f"[A4 Planner] Điều chỉnh lại tham số ngắt nghỉ (Lần thử {job.retries}/{MAX_RETRIES})...", flush=True)
    job = a4_planner.revise(job)
    job.save()
    return job


def node_a7_drive(job: Job) -> Job:
    if not Path("credentials.json").exists() and not Path("token.json").exists():
        print("[A7 Drive] Bỏ qua upload Drive (chưa cấu hình credentials.json / token.json).", flush=True)
        job.status = Status.DONE
        job.save()
        return job

    print("[A7 Drive] Đang tải audio và văn bản đã duyệt lên Google Drive...", flush=True)
    job = a7_drive.run(job)
    job.save()
    return job


# ---------------- Điều kiện rẽ nhánh (Conditional Edges) ----------------
def check_a1_status(job: Job) -> Literal["to_a2", "failed"]:
    return "failed" if job.status == Status.FAILED else "to_a2"


def check_a2_status(job: Job) -> Literal["to_human_or_a4", "failed"]:
    return "failed" if job.status == Status.FAILED else "to_human_or_a4"


def check_a5_status(job: Job) -> Literal["to_a6", "failed"]:
    return "failed" if job.status == Status.FAILED else "to_a6"


def route_after_evaluation(job: Job) -> Literal["converged", "retry_tune", "failed"]:
    if job.status == Status.FAILED:
        return "failed"

    if a4_planner.converged(job):
        print(f"[Agentic Loop] Âm thanh đã HỘI TỤ chuẩn phong cách sau {job.retries} lần điều chỉnh!", flush=True)
        return "converged"

    if job.retries >= MAX_RETRIES:
        print(f"[Agentic Loop] Đã đạt giới hạn lặp tối đa ({MAX_RETRIES} lần). Tiến hành kết xuất.", flush=True)
        return "converged"

    print("[Agentic Loop] Quãng nghỉ chưa đạt dung sai. Gửi phản hồi về A4 để tinh chỉnh tiếp...", flush=True)
    return "retry_tune"


# ---------------- Xây dựng Đồ thị LangGraph ----------------
def create_poetry_graph():
    graph = StateGraph(Job)

    # 1. Thêm các Node
    graph.add_node("a1_vision", node_a1_vision)
    graph.add_node("a2_verifier", node_a2_verifier)
    graph.add_node("human_review", node_human_review_cli)
    graph.add_node("a4_initial", node_a4_initial)
    graph.add_node("a5_synth", node_a5_synth)
    graph.add_node("a6_eval", node_a6_eval)
    graph.add_node("a4_revise", node_a4_revise)
    graph.add_node("a7_drive", node_a7_drive)

    # 2. Thêm các Cạnh
    graph.add_edge(START, "a1_vision")

    graph.add_conditional_edges(
        "a1_vision",
        check_a1_status,
        {"to_a2": "a2_verifier", "failed": END}
    )

    graph.add_conditional_edges(
        "a2_verifier",
        check_a2_status,
        {"to_human_or_a4": "human_review", "failed": END}
    )

    graph.add_edge("human_review", "a4_initial")
    graph.add_edge("a4_initial", "a5_synth")

    graph.add_conditional_edges(
        "a5_synth",
        check_a5_status,
        {"to_a6": "a6_eval", "failed": END}
    )

    graph.add_conditional_edges(
        "a6_eval",
        route_after_evaluation,
        {
            "converged": "a7_drive",
            "retry_tune": "a4_revise",
            "failed": END,
        }
    )

    graph.add_edge("a4_revise", "a5_synth")
    graph.add_edge("a7_drive", END)

    return graph.compile()


app_workflow = create_poetry_graph()


def run_pipeline(image_path: str, speaker: str = "A", interactive: bool = False) -> Job:
    """Chạy toàn bộ pipeline từ đầu đến cuối."""
    if interactive:
        os.environ["ENABLE_CLI_HUMAN_INTERRUPT"] = "1"
    else:
        os.environ["ENABLE_CLI_HUMAN_INTERRUPT"] = "0"

    job_id = f"{datetime.now():%Y%m%d_%H%M%S}_{Path(image_path).stem}"
    initial_job = Job(job_id=job_id, image_path=image_path, speaker_id=speaker)
    result_dict_or_job = app_workflow.invoke(initial_job)

    if isinstance(result_dict_or_job, Job):
        return result_dict_or_job
    return Job.model_validate(result_dict_or_job)


# ---------------- Hàm hỗ trợ Human-in-the-Loop cho Web UI ----------------
def step_until_human_review(image_path: str, speaker: str = "A") -> Job:
    """Chạy từ đầu đến hết A2 rồi dừng để người dùng duyệt trên Web UI."""
    job_id = f"{datetime.now():%Y%m%d_%H%M%S}_{Path(image_path).stem}"
    job = Job(job_id=job_id, image_path=image_path, speaker_id=speaker)
    job = a1_vision.run(job)
    if job.status == Status.FAILED:
        return job
    job = a2_verifier.run(job)
    job.status = Status.WAITING_HUMAN
    job.save()
    return job


def resume_pipeline_after_review(job: Job, edited_text: str = None,
                                 custom_speech_rate: float = None,
                                 custom_pitch_shift: float = None) -> Job:
    """Tiếp tục pipeline từ sau khi người dùng duyệt trên Web UI."""
    if edited_text:
        job.verified_text = edited_text
    job.status = Status.VERIFIED

    # Chạy A4 (Khởi tạo nhịp điệu & cảm xúc)
    job = a4_planner.initial_plan(job)
    if custom_speech_rate is not None:
        job.speech_rate = custom_speech_rate
    if custom_pitch_shift is not None:
        job.pitch_shift = custom_pitch_shift
    job.save()

    # Vòng lặp A5 - A6 - A4_revise
    while True:
        job = a5_run.run(job)
        job.save()
        if job.status == Status.FAILED:
            return job

        job = a6_eval.run(job)
        job.save()

        if a4_planner.converged(job) or job.retries >= MAX_RETRIES:
            break

        job.retries += 1
        job = a4_planner.revise(job)
        job.save()

    # A7 Drive
    if Path("credentials.json").exists() or Path("token.json").exists():
        job = a7_drive.run(job)
    else:
        job.status = Status.DONE
    job.save()
    return job
