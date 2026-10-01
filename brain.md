# QueryMind Brain

## 1. Project state
QueryMind is a multi-agent Autonomous Data Analyst (LangGraph) over SQLite. Phase 1 of the SQL engine is implemented and covered by an offline pytest suite: read-only execution with timeout/row limits, lexical schema linking, SQL generation with a repair loop, a Mini-Dev eval harness, and a Manager → Analyst → Critic → Report graph with a hard critic guard.

## 2. Architecture & key locations
- **`src/querymind/engine/`**: F1–F3 (catalog, lexical linker, generate, execute/repair, SQL safety).
- **`src/querymind/llm/client.py`**: Gemini client with 429 retry; tests inject a callable instead.
- **`src/querymind/eval/`**: BIRD Mini-Dev path discovery + execution-accuracy harness.
- **`src/querymind/agents/` + `graph/`**: plan, critic guard, grounded report, LangGraph cycle.
- **`tests/fixtures/`**: hand-built `fixture.sqlite` (customers/products/sales) — not BIRD.

## 3. Current focus
Keep the offline suite green. Next: real Gemini eval numbers on Mini-Dev, richer schema linking (embeddings), HITL/checkpoints, Streamlit demo.

## 4. How to run
```
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
pytest
python -m querymind.eval --gold --limit 5 --db-id student_club
```

## 5. Session log
- **2026-09-18**: Initialized repository scaffold.
- **2026-09-18**: Implemented Phase 1 engine, eval harness, critic/report guards, and LangGraph loop with pytest coverage.
- **2026-09-25**: Completed full project analysis and created QUERYMIND_ANALYSIS.md / .docx and QUERYMIND_IMPLEMENTATION_PLAN.md.
- **2026-09-25**: Completed Phase 1 test fixes (Playwright Chromium install & builder checkpointer refactor; 24/24 tests green).
- **2026-09-25**: Completed Phase 2 BIRD benchmark evaluation (eval_results/student_club_gold.json & eval_results/ablation_summary.json generated).
- **2026-09-25**: Completed Phase 3 & 4 enhancements (automated Streamlit charts, distinct column value sampling, LLM plan revision, machine-readable run traces in logs/traces/, BaseDBExecutor adapter).
