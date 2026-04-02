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
    /* 🚫 Streamlit 기본 워터마크 완벽 숨기기 */
    header { visibility: hidden !important; display: none !important; }
    [data-testid="stToolbar"] { visibility: hidden !important; display: none !important; }
    footer { visibility: hidden !important; display: none !important; }
    .viewerBadge_container__1QSob { display: none !important; }
    [data-testid="stDecoration"] { display: none !important; }

    /* 1. 앱 전체 배경을 토스 회색으로 변경 & 상단 마진 대폭 추가 */
    .stApp { background-color: #f2f4f6; }
    .block-container { 
        padding-top: 3.5rem !important; /* 상단 여백 확보 */
        padding-bottom: 2rem !important; 
    }
    
    /* 2. 개별 하얀색 둥근 카드 스타일 (Toss Card) */
    .toss-card {
        background-color: #ffffff;
        border-radius: 20px;
        padding: 24px 20px;
        margin-bottom: 16px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.02); /* 부드러운 그림자 */
    }

    /* 타이틀 폰트 최적화 */
    .title-text { font-size: 1.3rem !important; font-weight: 800; color: #191f28; line-height: 1.4; word-break: keep-all; }
    .title-text.gray { color: #505967; font-weight: 600; font-size: 1.1rem !important; margin-top: 6px; }
    .section-header { font-size: 1.25rem !important; font-weight: 700; color: #191f28; margin-bottom: 15px; }

    /* 3. 조회년도 영역을 완벽한 독립된 카드로 변신 */
    div[data-testid="stSelectbox"] {
        background-color: #ffffff;
        border-radius: 20px;
        padding: 16px 20px;
        margin-bottom: 16px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.02);
        display: flex; flex-direction: row; align-items: center; justify-content: space-between;
    }
    /* 조회년도 바깥 라벨 글자 크기 */
    div[data-testid="stSelectbox"] > label {
        font-size: 1.1rem !important; font-weight: 700 !important; color: #191f28 !important; margin: 0 !important;
    }
    /* 년도 선택 박스 (잘림 현상 해결 & 글자 크기 동기화) */
    div[data-baseweb="select"] {
        background-color: #f2f4f6 !important; border-radius: 10px !important; border: none !important;
        width: 130px !important; min-width: 130px !important; flex: none !important; /* 가로폭 넓힘 */
    }
    div[data-baseweb="select"] > div {
        font-size: 1.1rem !important; /* 바깥 라벨과 크기 똑같이 맞춤 */
        font-weight: 700 !important; color: #191f28 !important;
        min-height: 40px !important; padding: 0 12px !important;
    }

    /* 프로그레스 바 */
    .progress-bg { background-color: #f2f4f6; border-radius: 10px; height: 14px; width: 100%; margin: 5px 0 20px 0; }
    .progress-fill { background-color: #3182f6; height: 100%; border-radius: 10px; }

    /* 연차 사용 현황 3등분 서브 카드 (토스 스타일 데이터 박스) */
    .metric-wrapper { display: flex; gap: 10px; margin-bottom: 5px; }
    .metric-card {
        background-color: #f9fafb; /* 흰 카드 안의 옅은 회색 박스 */
        border-radius: 12px;
        padding: 14px 0; 
        flex: 1; text-align: center;
    }
    .metric-label { font-size: 0.85rem; font-weight: 600; color: #6b7684; margin-bottom: 4px; }
    .metric-value { font-size: 1.3rem; font-weight: 800; color: #191f28; }
    .metric-value.blue { color: #3182f6; }

    /* 상세 내역 리스트 (카드 안의 리스트) */
    .history-row { 
        display: flex; align-items: center; 
        border-bottom: 1px solid #f2f4f6; padding: 16px 4px; 
    }
    .history-row:last-child { border-bottom: none; padding-bottom: 0; }
    .history-type { flex: 1; text-align: left; font-size: 1.1rem; font-weight: 700; color: #191f28; }
    .history-date { flex: 1; text-align: center; font-size: 1.0rem; color: #8b95a1; font-weight: 500; }
    .history-days { flex: 1; text-align: right; font-size: 1.15rem; font-weight: 800; color: #3182f6; }

    /* 4. 로그인 버튼 (Primary) - 파란색 유지 */
    button[kind="primary"] { 
        background-color: #3182f6 !important; color: white !important; 
        border-radius: 14px !important; height: 3.5rem !important; 
        font-weight: 700 !important; font-size: 1.15rem !important; border: none !important; 
    }
    /* 5. 로그아웃 버튼 (Secondary) - 텍스트 버튼으로 축소 변경 */
    button[kind="secondary"] { 
        background-color: transparent !important; color: #8b95a1 !important; 
        border: none !important; box-shadow: none !important; 
        font-size: 0.9rem !important; font-weight: 600 !important; 
        padding: 0 !important; height: auto !important; margin-top: 10px;
        text-decoration: underline; /* 텍스트 링크 느낌 강조 */
    }
    button[kind="secondary"]:hover { color: #505967 !important; }
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
# 3. 앱 로직 시작
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_info = None

# [로그인 화면]
if not st.session_state.logged_in:
    st.markdown("<div class='title-text' style='font-size: 1.6rem !important; margin-bottom: 25px; text-align: center;'>🏢 성진정밀 연차조회</div>", unsafe_allow_html=True)
    user_name = st.text_input("👤 이름", placeholder="성함을 입력하세요")
    user_id = st.text_input("🔑 사번", type="password", placeholder="사번 4자리를 입력하세요")
    
    st.markdown("<br>", unsafe_allow_html=True)
    # 로그인 버튼은 파란색(type="primary")
    if st.button("로그인", type="primary", use_container_width=True):
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
    
    # [1번 카드] 내 정보 (하얀색 바탕)
    join_date_fmt = pd.to_datetime(user['입사일']).strftime('%y.%m.%d')
    st.markdown(f"""
    <div class="toss-card">
        <div class='title-text'>👋 {user['성명']} {user['직책']}님,<br>반갑습니다.</div>
        <div class='title-text gray'>📅 입사일 : {join_date_fmt}</div>
    </div>
    """, unsafe_allow_html=True)
    
    # [2번 카드] 조회년도 (박스가 자체적으로 하나의 독립된 하얀색 카드처럼 보이게 CSS 세팅됨)
    current_year = str(datetime.now().year)
    selected_year = st.selectbox("🔍 조회년도", ["2026", "2025", "2024"], index=["2026", "2025", "2024"].index(current_year) if current_year in ["2026", "2025", "2024"] else 0)
    
    with st.spinner('로딩중...'):
        df_leave = load_excel_from_drive(f"{selected_year} 연차.xlsm", sheet_name='연차입력', skiprows=14, usecols="B:K")
    
    if df_leave is not None:
        df_leave['사원번호'] = df_leave['사원번호'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(4)
        my_leaves = df_leave[df_leave['사원번호'] == str(user['사번']).zfill(4)]
        used_leave = pd.to_numeric(my_leaves['연차기간'], errors='coerce').sum()
        total_leave = calculate_annual_leave(user['입사일'], selected_year)
        remain_leave = max(total_leave - used_leave, 0)
        
        # [3번 카드] 연차 사용 현황
        st.markdown(f"""
        <div class="toss-card">
            <div class='section-header'>📊 연차 사용 현황</div>
            <div class="progress-bg">
                <div class="progress-fill" style="width: {min((used_leave / total_leave) * 100, 100) if total_leave > 0 else 0}%;"></div>
            </div>
            
            <div class="metric-wrapper">
                <div class="metric-card">
                    <div class="metric-label">총 연차</div>
                    <div class="metric-value">{total_leave}<span style="font-size:1.0rem;">일</span></div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">사용</div>
                    <div class="metric-value blue">{used_leave}<span style="font-size:1.0rem;">일</span></div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">잔여</div>
                    <div class="metric-value">{remain_leave}<span style="font-size:1.0rem;">일</span></div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # [4번 카드] 상세 내역
        html_history = f"""
        <div class="toss-card">
            <div class='section-header'>📂 {selected_year[2:]}년 연차 내역</div>
        """
        
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
                
                html_history += f"""
                <div class="history-row">
                    <span class="history-type">{l_type}</span>
                    <span class="history-date">{l_date}</span>
                    <span class="history-days">{l_days}일</span>
                </div>
                """
        else:
            html_history += "<div style='text-align:center; padding:20px; color:#8b95a1; font-size:1rem;'>내역이 없습니다.</div>"
            
        html_history += "</div>"
        st.markdown(html_history, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    # 로그아웃 버튼은 텍스트(type="secondary")
    if st.button("로그아웃", type="secondary", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()
