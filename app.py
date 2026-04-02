import streamlit as st
import pandas as pd

# 1. 웹앱 기본 설정 (탭 이름, 아이콘 등)
st.set_page_config(page_title="성진정밀 연차관리", page_icon="🏢", layout="centered")

# --- 임시 데이터 영역 (나중에 구글 드라이브 엑셀이랑 연결될 부분!) ---
# 실제로는 여기서 pd.read_excel("1. 성진정밀_직원목록.xlsm", skiprows=8) 등을 씁니다.

# 2. 로그인 세션 관리
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_name = ""

# 3. 로그인 화면
if not st.session_state.logged_in:
    st.title("🔐 성진정밀 연차 조회")
    st.write("이름과 사번을 입력해주세요.")
    
    # 텍스트 박스
    user_name = st.text_input("이름 (ID)")
    user_id = st.text_input("사번 (Password)", type="password")
    
    if st.button("로그인"):
        # 임시 로그인 확인 (나중엔 엑셀 데이터의 O열 사번과 K열 퇴사여부 검사)
        if user_name and user_id: 
            st.session_state.logged_in = True
            st.session_state.user_name = user_name
            st.rerun() # 화면 새로고침!
        else:
            st.error("이름과 사번을 입력해주세요.")

# 4. 메인 화면 (로그인 성공 시)
else:
    # 상단 환영 인사
    st.title(f"🎉 환영합니다, {st.session_state.user_name}님!")
    st.info("입사 3주년을 축하합니다! (임시 표시)")
    
    # 연도 선택 드롭박스
    selected_year = st.selectbox("조회할 연도를 선택하세요", ["2026", "2025", "2024"])
    
    st.divider() # 구분선
    
    # 연차 요약 (가운데 바 막대)
    st.subheader(f"📊 {selected_year}년 연차 현황")
    
    # 임시 계산값
    total_leave = 15.0
    used_leave = 6.5
    remain_leave = total_leave - used_leave
    
    # 바 막대 생성! (사용량 / 총량)
    progress_val = used_leave / total_leave
    st.progress(progress_val)
    
    # 사용/잔여 연차 텍스트 표시
    col1, col2, col3 = st.columns(3)
    col1.metric("총 발생 연차", f"{total_leave} 일")
    col2.metric("사용 연차", f"{used_leave} 일")
    col3.metric("잔여 연차", f"{remain_leave} 일")
    
    st.divider()
    
    # 하단 사용 내역 조회
    st.subheader("📅 상세 사용 내역")
    
    # 표(테이블) 형태로 깔끔하게 띄우기
    st.table(pd.DataFrame({
        "사용 날짜": ["2026-02-10", "2026-03-15"],
        "휴가 구분": ["연차", "반차"],
        "사용 일수": [1.0, 0.5]
    }))
    
    # 로그아웃 버튼
    if st.button("로그아웃"):
        st.session_state.logged_in = False
        st.rerun()