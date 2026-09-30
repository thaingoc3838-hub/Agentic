import os
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("GEMINI_API_KEY")
print("Đã đọc key" if key else "KHÔNG đọc được key", "| độ dài:", len(key) if key else 0)