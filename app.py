import streamlit as st
import pandas as pd
import json
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from datetime import datetime
import math

# ==========================================
# 1. 디자인 및 스타일 설정 (CSS)
# ==========================================
st.set_page_config(page_title="성진정밀 연차관리", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    /* 메인 타이틀 및 섹션 헤더 (기존보다 2단계 크게) */
    .main-title { font-size: 1.8rem; font-weight: 800; color: #111; margin-bottom: 8px; line-height: 1.3; }
    .section-header { font-size: 1.3rem; font-weight: 700; color: #333; margin-top: 25px; margin-bottom: 15px; }
    
    /* 스마트폰 가로 정렬을 위한 메트릭 컨테이너 */
    .metric-container {
        display: flex;
        justify-content: space-between;
        background-color: #f8f9fa;
        border-radius: 12px;
        padding: 15px 10px;
        margin: 10px 0;
    }
    .metric-box { text-align: center; flex: 1; }
    .metric-label { font-size: 0.75rem; color: #666; margin-bottom: 4px; }
    .metric-value { font-size: 1.1rem; font-weight: 800; color: #222; }
    .metric-unit { font-size: 0.8rem; font-weight: 400; margin-left: 2px; }

    /* 더 두꺼워진 프로그레스 바 */
    .progress-bg { background-color: #e9ecef; border-radius: 15px; height: 22px; width: 100%; overflow: hidden; margin: 15px 0; }
    .progress-fill { background-color: #007bff; height: 100%; border-radius: 15px; transition: width 0.5s ease-in-out; }
    
    /* 상세 내역 리스트 (1줄 스타일) */
    .history-item { 
        border-bottom: 1px solid #f0f0f0; 
        padding: 15px 5px; 
        display: flex; 
        justify-content: space-between; 
        align-items: center;
    }
    .history-info { display: flex; flex-direction: column; }
    .history-type { font-size: 1rem; font-weight: 600; color: #333; }
    .history-date { font-size: 0.85rem; color: #999; }
    .history-days { font-size: 1.05rem; font-weight: 700; color: #007bff; }

    /* 입력창 및 버튼 최적화 */
    .stButton>button { border-radius: 10px; height: 3rem; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 구글 드라이브 연결 및 데이터 로딩 (최적화)
# ==========================================
@st.cache_resource
def get_drive_service():
    key_dict = json.loads(st.secrets["GCP_KEY"])
    creds = service_account.Credentials.from_service_account_info(
        key_dict, scopes=['https://www.googleapis.com/auth/drive.readonly']
    )
    return build('drive', 'v3', credentials=creds)

@st.cache_data(ttl=300) # 캐시 시간을 5분으로 늘려 로그인 속도 개선
def load_excel_from_drive(file_name, sheet_name, skiprows, usecols=None):
    try:
        service = get_drive_service()
        results = service.files().list(q=f"name='{file_name}' and trashed=false", spaces='drive', fields='files(id, name)').execute()
        items = results.get('files', [])
        if not items: return None 
        
        file_id = items[0]['id']
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
        fh.seek(0)
        
        df = pd.read_excel(fh, sheet_name=sheet_name, skiprows=skiprows, usecols=usecols, engine='openpyxl')
        df.columns = df.columns.astype(str).str.replace(r'\s+', '', regex=True) 
        return df
    except:
        return None

def calculate_annual_leave(join_date_str, target_year):
    join_date = pd.to_datetime(join_date_str)
    target_year = int(target_year)
    join_year = join_date.year
    years_employed = target_year - join_year
    
    if years_employed < 1: return 0.0
    if years_employed == 1:
        days_in_join_year = (datetime(join_year, 12, 31) - join_date).days + 1
        return round(15 * (days_in_join_year / 365.0), 1)
    
    base_leave = 15
    bonus_leave = math.floor((years_employed - 1) / 2)
    return min(base_leave + bonus_leave, 25.0)

# ==========================================
# 3. 앱 로직
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_info = None

# [로그인 화면]
if not st.session_state.logged_in:
    st.markdown("<div class='main-title'>🏢 성진정밀 연차조회</div>", unsafe_allow_html=True)
    user_name = st.text_input("👤 이름", placeholder="성함을 입력하세요")
    user_id = st.text_input("🔑 사번", type="password", placeholder="사번 4자리를 입력하세요")
    
    if st.button("로그인", use_container_width=True):
        # 데이터 로딩 시 Spinner를 사용하여 사용자에게 진행 상황 알림 (체감 속도 개선)
        with st.spinner('데이터베이스에 안전하게 접속 중입니다...'):
            df_emp = load_excel_from_drive('1. 성진정밀_직원목록.xlsm', sheet_name='사원정보', skiprows=8, usecols="B:R")
            
            if df_emp is not None:
                df_emp['사번'] = df_emp['사번'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(4)
                user_match = df_emp[(df_emp['성명'] == user_name) & (df_emp['사번'] == str(user_id).zfill(4))]
                
                if not user_match.empty:
                    if pd.isna(user_match.iloc[0]['퇴사일']):
                        st.session_state.logged_in = True
                        st.session_state.user_info = user_match.iloc[0]
                        st.rerun()
                    else:
                        st.error("퇴사 처리된 계정입니다.")
                else:
                    st.error("이름 또는 사번이 일치하지 않습니다.")
            else:
                st.error("직원 목록을 불러올 수 없습니다. 네트워크를 확인하세요.")

# [메인 화면]
else:
    user = st.session_state.user_info
    st.markdown(f"<div class='main-title'>👋 {user['성명']} {user['직책']}님,<br>반갑습니다.</div>", unsafe_allow_html=True)
    
    # 입사일 & 연도 선택 (한 줄 배치)
    c1, c2 = st.columns([1.2, 1])
    join_date_fmt = pd.to_datetime(user['입사일']).strftime('%y.%m.%d')
    with c1:
        st.markdown(f"<div style='margin-top:12px; font-size:1rem; color:#666;'>📅 입사일: <b>{join_date_fmt}</b></div>", unsafe_allow_html=True)
    with c2:
        current_year = str(datetime.now().year)
        selected_year = st.selectbox("연도", ["2026", "2025", "2024"], index=["2026", "2025", "2024"].index(current_year) if current_year in ["2026", "2025", "2024"] else 0, label_visibility="collapsed")
    
    # 데이터 로딩
    with st.spinner(f'{selected_year}년 데이터를 가져오고 있습니다...'):
        df_leave = load_excel_from_drive(f"{selected_year} 연차.xlsm", sheet_name='연차입력', skiprows=14, usecols="B:K")
    
    if df_leave is not None:
        # 연차 계산
        df_leave['사원번호'] = df_leave['사원번호'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(4)
        my_leaves = df_leave[df_leave['사원번호'] == str(user['사번']).zfill(4)]
        used_leave = pd.to_numeric(my_leaves['연차기간'], errors='coerce').sum()
        total_leave = calculate_annual_leave(user['입사일'], selected_year)
        remain_leave = max(total_leave - used_leave, 0)
        
        # 1. 연차 사용 현황 (막대 두껍게)
        st.markdown("<div class='section-header'>📊 연차 사용 현황</div>", unsafe_allow_html=True)
        progress_percent = min((used_leave / total_leave) * 100, 100) if total_leave > 0 else 0
        st.markdown(f"""
        <div class="progress-bg"><div class="progress-fill" style="width: {progress_percent}%;"></div></div>
        """, unsafe_allow_html=True)
        
        # 2. 메트릭 가로 정렬 (모바일 강제 가로 유지)
        st.markdown(f"""
        <div class="metric-container">
            <div class="metric-box">
                <div class="metric-label">총 연차</div>
                <div class="metric-value">{total_leave}<span class="metric-unit">일</span></div>
            </div>
            <div class="metric-box" style="border-left: 1px solid #ddd; border-right: 1px solid #ddd;">
                <div class="metric-label">사용</div>
                <div class="metric-value" style="color:#007bff;">{used_leave}<span class="metric-unit">일</span></div>
            </div>
            <div class="metric-box">
                <div class="metric-label">잔여</div>
                <div class="metric-value" style="color:#28a745;">{remain_leave}<span class="metric-unit">일</span></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.divider()
        
        # 3. 상세 내역 (이름 변경 및 디자인 개선)
        st.markdown(f"<div class='section-header'>📂 {selected_year[2:]}년 연차 내역</div>", unsafe_allow_html=True)
        if not my_leaves.empty:
            for _, row in my_leaves.iterrows():
                l_type = row.get('휴가구분', '연차')
                l_date = pd.to_datetime(row['연차시작일']).strftime('%Y.%m.%d')
                l_days = row.get('연차기간', 0)
                st.markdown(f"""
                <div class="history-item">
                    <div class="history-info">
                        <div class="history-type">{l_type}</div>
                        <div class="history-date">{l_date}</div>
                    </div>
                    <div class="history-days">-{l_days}일</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info(f"{selected_year}년도 내역이 없습니다.")
    
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("로그아웃", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()
