import os
import subprocess
import sys
import time
from pathlib import Path
import pytest
import requests

try:
    from playwright.sync_api import Page, expect
except ImportError:
    Page = Any = object  # type: ignore
    pytestmark = pytest.mark.skip("Playwright not installed")


@pytest.fixture(scope="session")
def streamlit_server():
    """Start Streamlit in a subprocess for testing."""
    # Set MOCK_LLM so we don't hit the real API or need a key
    env = os.environ.copy()
    env["MOCK_LLM"] = "1"
    
    app_path = Path(__file__).parent.parent / "src" / "querymind" / "app.py"
    
    # Start streamlit on a specific port for testing
    process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(app_path), "--server.port", "8502", "--server.headless", "true"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for the server to start
    started = False
    for _ in range(15):
        try:
            res = requests.get("http://localhost:8502/_stcore/health")
            if res.status_code == 200:
                started = True
                break
        except requests.ConnectionError:
            time.sleep(1)
            
    if not started:
        process.kill()
        pytest.fail("Streamlit server failed to start")
        
    yield "http://localhost:8502"
    
    # Cleanup
    process.terminate()
    try:
        outs, errs = process.communicate(timeout=5)
        print("STREAMLIT STDOUT:\n", outs.decode() if outs else "")
        print("STREAMLIT STDERR:\n", errs.decode() if errs else "")
    except subprocess.TimeoutExpired:
        process.kill()


def test_app_title_and_query_flow(page: Page, streamlit_server: str):
    """Test the main Streamlit UI flow with mocked LLM."""
    page.goto(streamlit_server)
    
    # Verify title
    expect(page.locator("h1").filter(has_text="QueryMind")).to_be_visible(timeout=10000)
    
    # Input a question
    chat_input = page.get_by_placeholder("Ask a business question...")
    chat_input.fill("What is the revenue?")
    chat_input.press("Enter")
    
    # Wait for the profiler and manager to finish and the HITL interrupt to appear
    expect(page.get_by_text("Data Profiler")).to_be_visible(timeout=30000)
    expect(page.get_by_text("Investigation Paused for Review")).to_be_visible(timeout=30000)
    
    # Approve the execution
    page.get_by_role("button", name="Approve & Execute queries").click()
    
    # Expect final report to render
    expect(page.get_by_text("Evidence", exact=False)).to_be_visible(timeout=30000)
