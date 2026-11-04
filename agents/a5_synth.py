"""a5_synth.py - Đọc thơ từng cụm bằng giọng clone, chèn quãng nghỉ theo cụm/dòng/cặp/khổ.
Dòng lục (6 tiếng) đọc nhịp 3-3, dòng bát (8 tiếng) đọc nhịp 4-4.
Chạy trong venv_tts:
  python agents/a5_synth.py <file_thơ.txt> <ref.wav> <out.wav>
      [pause_line_ms] [pause_stanza_ms] [pause_clause_ms] [pause_couplet_ms] [pause_half_ms] [even_rhythm 1/0]
"""
import re
import sys

import numpy as np
import soundfile as sf
from vieneu import Vieneu

SR = 48000


def clean_line(line: str) -> str:
    """Bỏ số thứ tự dòng như (15), (20)."""
    return re.sub(r"\s*\(\s*\d+\s*\)", "", line).strip()


def split_clauses(line: str) -> list[str]:
    """Tách dòng theo dấu phẩy/chấm phẩy/hai chấm, bỏ dấu câu cuối cụm."""
    parts = re.split(r"[,;:]", line)
    out = []
    for p in parts:
        p = p.strip().strip(".!?…").strip()
        if p:
            out.append(p)
    return out


def split_even(line: str):
    """Dòng 6 tiếng -> 3-3, dòng 8 tiếng -> 4-4. Dòng khác trả None (dùng tách theo dấu phẩy)."""
    words = re.sub(r"[^\w\s]", " ", line).split()
    n = len(words)
    k = 3 if n == 6 else 4 if n == 8 else None
    if k is None:
        return None
    return [" ".join(words[:k]), " ".join(words[k:])]


def trim_silence(a: np.ndarray, thr_db: float = -40.0, margin_ms: int = 30) -> np.ndarray:
    """Cắt im lặng ở đầu và cuối, giữ lại biên nhỏ."""
    peak = float(np.max(np.abs(a))) if a.size else 0.0
    if peak == 0.0:
        return a
    idx = np.where(np.abs(a) > peak * 10 ** (thr_db / 20))[0]
    if idx.size == 0:
        return a
    m = int(SR * margin_ms / 1000)
    return a[max(0, idx[0] - m): min(len(a), idx[-1] + m)]


def silence(ms: int) -> np.ndarray:
    return np.zeros(int(SR * ms / 1000), dtype=np.float32)


def synth_poem(text: str, ref_audio: str, out_path: str,
               pause_line_ms: int = 500, pause_stanza_ms: int = 1800,
               pause_clause_ms: int = 80, pause_couplet_ms: int = 1200,
               pause_half_ms: int = 200, even_rhythm: bool = True) -> None:
    tts = Vieneu()
    stanzas = [[clean_line(ln) for ln in block.splitlines() if clean_line(ln)]
               for block in text.strip().split("\n\n")]
    parts = []
    for si, lines in enumerate(stanzas):
        for li, line in enumerate(lines):
            even = split_even(line) if even_rhythm else None
            clauses = even if even else split_clauses(line)
            gap = pause_half_ms if even else pause_clause_ms
            for ci, clause in enumerate(clauses):
                print("Đang đọc:", clause, flush=True)
                audio = tts.infer(clause, ref_audio=ref_audio, denoise=True)
                parts.append(trim_silence(np.asarray(audio, dtype=np.float32)))
                if ci < len(clauses) - 1:
                    parts.append(silence(gap))
            last_line = li == len(lines) - 1
            last_stanza = si == len(stanzas) - 1
            if last_stanza and last_line:
                break
            if last_line:
                ms = pause_stanza_ms
            elif li % 2 == 1:        # sau dòng 8 (dòng thứ 2, 4, 6...) = cuối cặp lục bát
                ms = pause_couplet_ms
            else:                    # giữa dòng 6 và dòng 8
                ms = pause_line_ms
            parts.append(silence(ms))
    sf.write(out_path, np.concatenate(parts), SR)
    print("Đã lưu", out_path)


if __name__ == "__main__":
    poem_file, ref, out = sys.argv[1], sys.argv[2], sys.argv[3]
    pl = int(float(sys.argv[4])) if len(sys.argv) > 4 else 400
    ps = int(float(sys.argv[5])) if len(sys.argv) > 5 else 1800
    pc = int(float(sys.argv[6])) if len(sys.argv) > 6 else 80
    pcp = int(float(sys.argv[7])) if len(sys.argv) > 7 else 1200
    ph = int(float(sys.argv[8])) if len(sys.argv) > 8 else 200
    er = (sys.argv[9] != "0") if len(sys.argv) > 9 else True
    synth_poem(open(poem_file, encoding="utf-8").read(), ref, out,
               pause_line_ms=pl, pause_stanza_ms=ps, pause_clause_ms=pc,
               pause_couplet_ms=pcp, pause_half_ms=ph, even_rhythm=er)