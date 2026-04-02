import streamlit as st
import pandas as pd
import json
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from datetime import datetime
import math

# ==========================================
# 1. 디자인 및 스타일 설정 (완벽했던 Toss 스타일 복구)
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

    div[data-testid="stSelectbox"] { background-color: #ffffff; border-radius: 20px; padding: 12px 20px; margin-bottom: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.02); display: flex; flex-direction: row; align-items: center; justify-content: space-between; }
    div[data-testid="stSelectbox"] > label { font-size: 1.1rem !important; font-weight: 700 !important; color: #191f28 !important; margin: 0 !important; }
    div[data-baseweb="select"] { background-color: #f2f4f6 !important; border-radius: 10px !important; border: none !important; width: 130px !important; min-width: 130px !important; flex: none !important; }
    div[data-baseweb="select"] > div { font-size: 1.1rem !important; font-weight: 700 !important; color: #191f28 !important; min-height: 40px !important; padding: 0 12px !important; }

    .progress-bg { background-color: #f2f4f6; border-radius: 10px; height: 14px; width: 100%; margin: 5px 0 20px 0; }
    .progress-fill { background-color: #3182f6; height: 100%; border-radius: 10px; }

    /* 💡 디자인 깨짐의 원인이었던 파이썬 컬럼 삭제, 다시 완벽한 HTML 카드로 복구 */
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
    button[kind="secondary"] { background-color: transparent !important; color: #8b95a1 !important; border: none !important; box-shadow: none !important; font-size: 0.9rem !important; font-weight: 600 !important; text-decoration: underline; margin-top: 15px;}
    
    /* 팝업 안에 들어갈 텍스트 인풋 스타일 (더하기 빼기 버튼 없음) */
    div[data-testid="stPopover"] button { border-radius: 10px; font-size: 0.9rem; font-weight: 600; height: auto; padding: 5px 10px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 구글 드라이브 연결 및 저장 (HttpError 원천 차단)
# ==========================================
@st.cache_resource
def get_drive_service_v2():
    key_dict = json.loads(st.secrets["GCP_KEY"])
    creds = service_account.Credentials.from_service_account_info(
        key_dict, scopes=['https://www.googleapis.com/auth/drive']
    )
    return build('drive', 'v3', credentials=creds)

@st.cache_data(ttl=60, show_spinner="로딩중...") 
def load_file_from_drive(file_name, file_type='excel', sheet_name=None, skiprows=0):
    try:
        service = get_drive_service_v2()
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
        
        if file_type == 'excel':
            df = pd.read_excel(fh, sheet_name=sheet_name, skiprows=skiprows, engine='openpyxl')
        else:
            df = pd.read_csv(fh)
        df.columns = df.columns.astype(str).str.replace(r'\s+', '', regex=True) 
        return df
    except:
        return None

# 💡 에러 원인 제거: NAS 폴더에 억지로 넣지 않고, 로봇의 전용 공간에 저장하여 권한 충돌 방지!
def save_manual_leave(emp_id, year, absolute_total):
    service = get_drive_service_v2()
    file_name = "manual_leave_db.csv"
    
    results = service.files().list(q=f"name='{file_name}' and trashed=false").execute()
    items = results.get('files', [])
    
    if items:
        df = load_file_from_drive(file_name, file_type='csv')
    else:
        df = pd.DataFrame(columns=['사번', '연도', '총연차'])

    df['사번'] = df['사번'].astype(str).str.zfill(4)
    mask = (df['사번'] == str(emp_id).zfill(4)) & (df['연도'] == int(year))
    
    if not df[mask].empty:
        df.loc[mask, '총연차'] = absolute_total
    else:
        new_row = pd.DataFrame([{'사번': str(emp_id).zfill(4), '연도': int(year), '총연차': absolute_total}])
        df = pd.concat([df, new_row], ignore_index=True)
    
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    media = MediaIoBaseUpload(io.BytesIO(csv_buffer.getvalue().encode()), mimetype='text/csv')
    
    if items:
        service.files().update(fileId=items[0]['id'], media_body=media).execute()
    else:
        file_metadata = {'name': file_name, 'mimeType': 'text/csv'}
        service.files().create(body=file_metadata, media_body=media).execute()
    
    st.cache_data.clear()

# ==========================================
# 3. 노동법 개정 반영된 연차 계산 로직
# ==========================================
def calculate_annual_leave(join_date_str, target_year):
    join_date = pd.to_datetime(join_date_str)
    target_year = int(target_year)
    join_year = join_date.year
    years_employed = target_year - join_year
    
    is_pre_2017_law = join_date < datetime(2017, 5, 30)
    
    if years_employed < 1: return 0.0
    if years_employed == 1:
        days_in_join_year = (datetime(join_year, 12, 31) - join_date).days + 1
        return round(15 * (days_in_join_year / 365.0), 1)
        
    if years_employed == 2 and is_pre_2017_law: base_leave = 15
    else: base_leave = 15
        
    bonus_leave = math.floor((years_employed - 1) / 2)
    return min(base_leave + bonus_leave, 25.0)

# ==========================================
# 4. 화면 렌더링 및 앱 메인 로직
# ==========================================
def render_user_dashboard(user_row, selected_year, is_admin=False):
    df_leave = load_file_from_drive(f"{selected_year} 연차.xlsm", 'excel', '연차입력', 14)
    df_manual = load_file_from_drive("manual_leave_db.csv", 'csv')
    
    if df_leave is not None:
        df_leave['사원번호'] = df_leave['사원번호'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(4)
        my_leaves = df_leave[df_leave['사원번호'] == str(user_row['사번']).zfill(4)]
        used_days = pd.to_numeric(my_leaves['연차기간'], errors='coerce').sum()
        
        auto_days = calculate_annual_leave(user_row['입사일'], selected_year)
        total_days = auto_days
        
        if df_manual is not None:
            df_manual['사번'] = df_manual['사번'].astype(str).str.zfill(4)
            match = df_manual[(df_manual['사번'] == str(user_row['사번']).zfill(4)) & (df_manual['연도'] == int(selected_year))]
            if not match.empty:
                total_days = float(match.iloc[0]['총연차']) 
        
        remain_days = max(total_days - used_days, 0)
        progress = min((used_days / total_days) * 100, 100) if total_days > 0 else 0
        
        # 💡 토스 카드 시작
        st.markdown("<div class='toss-card' style='margin-bottom: 16px;'>", unsafe_allow_html=True)
        
        # 💡 관리자용 팝업(Popover) 버튼 삽입 (디자인 깨짐 없이 자연스럽게 배치)
        if is_admin:
            c1, c2 = st.columns([4, 1])
            with c1:
                st.markdown("<div class='section-header' style='margin-bottom:0;'>📊 연차 사용 현황</div>", unsafe_allow_html=True)
            with c2:
                # 팝업 생성
                with st.popover("⚙️ 수정"):
                    st.markdown("**총 연차 직접 수정**")
                    st.caption(f"시스템 자동 계산: {auto_days}일")
                    
                    # 💡 더하기 빼기(+- 버튼)가 없는 텍스트 입력창 사용!
                    new_val_str = st.text_input("새로운 값 입력", value=str(total_days), label_visibility="collapsed")
                    
                    if st.button("저장", type="primary", use_container_width=True):
                        try:
                            # 텍스트로 받은 '17.5'를 컴퓨터가 숫자로 변환 후 에러 없이 완벽 저장
                            save_manual_leave(user_row['사번'], selected_year, float(new_val_str))
                            st.rerun()
                        except ValueError:
                            st.error("숫자만 입력해 주세요!")
        else:
            st.markdown("<div class='section-header'>📊 연차 사용 현황</div>", unsafe_allow_html=True)
            
        # 💡 이전의 완벽했던 3등분 HTML 카드 디자인 그대로 복구
        st.markdown(f"""
        <div class="progress-bg"><div class="progress-fill" style="width: {progress}%;"></div></div>
        <div class="metric-wrapper">
            <div class="metric-card"><div class="metric-label">총 연차</div><div class="metric-value">{total_days}<span style="font-size:1.0rem;">일</span></div></div>
            <div class="metric-card"><div class="metric-label">사용</div><div class="metric-value blue">{used_days}<span style="font-size:1.0rem;">일</span></div></div>
            <div class="metric-card"><div class="metric-label">잔여</div><div class="metric-value">{remain_days}<span style="font-size:1.0rem;">일</span></div></div>
        </div>
        </div>
        """, unsafe_allow_html=True)
        
        # 내역 카드
        html_history = f"<div class='toss-card'><div class='section-header'>📂 {selected_year[2:]}년 연차 내역</div>"
        if not my_leaves.empty:
            for _, row in my_leaves.iterrows():
                l_type = str(row.get('휴가구분', '연차')).replace('소진', '')
                l_date = pd.to_datetime(row['연차시작일']).strftime('%Y.%m.%d')
                l_days = abs(float(row.get('연차기간', 0)))
                html_history += f"<div class='history-row'><span class='history-type'>{l_type}</span><span class='history-date'>{l_date}</span><span class='history-days'>{l_days}일</span></div>"
        else:
            html_history += "<div style='text-align:center; padding:20px; color:#8b95a1; font-size:1rem;'>내역이 없습니다.</div>"
        html_history += "</div>"
        st.markdown(html_history, unsafe_allow_html=True)

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_info = None
    st.session_state.is_admin = False

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
                else: st.error("정보가 없거나 퇴사자입니다.")

else:
    if st.session_state.is_admin:
        st.markdown("<div class='title-text' style='color:#3182f6; margin-bottom:15px;'>👑 관리자 모드</div>", unsafe_allow_html=True)
        df_emp = load_file_from_drive('1. 성진정밀_직원목록.xlsm', 'excel', '사원정보', 8)
        if df_emp is not None:
            active_emps = df_emp[pd.isna(df_emp['퇴사일'])].copy()
            emp_list = (active_emps['성명'] + " (" + active_emps['사번'].astype(str).str.zfill(4) + ")").tolist()
            
            selected_emp_name = st.selectbox("조회할 직원 선택", emp_list)
            selected_user = active_emps.iloc[emp_list.index(selected_emp_name)]
            selected_year = st.selectbox("조회 연도", ["2026", "2025", "2024"])
            
            render_user_dashboard(selected_user, selected_year, is_admin=True)

    else:
        user = st.session_state.user_info
        st.markdown(f"<div class='toss-card'><div class='title-text'>👋 {user['성명']} {user['직책']}님,<br>반갑습니다.</div><div class='title-text gray'>📅 입사일 : {pd.to_datetime(user['입사일']).strftime('%y.%m.%d')}</div></div>", unsafe_allow_html=True)
        selected_year = st.selectbox("🔍 조회년도", ["2026", "2025", "2024"])
        render_user_dashboard(user, selected_year, is_admin=False)
    
    if st.button("로그아웃", type="secondary", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.is_admin = False
        st.rerun()
