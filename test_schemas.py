from schemas import Job, Status

job = Job(job_id="test_001", image_path="data/samples/tho01.jpg")
print(job.status)

job.raw_text = "Nội dung thử"
job.status = Status.OCR_DONE
path = job.save()
print("Đã lưu:", path)

job2 = Job.load(str(path))
print(job2.status, job2.raw_text)