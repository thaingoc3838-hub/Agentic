from agents import a1_vision, a2_verifier, a4_planner, a5_run, a6_eval
from schemas import Job

job = Job(job_id="loop_test", image_path="data/samples/tho02.png")
job = a2_verifier.run(a1_vision.run(job))
job = a4_planner.initial_plan(job)

for rnd in range(3):
    job = a5_run.run(job)
    job = a6_eval.run(job)
    print(f"Vòng {rnd+1}: params={ {k: round(v) for k, v in job.plan_params.items()} }")
    for k in ("pause_short_ms_mean", "pause_long_ms_mean"):
        print("   ", k, job.eval_detail[k].get("value"), "delta:", job.eval_detail[k].get("delta"))
    if a4_planner.converged(job):
        print("Đã hội tụ"); break
    job = a4_planner.revise(job)
