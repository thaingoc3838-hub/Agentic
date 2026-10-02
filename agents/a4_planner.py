"""a4_planner.py - Tác nhân A4: quyết định và điều chỉnh tham số trình diễn."""
from agents.a6_eval import reference_stats
from schemas import Job

TOL_MS = 30          # sai lệch quãng nghỉ chấp nhận được


def initial_plan(job: Job) -> Job:
    st = reference_stats()
    job.plan_params = {
        "pause_line_ms": st["pause_short_ms_mean"]["target"],
        "pause_stanza_ms": st["pause_long_ms_mean"]["target"],
    }
    return job


def converged(job: Job) -> bool:
    """Dừng khi các quãng nghỉ đo được đã nằm trong dung sai (chỉ xét chỉ số điều khiển được)."""
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