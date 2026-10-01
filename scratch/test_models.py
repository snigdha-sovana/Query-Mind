import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

for m in ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-1.5-flash"]:
    print(f"\n--- Testing model: {m} ---")
    try:
        llm = ChatGoogleGenerativeAI(model=m, google_api_key=api_key)
        res = llm.invoke("Hi! Reply with 'OK'.")
        print(f"SUCCESS with {m}:", res.content)
    except Exception as e:
        print(f"FAILED with {m}:", type(e).__name__, e)
