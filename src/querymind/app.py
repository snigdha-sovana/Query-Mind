"""Streamlit UI for QueryMind."""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import streamlit as st

from langgraph.checkpoint.memory import MemorySaver

from querymind.engine.sql_gen import SQLEngine
from querymind.graph.builder import build_graph

# Setup Paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB = BASE_DIR / "tests" / "fixtures" / "fixture.sqlite"

st.set_page_config(page_title="QueryMind Analyst", page_icon="🧠", layout="wide")

st.title("🧠 QueryMind Autonomous Data Analyst")

def discover_databases() -> dict[str, str]:
    dbs = {"Default Fixture (Sales)": str(DEFAULT_DB)}
    data_dev = BASE_DIR / "data" / "dev_databases"
    if data_dev.exists():
        for db_file in sorted(data_dev.glob("*/*.sqlite")):
            db_name = db_file.stem.replace("_", " ").title()
            dbs[f"BIRD: {db_name}"] = str(db_file)
    dbs["Custom Path..."] = "custom"
    return dbs

with st.sidebar:
    st.header("Configuration")
    discovered_dbs = discover_databases()
    selected_option = st.selectbox(
        "Select Database",
        options=list(discovered_dbs.keys()),
        index=0,
    )
    if selected_option == "Custom Path...":
        db_path_input = st.text_input("Custom Database Path (SQLite)", value=str(DEFAULT_DB))
    else:
        db_path_input = discovered_dbs[selected_option]
        st.caption(f"📁 `{db_path_input}`")

    max_iters = st.number_input("Max Investigation Iters", min_value=1, max_value=5, value=3)
    hitl_mode = st.toggle("Human-in-the-Loop Review", value=True, help="Pause before SQL execution to review investigation plan")
    
    st.markdown("---")
    st.markdown("""
    **Architecture:**
    1. **Manager**: Plans the investigation.
    2. **Analyst**: Generates & repairs SQL.
    3. **Critic**: Validates the evidence.
    4. **Report**: Synthesizes findings.
    """)

# Ensure DB exists
if not os.path.exists(db_path_input):
    st.error(f"Database not found at: {db_path_input}")
    st.stop()


# State initialization
if "checkpointer" not in st.session_state:
    st.session_state.checkpointer = MemorySaver()
if "messages" not in st.session_state:
    st.session_state.messages = []
if "thread_id" not in st.session_state:
    st.session_state.thread_id = "session_1"

# Initialize graph
def get_graph(db_path: str, max_iterations: int, pause_for_approval: bool = True):
    llm_caller = None
    if os.environ.get("MOCK_LLM") == "1":
        def mock_llm(prompt: str) -> str:
            if "Split this business question" in prompt:
                return "What is the revenue?"
            if "Write a SQLite query" in prompt:
                return "SELECT 1 as revenue;"
            if "Does this evidence support" in prompt:
                return "SUFFICIENT\n\nYes."
            return "Mocked insight and report."
        llm_caller = mock_llm
    else:
        from querymind.llm.client import get_llm_caller
        try:
            llm_caller = get_llm_caller()
        except RuntimeError as e:
            st.error(str(e))
            st.stop()

    engine = SQLEngine(db_path, llm_caller=llm_caller)
    return build_graph(
        engine=engine,
        llm_caller=llm_caller,
        max_iterations=max_iterations,
        checkpointer=st.session_state.checkpointer,
        interrupt_before=["analyst"] if pause_for_approval else None,
    )


graph = get_graph(db_path_input, max_iters, pause_for_approval=hitl_mode)
thread_config = {"configurable": {"thread_id": st.session_state.thread_id}}

# Display history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Get current graph state
current_state = graph.get_state(thread_config)
is_paused = current_state.next == ('analyst',)

# Render the stream function
def render_stream(stream_generator):
    status_placeholder = st.empty()
    for step_event in stream_generator:
        if not step_event or not isinstance(step_event, dict):
            continue
        node_name = list(step_event.keys())[0]
        state = step_event.get(node_name) or {}

        if node_name == "profiler":
            profile_text = state.get("data_profile")
            if profile_text:
                with st.expander("🔍 Data Profiler", expanded=True):
                    st.markdown(profile_text)
                status_placeholder.markdown(f"*{node_name} finished profiling...*")

        elif node_name == "manager":
            with st.expander(f"📝 Manager (Iteration {state.get('iteration', 1)})", expanded=True):
                st.write("**Plan:**")
                for q in state.get("plan") or []:
                    st.write(f"- {q}")
            status_placeholder.markdown(f"*{node_name} finished planning...*")

        elif node_name == "analyst":
            with st.expander("🛠️ Analyst", expanded=False):
                for res in state.get("analyst_results") or []:
                    st.write(f"**Sub-Q:** {res.get('subquestion')}")
                    if res.get("success"):
                        st.code(res.get("sql", ""), language="sql")
                        st.write(f"**Result Preview:** {str(res.get('result', []))[:100]}...")
                    else:
                        st.error(f"Failed: {res.get('error')}")
            status_placeholder.markdown(f"*{node_name} retrieved evidence...*")
            
        elif node_name == "critic":
            with st.expander("⚖️ Critic", expanded=True):
                verdict = state.get("verdict", "")
                reason = state.get("verdict_reason", "")
                if verdict == "SUFFICIENT":
                    st.success(f"**Verdict:** {verdict}")
                else:
                    st.warning(f"**Verdict:** {verdict}")
                st.write(f"**Reason:** {reason}")
            status_placeholder.markdown(f"*{node_name} judged the evidence...*")
            
        elif node_name == "report":
            report_content = state.get("report") or ""
            import re
            report_content = re.sub(r"<details>.*?</details>", "", report_content, flags=re.DOTALL)
            report_content = re.sub(r"</?details>", "", report_content)
            report_content = re.sub(r"</?summary>", "", report_content).strip()
            st.markdown(report_content)
            st.session_state.messages.append({"role": "assistant", "content": report_content})
            
            from querymind.agents.report import detect_chartable_data
            chart_spec = detect_chartable_data(state.get("analyst_results") or [])
            if chart_spec and chart_spec.get("chartable"):
                with st.expander(f"📊 {chart_spec['title']}", expanded=True):
                    try:
                        import pandas as pd
                        df = pd.DataFrame(chart_spec["data"])
                        st.bar_chart(df, x=chart_spec["x_col"], y=chart_spec["y_col"])
                    except Exception:
                        st.write(chart_spec["data"])

            try:
                from querymind.utils.trace import save_run_trace
                trace_file = save_run_trace(
                    question=state.get("question", ""),
                    final_state=state,
                    trace_id=st.session_state.thread_id,
                )
                st.caption(f"📁 Machine-readable trace saved: `{trace_file}`")
            except Exception:
                pass

            status_placeholder.empty()

if is_paused:
    with st.chat_message("assistant"):
        st.info("⏸️ **Investigation Paused for Review**")
        with st.expander("Proposed Investigation Plan", expanded=True):
            plan = current_state.values.get("plan", [])
            for q in plan:
                st.write(f"- {q}")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Approve & Execute queries", type="primary"):
                with st.spinner("Resuming investigation..."):
                    render_stream(graph.stream(None, thread_config))
                st.rerun()
        with col2:
            if st.button("Reject & Start Over"):
                # Simple hack: bump thread ID to start fresh
                st.session_state.thread_id = f"session_{len(st.session_state.messages) + 2}"
                st.rerun()

elif prompt := st.chat_input("Ask a business question..."):
    # Generate new unique thread ID for fresh investigation state
    import uuid
    st.session_state.thread_id = f"session_{uuid.uuid4().hex[:8]}"
    thread_config = {"configurable": {"thread_id": st.session_state.thread_id}}

    # Add user message to state and display
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").markdown(prompt)

    # Start new graph execution
    with st.chat_message("assistant"):
        render_stream(graph.stream({"question": prompt}, thread_config))
    
    st.rerun()
