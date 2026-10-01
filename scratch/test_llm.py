import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from querymind.llm.client import get_llm_caller

try:
    client = get_llm_caller()
    print("Invoking LLM...")
    res = client("Hello, answer in 1 word: hi")
    print("Result:", res)
except Exception as e:
    print("Error caught:", type(e).__name__, e)
