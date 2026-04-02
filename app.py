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
# 1. 디자인 및 스타일 설정 (Toss 앱 감성)
# ==========================================
st.set_page_config(page_title="성진정밀 연차관리", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    header { visibility: hidden !important; display: none !important; }
    [data-testid="stToolbar"] { visibility: hidden !important; display: none !important; }
    footer { visibility: hidden !important; display: none !important; }
    .viewerBadge_container__1QSob { display: none !important; }
    [data-testid="stDecoration"] { display: none !important; }

    .stApp { background-color: #f2f4f6; }
    .block-container { padding-top: 3.5rem !important; padding-bottom: 2rem !important; }
    
    .toss-card { background-color: #ffffff; border-radius: 20px; padding: 24px 20px; margin-bottom: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.02); }

    .title-text { font-size: 1.3rem !important; font-weight: 800; color: #191f28; line-height: 1.4; word-break: keep-all; }
    .title-text.gray { color: #505967; font-weight: 600; font-size: 1.1rem !important; margin-top: 6px; }
    .section-header { font-size: 1.25rem !important; font-weight: 700; color: #191f28; margin-bottom: 15px; }

    div[data-testid="stSelectbox"] {
        background-color: #ffffff; border-radius: 20px; padding: 12px 20px; margin-bottom: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.02);
    }
    div[data-testid="stSelectbox"] > label {
        font-size: 1.1rem !important; font-weight: 700 !important; color: #191f28 !important; margin-bottom: 8px !important;
    }
    div[data-baseweb="select"] {
        background-color: #f2f4f6 !important; border-radius: 10px !important; border: none !important;
    }

    .progress-bg { background-color: #f2f4f6; border-radius: 10px; height: 14px; width: 100%; margin: 5px 0 20px 0; }
    .progress-fill { background-color: #3182f6; height: 100%; border-radius: 10px; }

    .metric-wrapper { display: flex; gap: 10px; margin-bottom: 5px; }
    .metric-card { background-color: #f9fafb; border-radius: 12px; padding: 14px 0; flex: 1; text-align: center; }
    .metric-label { font-size: 0.85rem; font-weight: 600; color: #6b7684; margin-bottom: 4px; }
    .metric-value { font-size: 1.3rem; font-weight: 800; color: #191f28; }
    .metric-value.blue { color: #3182f6; }

    .history-row { display: flex; align-items: center; border-bottom: 1px solid #f2f4f6; padding: 16px 4px; }
    .history-row:last-child { border-bottom: none; padding-bottom: 0; }
    .history-type { flex: 1; text-align: left; font-size: 1.1rem; font-weight: 700; color: #191f28; }
    .history-date { flex: 1; text-align: center; font-size: 1.0rem; color: #8b95a1; font-weight: 500; }
    .history-days { flex: 1; text-align: right; font-size: 1.15rem; font-weight: 800; color: #3182f6; }

    button[kind="primary"] { background-color: #3182f6 !important; color: white !important; border-radius: 14px !important; height: 3.5rem !important; font-weight: 700 !important; font-size: 1.15rem !important; border: none !important; }
    button[kind="secondary"] { background-color: transparent !important; color: #8b95a1 !important; border: none !important; box-shadow: none !important; font-size: 0.9rem !important; font-weight: 600 !important; text-decoration: underline; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 구글 드라이브 연결
# ==========================================
@st.cache_resource
def get_drive_service():
    key_dict = json.loads(st.secrets["GCP_KEY"])
    creds = service_account.Credentials.from_service_account_info(
        key_dict, scopes=['https://www.googleapis.com/auth/drive.readonly']
    )
    return build('drive', 'v3', credentials=creds)

@st.cache_data(ttl=60, show_spinner="데이터 불러오는 중...") 
def load_file_from_drive(file_name, file_type='excel', sheet_name=None, skiprows=0):
    try:
        service = get_drive_service()
        results = service.files().list(q=f"name='{file_name}' and trashed=false", fields='files(id, name)').execute()
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
        
        df = pd.read_excel(fh, sheet_name=sheet_name, skiprows=skiprows, engine='openpyxl')
        # 열 이름 공백 제거 (예: '2024 총연차' -> '2024총연차')
        df.columns = df.columns.astype(str).str.replace(r'\s+', '', regex=True) 
        return df
    except:
        return None

# ==========================================
# 3. 화면 렌더링 로직
# ==========================================
def render_user_dashboard(user_row, selected_year):
    # 1. 연차 사용 내역 (2026 연차.xlsm 파일 등)
    df_leave = load_file_from_drive(f"{selected_year} 연차.xlsm", 'excel', '연차입력', 14)
    
    # 2. 💡 새로 만든 '연차' 시트 불러오기 (총 연차 DB)
    df_total = load_file_from_drive('1. 성진정밀_직원목록.xlsm', 'excel', '연차')
    
    target_emp_id = str(user_row['사번']).replace('.0', '').zfill(4)
    used_days = 0.0

    # 사용 내역 계산 (내역 파일이 있을 때만)
    if df_leave is not None:
        df_leave['사원번호'] = df_leave['사원번호'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(4)
        my_leaves = df_leave[df_leave['사원번호'] == target_emp_id]
        used_days = pd.to_numeric(my_leaves['연차기간'], errors='coerce').sum()
    else:
        my_leaves = pd.DataFrame() # 파일이 없으면 빈 데이터 생성

    # 총 연차 계산 (엑셀의 '연차' 시트에서 가져오기)
    total_days = 0.0
    if df_total is not None:
        # 💡 핵심: A1, B1이 비어있어도 당황하지 않게, 무조건 2번째 열(인덱스 1, 즉 B열)을 사번으로 인식하게 만듦
        df_total.iloc[:, 1] = df_total.iloc[:, 1].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(4)
        
        # 내 사번과 일치하는 줄 찾기
        match_total = df_total[df_total.iloc[:, 1] == target_emp_id]
        excel_col_name = f"{selected_year}총연차"
        
        # 해당 연도 열이 존재하고, 값이 비어있지 않으면 가져오기
        if not match_total.empty and excel_col_name in match_total.columns:
            val = match_total.iloc[0][excel_col_name]
            if pd.notna(val):
                total_days = float(val)

    # 혹시라도 엑셀에 실수로 값을 안 적었을 때를 대비한 방어막 (자동 계산)
    if total_days == 0.0:
        total_days = calculate_annual_leave(user_row['입사일'], selected_year)

    remain_days = max(total_days - used_days, 0)
    progress = min((used_days / total_days) * 100, 100) if total_days > 0 else 0

    # 연차 카드 디자인
    st.markdown(f"""
    <div class="toss-card">
        <div class='section-header'>📊 연차 사용 현황</div>
        <div class="progress-bg"><div class="progress-fill" style="width: {progress}%;"></div></div>
        <div class="metric-wrapper">
            <div class="metric-card"><div class="metric-label">총 연차</div><div class="metric-value">{total_days}<span style="font-size:1.0rem;">일</span></div></div>
            <div class="metric-card"><div class="metric-label">사용</div><div class="metric-value blue">{used_days}<span style="font-size:1.0rem;">일</span></div></div>
            <div class="metric-card"><div class="metric-label">잔여</div><div class="metric-value">{remain_days}<span style="font-size:1.0rem;">일</span></div></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 연차 내역 리스트
    html_history = f"<div class='toss-card'><div class='section-header'>📂 {selected_year[2:]}년 연차 내역</div>"
    if not my_leaves.empty:
        for _, row in my_leaves.iterrows():
            l_type = str(row.get('휴가구분', '연차')).replace('소진', '')
            try:
                l_date = pd.to_datetime(row['연차시작일']).strftime('%Y.%m.%d')
            except:
                l_date = "날짜오류"
            l_days = abs(float(row.get('연차기간', 0)))
            html_history += f"<div class='history-row'><span class='history-type'>{l_type}</span><span class='history-date'>{l_date}</span><span class='history-days'>{l_days}일</span></div>"
    else:
        html_history += "<div style='text-align:center; padding:20px; color:#8b95a1; font-size:1rem;'>내역이 없습니다.</div>"
    html_history += "</div>"
    st.markdown(html_history, unsafe_allow_html=True)

# ==========================================
# 4. 앱 메인 로직
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_info = None
    st.session_state.is_admin = False

# 💡 현재 연도를 기준으로 선택 가능한 연도 리스트 생성 (올해까지만!)
current_year = datetime.now().year
year_options = [str(y) for y in range(current_year, 2023, -1)] # 2024년부터 올해까지만 역순으로

if not st.session_state.logged_in:
    st.markdown("<div class='title-text' style='font-size: 1.6rem !important; margin-bottom: 25px; text-align: center;'>🏢 성진정밀 연차조회</div>", unsafe_allow_html=True)
    user_name = st.text_input("👤 이름", placeholder="성함을 입력하세요")
    user_id = st.text_input("🔑 사번", placeholder="사번 4자리를 입력하세요")
    
    if st.button("로그인", type="primary", use_container_width=True):
        if user_name == "관리자" and str(user_id) == "7777":
            st.session_state.logged_in, st.session_state.is_admin = True, True
            st.rerun()
        else:
            df_emp = load_file_from_drive('1. 성진정밀_직원목록.xlsm', 'excel', '사원정보', 8)
            if df_emp is not None:
                df_emp['사번'] = df_emp['사번'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(4)
                match = df_emp[(df_emp['성명'] == user_name) & (df_emp['사번'] == str(user_id).zfill(4))]
                if not match.empty and pd.isna(match.iloc[0]['퇴사일']):
                    st.session_state.logged_in, st.session_state.user_info = True, match.iloc[0]
                    st.rerun()
                else: 
                    st.error("정보가 없거나 퇴사자입니다.")

else:
    if st.session_state.is_admin:
        st.markdown("<div class='title-text' style='color:#3182f6; margin-bottom:15px;'>👑 관리자 모드</div>", unsafe_allow_html=True)
        df_emp = load_file_from_drive('1. 성진정밀_직원목록.xlsm', 'excel', '사원정보', 8)
        if df_emp is not None:
            active_emps = df_emp[pd.isna(df_emp['퇴사일'])].copy()
            emp_list = (active_emps['성명'] + " (" + active_emps['사번'].astype(str).str.replace('.0', '').str.zfill(4) + ")").tolist()
            
            selected_emp_name = st.selectbox("조회할 직원 선택", emp_list)
            selected_user = active_emps.iloc[emp_list.index(selected_emp_name)]
            
            selected_year = st.selectbox("조회 연도", year_options) # 💡 올해까지만 나타남
            render_user_dashboard(selected_user, selected_year)

    else:
        user = st.session_state.user_info
        st.markdown(f"<div class='toss-card'><div class='title-text'>👋 {user['성명']} {user['직책']}님,<br>반갑습니다.</div><div class='title-text gray'>📅 입사일 : {pd.to_datetime(user['입사일']).strftime('%y.%m.%d')}</div></div>", unsafe_allow_html=True)
        selected_year = st.selectbox("🔍 조회년도", year_options) # 💡 올해까지만 나타남
        render_user_dashboard(user, selected_year)
    
    if st.button("로그아웃", type="secondary", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.is_admin = False
        st.rerun()
