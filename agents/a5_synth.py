"""a5_synth.py - Đọc thơ từng dòng bằng giọng clone, chèn quãng nghỉ theo dòng/khổ.
Chạy trong venv_tts:  python agents/a5_synth.py <file_thơ.txt> <ref.wav> <out.wav>
"""
import sys

import numpy as np
import soundfile as sf
from vieneu import Vieneu

SR = 48000


def synth_poem(text: str, ref_audio: str, out_path: str,
               pause_line_ms: int = 360, pause_stanza_ms: int = 1800) -> None:
    tts = Vieneu()
    stanzas = [[ln.strip() for ln in block.splitlines() if ln.strip()]
               for block in text.strip().split("\n\n")]
    parts = []
    for si, lines in enumerate(stanzas):
        for li, line in enumerate(lines):
            print("Đang đọc:", line, flush=True)
            audio = tts.infer(line, ref_audio=ref_audio, denoise=True)
            parts.append(np.asarray(audio, dtype=np.float32))
            last_line = li == len(lines) - 1
            last_stanza = si == len(stanzas) - 1
            if last_stanza and last_line:
                break
            ms = pause_stanza_ms if last_line else pause_line_ms
            parts.append(np.zeros(int(SR * ms / 1000), dtype=np.float32))
    sf.write(out_path, np.concatenate(parts), SR)
    print("Đã lưu", out_path)


if __name__ == "__main__":
    poem_file, ref, out = sys.argv[1], sys.argv[2], sys.argv[3]
    pl = int(float(sys.argv[4])) if len(sys.argv) > 4 else 360
    ps = int(float(sys.argv[5])) if len(sys.argv) > 5 else 1800
    synth_poem(open(poem_file, encoding="utf-8").read(), ref, out,
               pause_line_ms=pl, pause_stanza_ms=ps)