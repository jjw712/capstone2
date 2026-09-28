"""모든 탭이 같이 쓰는 표시 요소."""

import streamlit as st

from client import API_URL, ApiError, get_health

# roboadvisor.DISCLAIMER와 같은 문구 (대시보드는 src를 import 하지 않는다)
DISCLAIMER = (
    "본 시스템은 교육 목적으로 개발되었으며 실제 투자 조언에 사용할 수 없습니다. "
    "백테스트 성과는 미래 수익을 보장하지 않습니다."
)


def api_status_sidebar() -> None:
    """사이드바에 API 연결 상태와 모델 로드 여부를 표시한다."""
    with st.sidebar:
        st.caption(f"API: {API_URL}")
        try:
            health = get_health()
        except ApiError:
            st.error("API 연결 실패")
            return
        st.success("API 정상")
        st.caption("모델 로드됨" if health.get("model_loaded") else "모델 미로드")


def page_placeholder(title: str, owner: str, todo: list[str]) -> None:
    """아직 구현 전인 탭의 자리 표시."""
    st.title(title)
    st.info(f"구현 예정 · 내용 담당: {owner}")
    for item in todo:
        st.markdown(f"- {item}")


def disclaimer_footer() -> None:
    st.divider()
    st.caption(DISCLAIMER)
