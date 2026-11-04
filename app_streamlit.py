"""app_streamlit.py - Giao diện Web tương tác toàn diện cho Hệ thống Multi-Agent Trình diễn Thơ Việt Nam.
Chạy ứng dụng:
    streamlit run app_streamlit.py
"""
import glob
import os
from pathlib import Path

from dotenv import load_dotenv
import pandas as pd
import streamlit as st
from PIL import Image

load_dotenv()

from schemas import Job, Status, PoemType
from workflow import step_until_human_review, resume_pipeline_after_review, run_pipeline
from agents import a4_planner

# Thiết lập trang Streamlit
st.set_page_config(
    page_title="NCKH Agentic - Trình diễn Thơ Việt Nam",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .stMetric {
        background: #F8FAFC;
        padding: 12px;
        border-radius: 8px;
        border: 1px solid #E2E8F0;
    }
    .badge-emotion {
        background-color: #EEF2FF;
        color: #4338CA;
        padding: 5px 12px;
        border-radius: 14px;
        font-weight: 600;
        font-size: 0.95rem;
        border: 1px solid #C7D2FE;
        display: inline-block;
    }
    .step-header {
        color: #1E40AF;
        font-weight: 700;
        border-bottom: 2px solid #DBEAFE;
        padding-bottom: 6px;
        margin-top: 15px;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# ---------------- SIDEBAR ----------------
st.sidebar.image("https://img.icons8.com/isometric/100/scroll.png", width=70)
st.sidebar.title("Cấu hình Pipeline")

speaker = st.sidebar.radio("Chọn giọng ngâm thơ mẫu:", ["A (Nữ - Truyền cảm)", "B (Nam - Trầm ấm)"], index=0)
speaker_id = "A" if "A" in speaker else "B"

st.sidebar.markdown("---")
st.sidebar.subheader("Giám sát & Thực nghiệm")
project_name = os.getenv("LANGCHAIN_PROJECT", "NCKH-Agentic-Poetry")
has_langsmith = bool(os.getenv("LANGCHAIN_API_KEY"))

if has_langsmith:
    st.sidebar.success(f"LangSmith Tracing: Đang BẬT\nProject: **{project_name}**")
    st.sidebar.markdown("[👉 Mở LangSmith Dashboard](https://smith.langchain.com)")
else:
    st.sidebar.warning("LangSmith Tracing: Chưa cấu hình API Key trong .env")

st.sidebar.markdown("---")
sample_images = sorted(glob.glob("data/samples/*.*"))
selected_sample = st.sidebar.selectbox(
    "Chọn ảnh mẫu có sẵn:",
    ["-- Tải ảnh mới từ máy --"] + [Path(p).name for p in sample_images]
)

# ---------------- HEADER ----------------
st.markdown('<div class="main-title">📜 Hệ thống Multi-Agent Tự động Hóa Trình diễn Thơ Việt</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Kiến trúc <b>LangGraph Closed-Loop</b> • <b>LangChain Multimodal OCR</b> • <b>Human-in-the-Loop</b> • <b>Audio Style Reflection</b></div>', unsafe_allow_html=True)

# Quản lý State của Session
if "current_job" not in st.session_state:
    st.session_state.current_job = None
if "image_path" not in st.session_state:
    st.session_state.image_path = None

tab1, tab2 = st.tabs(["🎯 Thao tác Pipeline & Trình diễn", "📊 Lịch sử Thực nghiệm & Chỉ số"])

# Từ điển tên chỉ số âm học thân thiện
METRIC_NAMES = {
    "pause_short_ms_mean": "Quãng nghỉ giữa câu/dòng (ms)",
    "pause_long_ms_mean": "Quãng nghỉ giữa các khổ (ms)",
    "pitch_hz_std": "Độ biến thiên cao độ (Hz)",
    "speech_ratio": "Tỉ lệ phát âm/im lặng",
    "energy_db_mean": "Mức năng lượng âm thanh (dB)"
}

with tab1:
    col_input, col_process = st.columns([1, 1.35], gap="large")

    with col_input:
        st.markdown('<h3 class="step-header">1. Ảnh thơ viết tay đầu vào</h3>', unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Tải ảnh bài thơ lên:", type=["png", "jpg", "jpeg"])

        image_to_process = None
        if uploaded_file is not None:
            temp_dir = Path("outputs/web_uploads")
            temp_dir.mkdir(parents=True, exist_ok=True)
            saved_path = temp_dir / uploaded_file.name
            with open(saved_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            image_to_process = str(saved_path)
            st.image(uploaded_file, caption="Ảnh gốc tải lên", use_container_width=True)
        elif selected_sample != "-- Tải ảnh mới từ máy --":
            image_to_process = f"data/samples/{selected_sample}"
            st.image(image_to_process, caption=f"Ảnh mẫu: {selected_sample}", use_container_width=True)

        if image_to_process:
            st.session_state.image_path = image_to_process

        # Hiển thị ảnh sau khi tiền xử lý (OpenCV M1) nếu đã chạy
        job: Job = st.session_state.current_job
        if job and job.preprocessed_path and Path(job.preprocessed_path).exists():
            st.markdown("---")
            st.markdown("#### 🔍 Ảnh sau Tiền xử lý (OpenCV M1)")
            st.image(job.preprocessed_path, caption="Đã xoay thẳng, tăng tương phản CLAHE, cắt lề", use_container_width=True)

    with col_process:
        st.markdown('<h3 class="step-header">2. Điều phối Tiến trình Multi-Agent</h3>', unsafe_allow_html=True)

        if not st.session_state.image_path:
            st.info("👈 Hãy chọn một ảnh mẫu hoặc tải ảnh bài thơ từ máy ở cột bên trái để bắt đầu.")
        else:
            # NÚT BƯỚC 1: A1 + A2
            btn_step1 = st.button("🚀 BƯỚC 1: Nhận diện ảnh & Kiểm luật thơ (A1 + A2)", type="primary", use_container_width=True)

            if btn_step1:
                with st.spinner("Đang chạy Tác nhân A1 (Preprocess + OCR) và A2 (Kiểm luật thơ)..."):
                    job = step_until_human_review(st.session_state.image_path, speaker=speaker_id)
                    st.session_state.current_job = job

            job: Job = st.session_state.current_job

            # NẾU ĐÃ CHẠY XONG BƯỚC 1 HOẶC ĐANG CHỜ DUYỆT (HUMAN-IN-THE-LOOP)
            if job is not None and job.status != Status.FAILED:
                st.markdown("---")
                st.markdown("### ✍️ Human-in-the-Loop (Duyệt & Kiểm soát thơ)")

                col_meta1, col_meta2, col_meta3 = st.columns(3)
                with col_meta1:
                    st.metric("Thể thơ phát hiện", job.poem_type.value)
                with col_meta2:
                    st.metric("Độ tin cậy OCR", f"{job.ocr_confidence * 100:.1f}%" if job.ocr_confidence else "N/A")
                with col_meta3:
                    st.metric("Cảnh báo nghi ngờ", f"{len(job.flags)} dòng")

                if job.flags:
                    with st.expander("⚠️ Chi tiết các dòng nghi ngờ từ A2:", expanded=True):
                        for f in job.flags:
                            st.write(f"- {f}")

                # So sánh OCR thô và văn bản đã sửa
                with st.expander("📝 So sánh bản OCR gốc vs Bản A2 đã sửa:", expanded=False):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.caption("Bản OCR gốc từ ảnh (A1):")
                        st.code(job.raw_text or "", language="text")
                    with c2:
                        st.caption("Bản A2 đã kiểm tra luật thơ:")
                        st.code(job.verified_text or "", language="text")

                # Ô CHO PHÉP NGƯỜI DÙNG DUYỆT VÀ SỬA TRỰC TIẾP
                edited_poem = st.text_area(
                    "Văn bản thơ sau kiểm duyệt (Bạn có thể trực tiếp chỉnh sửa câu từ dưới đây trước khi ngâm):",
                    value=job.verified_text or job.raw_text or "",
                    height=180
                )

                st.markdown("#### 🎭 Sắc thái cảm xúc & Nhịp điệu (Tác nhân A4)")
                # Phân tích sơ bộ cảm xúc
                with st.spinner("Đang nhận diện sắc thái cảm xúc..."):
                    if not job.emotion and edited_poem:
                        emo_analysis = a4_planner.analyze_emotion(edited_poem)
                        job.emotion = emo_analysis.emotion
                        job.emotion_reasoning = emo_analysis.reasoning
                        job.speech_rate = emo_analysis.speech_rate
                        job.pitch_shift = emo_analysis.pitch_shift

                st.markdown(f"Cảm xúc bài thơ nhận diện: <span class='badge-emotion'>{job.emotion}</span>", unsafe_allow_html=True)
                if job.emotion_reasoning:
                    st.caption(f"Lý giải: {job.emotion_reasoning}")

                col_ctl1, col_ctl2 = st.columns(2)
                with col_ctl1:
                    custom_rate = st.slider("Tốc độ ngâm thơ (Speed Rate):", 0.85, 1.15, float(job.speech_rate or 1.0), 0.01)
                with col_ctl2:
                    custom_pitch = st.slider("Cao độ giọng ngâm (Pitch Shift):", -2.0, 2.0, float(job.pitch_shift or 0.0), 0.1)

                # NÚT BƯỚC 2: A4 -> A5 -> A6 -> A7
                st.markdown("---")
                btn_step2 = st.button("🎵 BƯỚC 2: Xác nhận & Sinh âm thanh ngâm thơ (A4 $\\rightarrow$ A5 $\\rightarrow$ A6)", type="primary", use_container_width=True)

                if btn_step2:
                    with st.spinner("Đang tổng hợp giọng ngâm thơ và lặp tự phản biện nhịp điệu..."):
                        final_job = resume_pipeline_after_review(
                            job,
                            edited_text=edited_poem,
                            custom_speech_rate=custom_rate,
                            custom_pitch_shift=custom_pitch
                        )
                        st.session_state.current_job = final_job
                        st.success("Đã hoàn thành toàn bộ quy trình ngâm thơ!")
                        st.rerun()

            elif job is not None and job.status == Status.FAILED:
                st.error("Đã xảy ra lỗi trong quá trình thực thi:")
                for err in job.errors:
                    st.write(f"- {err}")

            # HIỂN THỊ KẾT QUẢ ÂM THANH KHI ĐÃ XONG
            if job is not None and job.audio_path and Path(job.audio_path).exists():
                st.markdown("---")
                st.markdown("### 🎧 Kết quả Âm thanh Ngâm thơ Hoàn thiện")
                st.audio(job.audio_path, format="audio/wav")

                col_dl1, col_dl2 = st.columns([1, 1])
                with col_dl1:
                    with open(job.audio_path, "rb") as f_audio:
                        st.download_button(
                            label="⬇️ Tải file Audio (.wav) về máy",
                            data=f_audio,
                            file_name=Path(job.audio_path).name,
                            mime="audio/wav",
                            use_container_width=True
                        )
                with col_dl2:
                    if job.drive_links:
                        st.success(f"Đã sao lưu lên Google Drive: [Mở thư mục]({job.drive_links.get('audio', '#')})")

                res_col1, res_col2 = st.columns(2)
                with res_col1:
                    st.metric("Điểm tương đồng phong cách (A6)", f"{job.style_score:.3f}" if job.style_score else "N/A")
                with res_col2:
                    st.metric("Số vòng lặp tinh chỉnh nhịp (A4)", f"{job.retries} lần")

                # BẢNG THỐNG KÊ ÂM HỌC A6 TRỰC QUAN
                if job.eval_detail:
                    st.markdown("#### 📊 Bảng phân tích đặc trưng âm học so với giọng mẫu:")
                    rows = []
                    for k, v in job.eval_detail.items():
                        rows.append({
                            "Chỉ số âm học": METRIC_NAMES.get(k, k),
                            "Giá trị đo được": f"{v.get('value'):.1f}" if isinstance(v.get('value'), (int, float)) else "N/A",
                            "Giá trị mẫu (Target)": f"{v.get('target'):.1f}" if isinstance(v.get('target'), (int, float)) else "N/A",
                            "Sai lệch (Delta)": f"{v.get('delta'):+0.1f}" if isinstance(v.get('delta'), (int, float)) else "N/A",
                            "Điểm thành phần (0-1)": f"{v.get('score'):.3f}" if isinstance(v.get('score'), (int, float)) else "N/A",
                        })
                    df_eval = pd.DataFrame(rows)
                    st.dataframe(df_eval, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("Lịch sử các phiên chạy gần đây (outputs/)")
    output_files = sorted(glob.glob("outputs/*.wav"), reverse=True)
    if output_files:
        for audio_file in output_files[:10]:
            name = Path(audio_file).name
            stem = Path(audio_file).stem
            json_file = Path(f"outputs/{stem}.json")
            with st.container():
                c_head1, c_head2 = st.columns([2, 1])
                with c_head1:
                    st.markdown(f"**Bài thơ: `{name}`**")
                st.audio(audio_file)
                if json_file.exists():
                    try:
                        job_data = Job.load(str(json_file))
                        st.caption(f"Thể thơ: **{job_data.poem_type.value}** | Điểm phong cách: **{job_data.style_score}** | Sắc thái: **{job_data.emotion}** | Lần lặp A4: **{job_data.retries}**")
                    except Exception:
                        pass
                st.markdown("---")
    else:
        st.info("Chưa có file âm thanh nào trong outputs/.")
