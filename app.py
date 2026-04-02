import streamlit as st
import pandas as pd
import json
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from datetime import datetime

# 1. 웹앱 기본 설정
st.set_page_config(page_title="성진정밀 연차관리", page_icon="🏢", layout="centered")

# 2. 구글 드라이브 로봇 접속 (이전과 동일)
@st.cache_resource
def get_drive_service():
    key_dict = json.loads(st.secrets["GCP_KEY"])
    creds = service_account.Credentials.from_service_account_info(
        key_dict, scopes=['https://www.googleapis.com/auth/drive.readonly']
    )
    return build('drive', 'v3', credentials=creds)

@st.cache_data(ttl=60) # 1분마다 새로고침 (직원이 입력하면 금방 반영되도록)
def load_excel_from_drive(file_name, sheet_name, skiprows):
    service = get_drive_service()
    results = service.files().list(q=f"name='{file_name}' and trashed=false", spaces='drive', fields='files(id, name)').execute()
    items = results.get('files', [])
    if not items:
        return None 
    file_id = items[0]['id']
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    fh.seek(0)
    return pd.read_excel(fh, sheet_name=sheet_name, skiprows=skiprows, engine='openpyxl')

# 3. 로그인 세션 관리
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_info = None

# ==========================================
# 🖥️ 화면 구성 시작
# ==========================================

# 직원 목록 데이터 미리 불러오기
df_emp = load_excel_from_drive('1. 성진정밀_직원목록.xlsm', sheet_name='사원정보', skiprows=8)

# [로그인 화면]
if not st.session_state.logged_in:
    st.title("🔐 성진정밀 연차 조회")
    st.write("이름과 사번을 입력해주세요.")
    
    if df_emp is None:
        st.error("데이터베이스(직원목록)를 불러오는 중 문제가 발생했습니다.")
    else:
        user_name = st.text_input("이름 (ID)")
        user_id = st.text_input("사번 (Password)", type="password")
        
        if st.button("로그인"):
            # 사번을 문자열로 변환하여 정확히 비교
            df_emp['사번'] = df_emp['사번'].astype(str)
            
            # 입력한 이름과 사번이 일치하는 행 찾기
            user_match = df_emp[(df_emp['성명'] == user_name) & (df_emp['사번'] == str(user_id))]
            
            if not user_match.empty:
                # 퇴사자 필터링 (퇴사일이 비어있거나(NaT) null인 경우만 통과)
                if pd.isna(user_match.iloc[0]['퇴사일']):
                    st.session_state.logged_in = True
                    st.session_state.user_info = user_match.iloc[0]
                    st.rerun()
                else:
                    st.error("퇴사 처리된 계정입니다. 관리자에게 문의하세요.")
            else:
                st.error("이름 또는 사번이 일치하지 않습니다.")

# [메인 화면 (로그인 성공)]
else:
    user = st.session_state.user_info
    
    # 상단 환영 인사
    st.title(f"🎉 환영합니다, {user['성명']} {user['직책']}님!")
    
    # 입사일 포맷팅
    join_date = pd.to_datetime(user['입사일']).strftime('%Y년 %m월 %d일')
    st.info(f"📅 입사일 : {join_date}")
    
    st.divider()
    
    # 연도 선택
    current_year = str(datetime.now().year)
    selected_year = st.selectbox("조회할 연도를 선택하세요", ["2026", "2025", "2024"], index=["2026", "2025", "2024"].index(current_year) if current_year in ["2026", "2025", "2024"] else 0)
    
    st.subheader(f"📊 {selected_year}년 연차 사용 현황")
    
    # 선택한 연도의 연차 데이터 불러오기
    leave_file_name = f"{selected_year} 연차.xlsm"
    df_leave = load_excel_from_drive(leave_file_name, sheet_name='연차입력', skiprows=14)
    
    if df_leave is not None:
        # 내 사번(사원번호)과 일치하는 연차 내역만 필터링 (B열: 사원번호)
        df_leave['사원번호'] = df_leave['사원번호'].astype(str)
        my_leaves = df_leave[df_leave['사원번호'] == str(user['사번'])]
        
        # '연차기간' 합산 (K열)
        used_leave = pd.to_numeric(my_leaves['연차기간'], errors='coerce').sum()
        
        # ⚠️ 총 발생 연차 (임시로 15일 고정, 추후 계산 로직 추가 필요)
        total_leave = 15.0 
        remain_leave = total_leave - used_leave
        
        # 바 막대 생성 (최대치를 넘지 않도록 제한)
        progress_val = min(used_leave / total_leave, 1.0) if total_leave > 0 else 0
        st.progress(progress_val)
        
        # 사용/잔여 연차 텍스트 표시
        col1, col2, col3 = st.columns(3)
        col1.metric("총 발생 연차", f"{total_leave} 일")
        col2.metric("사용 연차", f"{used_leave} 일")
        col3.metric("잔여 연차", f"{remain_leave} 일")
        
        st.divider()
        
        # 하단 사용 내역 상세 표
        st.subheader("📅 상세 사용 내역")
        if not my_leaves.empty:
            # 보여줄 열만 선택 (휴가구분, 시작일, 종료일, 기간)
            display_df = my_leaves[['휴가구분', '연차시작일', '연차종료일', '연차기간']].copy()
            # 날짜 포맷 깔끔하게 변경
            display_df['연차시작일'] = pd.to_datetime(display_df['연차시작일']).dt.strftime('%Y-%m-%d')
            display_df['연차종료일'] = pd.to_datetime(display_df['연차종료일']).dt.strftime('%Y-%m-%d')
            display_df.columns = ['구분', '시작일', '종료일', '사용일수']
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            st.info(f"{selected_year}년도 연차 사용 내역이 없습니다.")
            
    else:
        st.warning(f"{leave_file_name} 파일이 아직 업로드되지 않았습니다.")
    
    st.divider()
    if st.button("로그아웃"):
        st.session_state.logged_in = False
        st.rerun()
