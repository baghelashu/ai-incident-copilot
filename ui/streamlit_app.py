"""Streamlit front end: streamlit run ui/streamlit_app.py"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from copilot.agent import IncidentCopilot  # noqa: E402

st.set_page_config(page_title="Incident Copilot", layout="wide")
st.title("AI Incident & Log Analysis Copilot")


@st.cache_resource
def copilot() -> IncidentCopilot:
    return IncidentCopilot()


uploaded = st.file_uploader("Upload a log file (Spring Boot, syslog, generic)", type=["log", "txt"])
question = st.text_input("Ask a question", placeholder="Why did the order service fail last night?")

if uploaded and st.button("Analyze", type="primary"):
    with st.spinner("Parsing logs, searching runbooks, analyzing..."):
        result = copilot().run(uploaded.getvalue().decode("utf-8", errors="replace"), question)
    col1, col2 = st.columns([3, 2])
    with col1:
        st.markdown(result["report"])
    with col2:
        st.subheader("Error clusters")
        st.dataframe(pd.DataFrame(result["clusters"])[["level", "count", "logger", "exception", "signature"]], use_container_width=True)
        if result["anomalies"]:
            st.subheader("Anomalies")
            st.dataframe(pd.DataFrame(result["anomalies"]), use_container_width=True)
        st.subheader("Sources")
        for c in result["context"]:
            st.caption(f"{c['title']} — {c['source']}")
