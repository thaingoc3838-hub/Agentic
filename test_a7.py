import glob
from agents import a7_drive
from schemas import Job

latest = sorted(glob.glob("outputs/*_tho01.json"))[-1]   # job mới nhất
job = Job.load(latest)
job = a7_drive.run(job)
print(job.status.value, job.drive_links, job.errors)