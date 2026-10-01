from schemas import Job, Status, PerformancePlan, PerformanceLine

job = Job(job_id="test_001", image_path="data/samples/tho01.png")
assert job.status == Status.NEW
assert job.speaker_id == "A"

job.raw_text = "Nội dung thử"
job.status = Status.OCR_DONE
job.plan = PerformancePlan(lines=[PerformanceLine(text="Dòng thử")])
path = job.save()

job2 = Job.load(str(path))
assert job2.status == Status.OCR_DONE
assert job2.raw_text == "Nội dung thử"
assert job2.plan.lines[0].text == "Dòng thử"
print("OK: schema lưu và đọc lại đúng")