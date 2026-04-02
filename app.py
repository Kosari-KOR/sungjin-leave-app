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
    /* 1. 메인 타이틀 스마트폰 규격화 (줄바꿈 방지 및 자동 크기 조절) */
    .main-title { 
        font-size: clamp(1.4rem, 5vw, 1.8rem); /* 폰에 맞춰 글자 크기 유동적 조절 */
        word-break: keep-all; /* 단어 중간에 끊기지 않도록 설정 */
        font-weight: 800; 
        color: #111; 
        margin-bottom: 8px; 
        line-height: 1.3; 
    }
    
    .section-header { font-size: 1.3rem; font-weight: 700; color: #333; margin-top: 25px; margin-bottom: 15px; }
    
    /* 2. 셀렉트박스(조회년도) 내부 글자 크기 확대 */
    div[data-baseweb="select"] > div {
        font-size: 1.2rem !important;
        padding: 5px !important;
    }

    /* 3. 메트릭 박스 (박스 대비 글자 크기 대폭 확대) */
    .metric-container {
        display: flex;
        justify-content: space-between;
        background-color: #f8f9fa;
        border-radius: 12px;
        padding: 20px 10px; /* 위아래 여백을 늘려서 넉넉하게 */
        margin: 10px 0;
    }
    .metric-box { text-align: center; flex: 1; }
    .metric-label { font-size: 1.0rem; font-weight: 700; color: #555; margin-bottom: 5px; } /* 라벨 크기 확대 */
    .metric-value { font-size: 1.6rem; font-weight: 800; color: #222; } /* 숫자 엄청 크게 */
    .metric-unit { font-size: 1.1rem; font-weight: 600; margin-left: 2px; } /* '일' 글자 크기도 비례해서 확대 */

    /* 프로그레스 바 */
    .progress-bg { background-color: #e9ecef; border-radius: 15px; height: 22px; width: 100%; overflow: hidden; margin: 15px 0; }
    .progress-fill { background-color: #007bff; height: 100%; border-radius: 15px; transition: width 0.5s ease-in-out; }
    
    /* 4. 상세 내역 리스트 (한 줄로 꽉 차게 변경) */
    .history-row { 
        display: flex; 
        justify-content: space-between; 
        align-items: center; 
        border-bottom: 1px solid #f0f0f0; 
        padding: 16px 5px; 
    }
    .history-left { display: flex; align-items: center; gap: 15px; } /* 구분과 날짜 사이 간격 */
    .history-type { font-size: 1.1rem; font-weight: 700; color: #222; min-width: 45px; }
    .history-date { font-size: 1.05rem; color: #666; font-weight: 500; }
    .history-days { font-size: 1.2rem; font-weight: 800; color: #007bff; }

    .stButton>button { border-radius: 10px; height: 3rem; font-weight: 600; font-size: 1.1rem; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 구글 드라이브 연결 및 데이터 로딩
# ==========================================
@st.cache_resource
def get_drive_service():
    key_dict = json.loads(st.secrets["GCP_KEY"])
    creds = service_account.Credentials.from_service_account_info(
        key_dict, scopes=['https://www.googleapis.com/auth/drive.readonly']
    )
    return build('drive', 'v3', credentials=creds)

@st.cache_data(ttl=300) 
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
        # 문구 변경: 로딩중
        with st.spinner('로딩중...'):
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
                st.error("데이터를 불러올 수 없습니다.")

# [메인 화면]
else:
    user = st.session_state.user_info
    st.markdown(f"<div class='main-title'>👋 {user['성명']} {user['직책']}님,<br>반갑습니다.</div>", unsafe_allow_html=True)
    
    st.divider()
    
    # 1. 입사일 폰트 크기 확대
    join_date_fmt = pd.to_datetime(user['입사일']).strftime('%Y.%m.%d')
    st.markdown(f"<div style='font-size:1.15rem; color:#444; margin-bottom: 15px;'>📅 입사일 : <span style='font-weight:700; color:#222;'>{join_date_fmt}</span></div>", unsafe_allow_html=True)
    
    # 2. 조회년도 텍스트 크기 확대 및 아래로 배치
    st.markdown("<div style='font-size:1.3rem; font-weight:800; color:#111; margin-bottom: 5px;'>🔍 조회년도</div>", unsafe_allow_html=True)
    current_year = str(datetime.now().year)
    selected_year = st.selectbox("연도", ["2026", "2025", "2024"], index=["2026", "2025", "2024"].index(current_year) if current_year in ["2026", "2025", "2024"] else 0, label_visibility="collapsed")
    
    # 문구 변경: 로딩중
    with st.spinner('로딩중...'):
        df_leave = load_excel_from_drive(f"{selected_year} 연차.xlsm", sheet_name='연차입력', skiprows=14, usecols="B:K")
    
    if df_leave is not None:
        df_leave['사원번호'] = df_leave['사원번호'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(4)
        my_leaves = df_leave[df_leave['사원번호'] == str(user['사번']).zfill(4)]
        used_leave = pd.to_numeric(my_leaves['연차기간'], errors='coerce').sum()
        total_leave = calculate_annual_leave(user['입사일'], selected_year)
        remain_leave = max(total_leave - used_leave, 0)
        
        st.markdown("<div class='section-header'>📊 연차 사용 현황</div>", unsafe_allow_html=True)
        progress_percent = min((used_leave / total_leave) * 100, 100) if total_leave > 0 else 0
        st.markdown(f"""
        <div class="progress-bg"><div class="progress-fill" style="width: {progress_percent}%;"></div></div>
        """, unsafe_allow_html=True)
        
        # 메트릭 박스 내 글자 크기 대폭 상향 적용
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
        
        st.markdown(f"<div class='section-header'>📂 {selected_year[2:]}년 연차 내역</div>", unsafe_allow_html=True)
        
        if not my_leaves.empty:
            for _, row in my_leaves.iterrows():
                # 3. '연차소진' -> '연차' 로 텍스트 정리
                raw_type = str(row.get('휴가구분', '연차'))
                l_type = raw_type.replace('소진', '') 
                
                l_date = pd.to_datetime(row['연차시작일']).strftime('%Y.%m.%d')
                
                # 4. 마이너스(-) 제외하고 숫자만 표시
                l_days = str(row.get('연차기간', 0))
                
                # 5. 한 줄(Row)에 가로로 꽉 차게 배치
                st.markdown(f"""
                <div class="history-row">
                    <div class="history-left">
                        <span class="history-type">{l_type}</span>
                        <span class="history-date">{l_date}</span>
                    </div>
                    <span class="history-days">{l_days}일</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info(f"{selected_year}년도 내역이 없습니다.")
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button("로그아웃", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()
