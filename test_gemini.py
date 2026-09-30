import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

try:
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents="Trả lời đúng một câu: Hà Nội là thủ đô của nước nào?"
    )
    print(response.text)
except Exception as e:
    print("LOI:", type(e).__name__)
    print(str(e)[:500])