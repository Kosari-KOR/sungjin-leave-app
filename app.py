st.markdown("""
<style>
    /* =========================================
       🚫 Streamlit 기본 UI 완벽 숨기기
       ========================================= */
    header { visibility: hidden !important; display: none !important; }
    [data-testid="stToolbar"] { visibility: hidden !important; display: none !important; }
    footer { visibility: hidden !important; display: none !important; }
    .viewerBadge_container__1QSob { display: none !important; }
    [data-testid="stDecoration"] { display: none !important; }

    /* 전체 상단 여백 확 줄이기 */
    .block-container { padding-top: 1.5rem !important; padding-bottom: 1rem !important; }
    
    /* ... (기존에 있던 토스 스타일 CSS 내용들 그대로 유지) ... */
