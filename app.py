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
# 1. 디자인 및 스타일 설정 (CSS) - 토스(Toss) 스타일
# ==========================================
st.set_page_config(page_title="성진정밀 연차관리", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    /* 전체 상단 여백 확 줄이기 */
    .block-container { padding-top: 1.5rem !important; padding-bottom: 1rem !important; }
    
    /* 1 & 4. 메인 타이틀 및 섹션 헤더 크기 동일하게 맞춤 (초대형) */
    .main-title, .section-header { 
        font-size: 2.2rem !important; 
        font-weight: 800; 
        color: #191f28; /* 토스 블랙 */
        margin-top: -10px; 
        margin-bottom: 5px; 
        line-height: 1.3; 
        letter-spacing: -0.5px;
        word-break: keep-all;
    }
    .section-header { margin-top: 10px; margin-bottom: 15px; } /* 섹션 헤더 여백 조정 */
    
    /* 입사일 스타일 */
    .join-date-box { font-size: 1.2rem; color: #505967; margin-bottom: 10px; font-weight: 600; }
    
    /* 2 & 3. 조회년도 텍스트와 박스를 무조건 한 줄로 (Flexbox) & 잘림 현상 해결 */
    div[data-testid="stSelectbox"] {
        display: flex;
        flex-direction: row;
        align-items: center;
        gap: 15px; /* 글자와 박스 사이 토스 앱 간격 */
        margin-bottom: 10px;
    }
    div[data-testid="stSelectbox"] > label {
        font-size: 1.4rem !important;
        font-weight: 800 !important;
        color: #191f28 !important;
        min-height: 0 !important;
        margin-bottom: 0 !important;
    }
    div[data-baseweb="select"] {
        background-color: #f2f4f6 !important; /* 토스 그레이 */
        border-radius: 12px !important;
        border: none !important;
    }
    /* 박스 내부 글자 크기 및 잘림 방지용 높이 확보 */
    div[data-baseweb="select"] > div {
        font-size: 1.4rem !important;
        font-weight: 700 !important;
        min-height: 48px !important; 
        padding: 5px 12px !important;
    }

    /* 6. 칼럼 간격 축소 및 토스 카드 느낌 (Metric) */
    .metric-container {
        display: flex;
        justify-content: space-between;
        background-color: #f2f4f6; 
        border-radius: 16px;
        padding: 24px 15px; /* 위아래 여백을 늘려 카드 느낌 강조 */
        margin: 5px 0;
    }
    .metric-box { text-align: center; flex: 1; }
    .metric-label { font-size: 1.0rem; font-weight: 700; color: #6b7684; margin-bottom: 6px; }
    .metric-value { font-size: 1.6rem; font-weight: 800; color: #191f28; }
    .metric-unit { font-size: 1.2rem; font-weight: 600; margin-left: 2px; }

    /* 프로그레스 바 */
    .progress-bg { background-color: #f2f4f6; border-radius: 20px; height: 24px; width: 100%; margin: 15px 0 25px 0; }
    .progress-fill { background-color: #3182f6; height: 100%; border-radius: 20px; } /* 토스 블루 */
    
    /* 앱 구분선 (얇은 실선 대신 두꺼운 회색 여백) */
    .toss-divider { height: 12px; background-color: #f2f4f6; margin: 25px -20px; }
    
    /* 5. 상세 내역 한 줄 & 날짜 가운데 정렬 */
    .history-row { 
        display: flex; 
        align-items: center; 
        border-bottom: 1px solid #f2f4f6; 
        padding: 16px 0; 
    }
    .history-type { flex: 1; text-align: left; font-size: 1.2rem; font-weight: 800; color: #191f28; }
    .history-date { flex: 1; text-align: center; font-size: 1.1rem; color: #8b95a1; font-weight: 600; } /* 무조건 중앙 */
    .history-days { flex: 1; text-align: right; font-size: 1.3rem; font-weight: 800; color: #3182f6; }

    /* 토스 스타일 둥근 버튼 */
    .stButton>button { border-radius: 14px; height: 3.5rem; font-weight: 700; font-size: 1.2rem; background-color: #3182f6; color: white; border: none; }
    .stButton>button:hover { background-color: #1b64da; color: white; }
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
    
    # 1. 초대형 타이틀 (마진 최소화)
    st.markdown(f"<div class='main-title'>👋 {user['성명']} {user['직책']}님,<br>반갑습니다.</div>", unsafe_allow_html=True)
    
    # 3. 입사일
    join_date_fmt = pd.to_datetime(user['입사일']).strftime('%y.%m.%d')
    st.markdown(f"<div class='join-date-box'>📅 입사일 : {join_date_fmt}</div>", unsafe_allow_html=True)
    
    # 2 & 3. 텍스트와 박스 한 줄 배치 (CSS Flexbox 적용됨) + 크기 통일 및 잘림 해결
    current_year = str(datetime.now().year)
    selected_year = st.selectbox("🔍 조회년도", ["2026", "2025", "2024"], index=["2026", "2025", "2024"].index(current_year) if current_year in ["2026", "2025", "2024"] else 0)
    
    # 두꺼운 앱 스타일 여백선
    st.markdown("<div class='toss-divider'></div>", unsafe_allow_html=True)
    
    with st.spinner('로딩중...'):
        df_leave = load_excel_from_drive(f"{selected_year} 연차.xlsm", sheet_name='연차입력', skiprows=14, usecols="B:K")
    
    if df_leave is not None:
        df_leave['사원번호'] = df_leave['사원번호'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(4)
        my_leaves = df_leave[df_leave['사원번호'] == str(user['사번']).zfill(4)]
        used_leave = pd.to_numeric(my_leaves['연차기간'], errors='coerce').sum()
        total_leave = calculate_annual_leave(user['입사일'], selected_year)
        remain_leave = max(total_leave - used_leave, 0)
        
        # 4. 섹션 타이틀 크기를 메인 타이틀과 동일하게 (2.2rem)
        st.markdown("<div class='section-header'>📊 연차 사용 현황</div>", unsafe_allow_html=True)
        
        progress_percent = min((used_leave / total_leave) * 100, 100) if total_leave > 0 else 0
        st.markdown(f"""
        <div class="progress-bg"><div class="progress-fill" style="width: {progress_percent}%;"></div></div>
        """, unsafe_allow_html=True)
        
        # 6. 토스 앱 스타일의 타이트한 간격과 큰 글자 박스
        st.markdown(f"""
        <div class="metric-container">
            <div class="metric-box">
                <div class="metric-label">총 연차</div>
                <div class="metric-value">{total_leave}<span class="metric-unit">일</span></div>
            </div>
            <div class="metric-box" style="border-left: 1px solid #e5e8eb; border-right: 1px solid #e5e8eb;">
                <div class="metric-label">사용</div>
                <div class="metric-value" style="color:#3182f6;">{used_leave}<span class="metric-unit">일</span></div>
            </div>
            <div class="metric-box">
                <div class="metric-label">잔여</div>
                <div class="metric-value" style="color:#191f28;">{remain_leave}<span class="metric-unit">일</span></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<div class='toss-divider'></div>", unsafe_allow_html=True)
        
        # 4. 섹션 타이틀 크기 동일
        st.markdown(f"<div class='section-header'>📂 {selected_year[2:]}년 연차 내역</div>", unsafe_allow_html=True)
        
        if not my_leaves.empty:
            for _, row in my_leaves.iterrows():
                # 연차소진 -> 연차 변환
                raw_type = str(row.get('휴가구분', '연차'))
                l_type = raw_type.replace('소진', '') 
                
                l_date = pd.to_datetime(row['연차시작일']).strftime('%Y.%m.%d')
                
                # 7. 마이너스 기호 원천 제거 (절대값) 및 "일" 표기
                try:
                    l_days_num = abs(float(row.get('연차기간', 0)))
                    # 소수점이 .0으로 끝나면 정수로 표시, 아니면 그대로 표시
                    l_days = f"{int(l_days_num)}" if l_days_num.is_integer() else f"{l_days_num}"
                except:
                    l_days = "0"
                
                # 5. 한 줄 배치 & 날짜 완벽한 가운데 정렬 (Flexbox)
                st.markdown(f"""
                <div class="history-row">
                    <span class="history-type">{l_type}</span>
                    <span class="history-date">{l_date}</span>
                    <span class="history-days">{l_days}일</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("<div style='text-align:center; padding:30px; color:#8b95a1; font-size:1.1rem;'>내역이 없습니다.</div>", unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("로그아웃", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()
