import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from querymind.engine.sql_gen import SQLEngine
from querymind.graph.builder import build_graph
from querymind.llm.client import get_llm_caller

db_path = str(Path(__file__).resolve().parents[1] / "data" / "dev_databases" / "student_club" / "student_club.sqlite")
print("Testing DB path:", db_path)

llm = get_llm_caller()
engine = SQLEngine(db_path, llm_caller=llm)
app = build_graph(engine, llm_caller=llm)

question = "Which club events exceeded their budget allocation, and what were the total expenses incurred for those events?"
print(f"Question: {question}\n")

res = app.invoke({"question": question})
print("=== FINAL SYNTHESIZED REPORT ===")
print(res.get("report"))
