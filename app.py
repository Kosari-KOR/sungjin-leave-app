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
# 1. 디자인 및 스타일 설정 (CSS) - 토스(Toss) 디테일 적용
# ==========================================
st.set_page_config(page_title="성진정밀 연차관리", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    /* 🚫 Streamlit 기본 UI 완벽 숨기기 */
    header { visibility: hidden !important; display: none !important; }
    [data-testid="stToolbar"] { visibility: hidden !important; display: none !important; }
    footer { visibility: hidden !important; display: none !important; }
    .viewerBadge_container__1QSob { display: none !important; }
    [data-testid="stDecoration"] { display: none !important; }

    /* 전체 여백 타이트하게 줄이기 */
    .block-container { padding-top: 1.5rem !important; padding-bottom: 1rem !important; }
    
    /* 1 & 4. 타이틀과 입사일 폰트 크기 동일하게, 여백 축소 */
    .title-group { display: flex; flex-direction: column; gap: 4px; margin-bottom: 15px; }
    .title-text { font-size: 1.25rem !important; font-weight: 700; color: #191f28; line-height: 1.4; word-break: keep-all; }
    .title-text.gray { color: #505967; font-weight: 600; }
    
    /* 5 & 6. 조회년도 글자와 박스 폰트 크기 동일하게, 박스 사이즈 축소 */
    div[data-testid="stSelectbox"] {
        display: flex; flex-direction: row; align-items: center; gap: 8px; margin-bottom: 5px;
    }
    div[data-testid="stSelectbox"] > label {
        font-size: 1.1rem !important; font-weight: 600 !important; color: #191f28 !important; margin: 0 !important;
    }
    div[data-baseweb="select"] {
        background-color: #f2f4f6 !important; border-radius: 8px !important; border: none !important;
        width: 100px !important; min-width: 100px !important; flex: none !important; /* 박스 가로 크기 대폭 축소 */
    }
    div[data-baseweb="select"] > div {
        font-size: 1.1rem !important; /* 바깥 글자와 크기 완벽 동일 */
        font-weight: 600 !important; 
        min-height: 36px !important; /* 박스 세로 크기 축소 */
        padding: 0 10px !important;
    }

    /* 섹션 헤더 (타이틀과 동일한 크기) */
    .section-header { font-size: 1.25rem !important; font-weight: 700; color: #191f28; margin: 15px 0 10px 0; }

    /* 프로그레스 바 (더 얇고 세련되게) */
    .progress-bg { background-color: #f2f4f6; border-radius: 10px; height: 12px; width: 100%; margin: 5px 0 15px 0; }
    .progress-fill { background-color: #3182f6; height: 100%; border-radius: 10px; }

    /* 2 & 3. 칼럼마다 분리된 개별 카드 레이아웃 (마진 대폭 축소) */
    .metric-wrapper { display: flex; gap: 12px; margin: 10px 0 15px 0; }
    .metric-card {
        background-color: #ffffff; 
        border: 1px solid #e5e8eb; 
        border-radius: 14px;
        padding: 12px 0; /* 위아래 마진/패딩 최소화 */
        flex: 1; text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.03); /* 토스 특유의 은은한 그림자 */
    }
    .metric-label { font-size: 0.85rem; font-weight: 600; color: #6b7684; margin-bottom: 2px; }
    .metric-value { font-size: 1.25rem; font-weight: 700; color: #191f28; }
    .metric-value.blue { color: #3182f6; }

    /* 앱 구분선 */
    .toss-divider { height: 8px; background-color: #f2f4f6; margin: 20px -20px; }
    
    /* 상세 내역 개별 카드 형태 */
    .history-card {
        background-color: #ffffff; border: 1px solid #e5e8eb; border-radius: 12px;
        padding: 14px 16px; display: flex; align-items: center; margin-bottom: 8px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.02);
    }
    .history-type { flex: 1; text-align: left; font-size: 1.05rem; font-weight: 600; color: #191f28; }
    .history-date { flex: 1; text-align: center; font-size: 0.95rem; color: #8b95a1; font-weight: 500; }
    .history-days { flex: 1; text-align: right; font-size: 1.1rem; font-weight: 700; color: #3182f6; }

    /* 토스 스타일 버튼 */
    .stButton>button { border-radius: 12px; height: 3.2rem; font-weight: 600; font-size: 1.1rem; background-color: #3182f6; color: white; border: none; }
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
    st.markdown("<div class='title-text' style='font-size: 1.5rem !important; margin-bottom: 20px;'>🏢 성진정밀 연차조회</div>", unsafe_allow_html=True)
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
    
    # 타이틀과 입사일을 동일한 폰트 크기로 나란히 배치 (마진 축소)
    join_date_fmt = pd.to_datetime(user['입사일']).strftime('%y.%m.%d')
    st.markdown(f"""
    <div class='title-group'>
        <div class='title-text'>👋 {user['성명']} {user['직책']}님, 반갑습니다.</div>
        <div class='title-text gray'>📅 입사일 : {join_date_fmt}</div>
    </div>
    """, unsafe_allow_html=True)
    
    # 조회년도 (박스 축소 및 폰트 크기 동기화 완료)
    current_year = str(datetime.now().year)
    selected_year = st.selectbox("🔍 조회년도", ["2026", "2025", "2024"], index=["2026", "2025", "2024"].index(current_year) if current_year in ["2026", "2025", "2024"] else 0)
    
    st.markdown("<div class='toss-divider'></div>", unsafe_allow_html=True)
    
    with st.spinner('로딩중...'):
        df_leave = load_excel_from_drive(f"{selected_year} 연차.xlsm", sheet_name='연차입력', skiprows=14, usecols="B:K")
    
    if df_leave is not None:
        df_leave['사원번호'] = df_leave['사원번호'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(4)
        my_leaves = df_leave[df_leave['사원번호'] == str(user['사번']).zfill(4)]
        used_leave = pd.to_numeric(my_leaves['연차기간'], errors='coerce').sum()
        total_leave = calculate_annual_leave(user['입사일'], selected_year)
        remain_leave = max(total_leave - used_leave, 0)
        
        # 섹션 타이틀
        st.markdown("<div class='section-header'>📊 연차 사용 현황</div>", unsafe_allow_html=True)
        
        progress_percent = min((used_leave / total_leave) * 100, 100) if total_leave > 0 else 0
        st.markdown(f"""
        <div class="progress-bg"><div class="progress-fill" style="width: {progress_percent}%;"></div></div>
        """, unsafe_allow_html=True)
        
        # [핵심] 3개의 칼럼을 각각 완전히 분리된 하얀색 카드로 구현
        st.markdown(f"""
        <div class="metric-wrapper">
            <div class="metric-card">
                <div class="metric-label">총 연차</div>
                <div class="metric-value">{total_leave}<span style="font-size:1.05rem;">일</span></div>
            </div>
            <div class="metric-card">
                <div class="metric-label">사용</div>
                <div class="metric-value blue">{used_leave}<span style="font-size:1.05rem;">일</span></div>
            </div>
            <div class="metric-card">
                <div class="metric-label">잔여</div>
                <div class="metric-value">{remain_leave}<span style="font-size:1.05rem;">일</span></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<div class='toss-divider'></div>", unsafe_allow_html=True)
        
        st.markdown(f"<div class='section-header'>📂 {selected_year[2:]}년 연차 내역</div>", unsafe_allow_html=True)
        
        if not my_leaves.empty:
            for _, row in my_leaves.iterrows():
                raw_type = str(row.get('휴가구분', '연차'))
                l_type = raw_type.replace('소진', '') 
                l_date = pd.to_datetime(row['연차시작일']).strftime('%Y.%m.%d')
                try:
                    l_days_num = abs(float(row.get('연차기간', 0)))
                    l_days = f"{int(l_days_num)}" if l_days_num.is_integer() else f"{l_days_num}"
                except:
                    l_days = "0"
                
                # [핵심] 상세 내역도 각각 분리된 개별 카드 형태로 구현
                st.markdown(f"""
                <div class="history-card">
                    <span class="history-type">{l_type}</span>
                    <span class="history-date">{l_date}</span>
                    <span class="history-days">{l_days}일</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("<div style='text-align:center; padding:20px; color:#8b95a1; font-size:1rem;'>내역이 없습니다.</div>", unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("로그아웃", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()
