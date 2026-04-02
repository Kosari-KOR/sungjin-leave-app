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
# 1. 디자인 및 스타일 설정 (Toss Style)
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
    .admin-card { background-color: #f0f6ff; border: 1px solid #3182f6; } /* 관리자용 특수 카드 배경 */

    .title-text { font-size: 1.3rem !important; font-weight: 800; color: #191f28; line-height: 1.4; word-break: keep-all; }
    .title-text.gray { color: #505967; font-weight: 600; font-size: 1.1rem !important; margin-top: 6px; }
    .section-header { font-size: 1.25rem !important; font-weight: 700; color: #191f28; margin-bottom: 15px; }

    div[data-testid="stSelectbox"] { background-color: #ffffff; border-radius: 20px; padding: 16px 20px; margin-bottom: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.02); display: flex; flex-direction: row; align-items: center; justify-content: space-between; }
    div[data-testid="stSelectbox"] > label { font-size: 1.1rem !important; font-weight: 700 !important; color: #191f28 !important; margin: 0 !important; }
    div[data-baseweb="select"] { background-color: #f2f4f6 !important; border-radius: 10px !important; border: none !important; width: 130px !important; min-width: 130px !important; flex: none !important; }
    div[data-baseweb="select"] > div { font-size: 1.1rem !important; font-weight: 700 !important; color: #191f28 !important; min-height: 40px !important; padding: 0 12px !important; }

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
    button[kind="secondary"] { background-color: transparent !important; color: #8b95a1 !important; border: none !important; box-shadow: none !important; font-size: 0.9rem !important; font-weight: 600 !important; padding: 0 !important; height: auto !important; margin-top: 10px; text-decoration: underline; }
    button[kind="secondary"]:hover { color: #505967 !important; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 구글 드라이브 연결 (스피너 최적화 완료)
# ==========================================
@st.cache_resource
def get_drive_service():
    key_dict = json.loads(st.secrets["GCP_KEY"])
    creds = service_account.Credentials.from_service_account_info(key_dict, scopes=['https://www.googleapis.com/auth/drive.readonly'])
    return build('drive', 'v3', credentials=creds)

# 데이터가 없을 때만 스피너가 돌도록 show_spinner 설정
@st.cache_data(ttl=300, show_spinner="데이터를 불러오는 중입니다...") 
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
# 3. 화면 UI 그리는 함수 (재사용 가능하도록 묶음)
# ==========================================
def render_dashboard(user_row, selected_year):
    df_leave = load_excel_from_drive(f"{selected_year} 연차.xlsm", '연차입력', 14, "B:K")
    
    if df_leave is not None:
        df_leave['사원번호'] = df_leave['사원번호'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(4)
        my_leaves = df_leave[df_leave['사원번호'] == str(user_row['사번']).zfill(4)]
        used_leave = pd.to_numeric(my_leaves['연차기간'], errors='coerce').sum()
        total_leave = calculate_annual_leave(user_row['입사일'], selected_year)
        remain_leave = max(total_leave - used_leave, 0)
        
        progress_percent = min((used_leave / total_leave) * 100, 100) if total_leave > 0 else 0
        
        st.markdown(f"""
<div class="toss-card">
    <div class='section-header'>📊 연차 사용 현황</div>
    <div class="progress-bg"><div class="progress-fill" style="width: {progress_percent}%;"></div></div>
    <div class="metric-wrapper">
        <div class="metric-card"><div class="metric-label">총 연차</div><div class="metric-value">{total_leave}<span style="font-size:1.0rem;">일</span></div></div>
        <div class="metric-card"><div class="metric-label">사용</div><div class="metric-value blue">{used_leave}<span style="font-size:1.0rem;">일</span></div></div>
        <div class="metric-card"><div class="metric-label">잔여</div><div class="metric-value">{remain_leave}<span style="font-size:1.0rem;">일</span></div></div>
    </div>
</div>
""", unsafe_allow_html=True)
        
        html_history = f"<div class='toss-card'><div class='section-header'>📂 {selected_year[2:]}년 연차 내역</div>"
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
                html_history += f"<div class='history-row'><span class='history-type'>{l_type}</span><span class='history-date'>{l_date}</span><span class='history-days'>{l_days}일</span></div>"
        else:
            html_history += "<div style='text-align:center; padding:20px; color:#8b95a1; font-size:1rem;'>내역이 없습니다.</div>"
        html_history += "</div>"
        st.markdown(html_history, unsafe_allow_html=True)
    else:
        st.error(f"{selected_year}년도 연차 파일이 구글 드라이브에 없습니다.")

# ==========================================
# 4. 앱 로직 시작
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_info = None
    st.session_state.is_admin = False

# [로그인 화면]
if not st.session_state.logged_in:
    st.markdown("<div class='title-text' style='font-size: 1.6rem !important; margin-bottom: 25px; text-align: center;'>🏢 성진정밀 연차조회</div>", unsafe_allow_html=True)
    
    user_name = st.text_input("👤 이름", placeholder="성함을 입력하세요")
    # 비밀번호 타입 해제 (입력한 사번이 그대로 보임)
    user_id = st.text_input("🔑 사번", placeholder="사번 4자리를 입력하세요")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("로그인", type="primary", use_container_width=True):
        # 👑 관리자 로그인 패스워드 설정
        if user_name == "관리자" and str(user_id) == "7777":
            st.session_state.logged_in = True
            st.session_state.is_admin = True
            st.rerun()
        else:
            # 일반 직원 로그인 로직 (스피너 제거, 캐시 함수가 알아서 스피너 처리)
            df_emp = load_excel_from_drive('1. 성진정밀_직원목록.xlsm', '사원정보', 8, "B:R")
            if df_emp is not None:
                df_emp['사번'] = df_emp['사번'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(4)
                user_match = df_emp[(df_emp['성명'] == user_name) & (df_emp['사번'] == str(user_id).zfill(4))]
                
                if not user_match.empty:
                    if pd.isna(user_match.iloc[0]['퇴사일']):
                        st.session_state.logged_in = True
                        st.session_state.is_admin = False
                        st.session_state.user_info = user_match.iloc[0]
                        st.rerun()
                    else:
                        st.error("퇴사 처리된 계정입니다.")
                else:
                    st.error("이름 또는 사번이 일치하지 않습니다.")
            else:
                st.error("직원 목록 데이터를 불러올 수 없습니다.")

# [관리자 화면]
elif getattr(st.session_state, 'is_admin', False):
    st.markdown("""
    <div class="toss-card admin-card">
        <div class='title-text' style='color:#3182f6;'>👑 관리자 모드</div>
        <div class='title-text gray'>전체 직원의 연차 내역을 조회합니다.</div>
    </div>
    """, unsafe_allow_html=True)
    
    df_emp = load_excel_from_drive('1. 성진정밀_직원목록.xlsm', '사원정보', 8, "B:R")
    
    if df_emp is not None:
        # 퇴사일이 비어있는(NaN) 실제 재직자만 추출
        active_emps = df_emp[pd.isna(df_emp['퇴사일'])].copy()
        
        # 관리자가 조회할 직원 이름 리스트 생성 (동명이인 방지를 위해 사번 표기)
        emp_options = active_emps['성명'] + " (" + active_emps['직책'].fillna('') + ")"
        
        st.markdown("<div style='font-size:1.1rem; font-weight:700; margin-bottom:5px; color:#191f28;'>👤 직원 선택</div>", unsafe_allow_html=True)
        selected_option = st.selectbox("직원 선택", emp_options.tolist(), label_visibility="collapsed")
        
        # 선택한 직원의 데이터 한 줄을 빼옴
        selected_index = emp_options.tolist().index(selected_option)
        selected_user = active_emps.iloc[selected_index]
        
        st.markdown("<div class='toss-divider'></div>", unsafe_allow_html=True)
        
        # 입사일 및 연도 선택 바
        join_date_fmt = pd.to_datetime(selected_user['입사일']).strftime('%y.%m.%d')
        st.markdown(f"<div class='title-text gray' style='margin-bottom: 10px; padding-left:5px;'>📅 입사일 : {join_date_fmt}</div>", unsafe_allow_html=True)
        
        current_year = str(datetime.now().year)
        selected_year = st.selectbox("🔍 조회년도", ["2026", "2025", "2024"], index=["2026", "2025", "2024"].index(current_year) if current_year in ["2026", "2025", "2024"] else 0)
        
        # 💡 일반 직원과 똑같은 UI 그리기 함수 호출!
        render_dashboard(selected_user, selected_year)
        
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("로그아웃", type="secondary", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.is_admin = False
        st.rerun()

# [일반 직원 메인 화면]
else:
    user = st.session_state.user_info
    
    join_date_fmt = pd.to_datetime(user['입사일']).strftime('%y.%m.%d')
    st.markdown(f"""
<div class="toss-card">
    <div class='title-text'>👋 {user['성명']} {user['직책']}님,<br>반갑습니다.</div>
    <div class='title-text gray'>📅 입사일 : {join_date_fmt}</div>
</div>
""", unsafe_allow_html=True)
    
    current_year = str(datetime.now().year)
    selected_year = st.selectbox("🔍 조회년도", ["2026", "2025", "2024"], index=["2026", "2025", "2024"].index(current_year) if current_year in ["2026", "2025", "2024"] else 0)
    
    # 💡 UI 그리기 함수 호출!
    render_dashboard(user, selected_year)
    
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("로그아웃", type="secondary", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()
