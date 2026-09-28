"""Streamlit 진입점. 실행: streamlit run dashboard/app.py"""

import streamlit as st

from components.common import api_status_sidebar, disclaimer_footer

st.set_page_config(page_title="Robo-Advisor", layout="wide")

PAGES = [
    st.Page("pages/portfolio.py", title="포트폴리오 현황", default=True),
    st.Page("pages/rl_performance.py", title="강화학습 성과"),
    st.Page("pages/shap_explain.py", title="SHAP 해석"),
    st.Page("pages/research.py", title="에이전트 리서치"),
    st.Page("pages/anova.py", title="ANOVA 검증 결과"),
    st.Page("pages/risk_monitor.py", title="리스크 모니터링"),
]

page = st.navigation(PAGES)
api_status_sidebar()
page.run()
disclaimer_footer()
