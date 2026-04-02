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
# 1. 기본 설정 및 디자인 (CSS)
# ==========================================
st.set_page_config(page_title="연차조회", layout="centered", initial_sidebar_state="collapsed")

# 스마트폰 UI를 위한 깔끔한 커스텀 디자인 적용
st.markdown("""
<style>
    /* 메인 화면 폰트 및 여백 최적화 */
    .app-title { font-size: 1.5rem; font-weight: 700; color: #222; margin-bottom: 5px; }
    .sub-text { font-size: 0.9rem; color: #666; margin-bottom: 20px; }
    
    /* 카드형 사용 내역 디자인 (1줄, 이모티콘 없음) */
    .history-item { 
        border-bottom: 1px solid #eee; 
        padding: 12px 0; 
        display: flex; 
        justify-content: space-between; 
        align-items: center;
    }
    .history-type { font-size: 1rem; font-weight: 600; color: #333; }
    .history-date { font-size: 0.85rem; color: #888; margin-top: 4px; }
    .history-days { font-size: 1rem; font-weight: 700; color: #007bff; }
    
    /* 프로그레스 바 커스텀 */
    .progress-bg { background-color: #e9ecef; border-radius: 10px; height: 12px; width: 100%; overflow: hidden; margin: 10px 0 20px 0; }
    .progress-fill { background-color: #007bff; height: 100%; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 구글 드라이브 로봇 접속 및 데이터 로드
# ==========================================
@st.cache_resource
def get_drive_service():
    key_dict = json.loads(st.secrets["GCP_KEY"])
    creds = service_account.Credentials.from_service_account_info(
        key_dict, scopes=['https://www.googleapis.com/auth/drive.readonly']
    )
    return build('drive', 'v3', credentials=creds)

@st.cache_data(ttl=60) 
def load_excel_from_drive(file_name, sheet_name, skiprows, usecols=None):
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

# ==========================================
# 3. 회계연도 기준 연차 계산 로직 (근로기준법)
# ==========================================
def calculate_annual_leave(join_date_str, target_year):
    join_date = pd.to_datetime(join_date_str)
    target_year = int(target_year)
    join_year = join_date.year
    
    years_employed = target_year - join_year
    
    # 1. 아직 입사 전인 년도 조회 시
    if years_employed < 0: return 0.0
    
    # 2. 입사 당해 연도 (1년 미만) -> 0일 (관리자가 수동으로 부여한 월차만 적용됨)
    if years_employed == 0: return 0.0
    
    # 3. 입사 다음 해 (1년 차, 회계연도 비례 계산)
    if years_employed == 1:
        days_in_join_year = (datetime(join_year, 12, 31) - join_date).days + 1
        proportional_leave = 15 * (days_in_join_year / 365.0)
        # 소수점 처리: 회사 정책에 따라 다르지만 보통 1자리까지 반올림
        return round(proportional_leave, 1)
        
    # 4. 입사 2년 차 이상 (15일 기본 + 2년마다 1일 추가, 최대 25일)
    if years_employed >= 2:
        base_leave = 15
        bonus_leave = math.floor((years_employed - 1) / 2)
        total_leave = base_leave + bonus_leave
        return min(total_leave, 25.0) # 최대 25일 제한

# ==========================================
# 4. 로그인 및 화면 구성
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_info = None

df_emp = load_excel_from_drive('1. 성진정밀_직원목록.xlsm', sheet_name='사원정보', skiprows=8, usecols="B:R")

# [로그인 화면]
if not st.session_state.logged_in:
    st.markdown("<div class='app-title'>성진정밀 연차조회</div>", unsafe_allow_html=True)
    st.markdown("<div class='sub-text'>이름과 사번을 입력해주세요.</div>", unsafe_allow_html=True)
    
    if df_emp is None:
        st.error("직원목록을 불러올 수 없습니다.")
    else:
        user_name = st.text_input("이름")
        user_id = st.text_input("사번", type="password")
        
        if st.button("로그인", use_container_width=True):
            try:
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
                    st.error("정보가 일치하지 않습니다.")
            except:
                st.error("데이터베이스 읽기 오류")

# [메인 화면]
else:
    user = st.session_state.user_info
    
    st.markdown(f"<div class='app-title'>{user['성명']} {user['직책']}님, 반갑습니다.</div>", unsafe_allow_html=True)
    
    # 상단 탭: 입사일 & 조회 년도 나란히 배치 (공간 절약)
    col1, col2 = st.columns([1, 1])
    join_date_fmt = pd.to_datetime(user['입사일']).strftime('%y.%m.%d')
    with col1:
        st.markdown(f"<div style='margin-top:10px; font-size:0.9rem; color:#666;'>입사일: {join_date_fmt}</div>", unsafe_allow_html=True)
    with col2:
        current_year = str(datetime.now().year)
        selected_year = st.selectbox("조회 연도", ["2026", "2025", "2024"], index=["2026", "2025", "2024"].index(current_year) if current_year in ["2026", "2025", "2024"] else 0, label_visibility="collapsed")
    
    st.divider()
    
    # 데이터 불러오기
    leave_file_name = f"{selected_year} 연차.xlsm"
    df_leave = load_excel_from_drive(leave_file_name, sheet_name='연차입력', skiprows=14, usecols="B:K")
    
    if df_leave is not None:
        try:
            df_leave['사원번호'] = df_leave['사원번호'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(4)
            my_leaves = df_leave[df_leave['사원번호'] == str(user['사번']).zfill(4)]
            
            # 사용 연차 합산
            used_leave = pd.to_numeric(my_leaves['연차기간'], errors='coerce').sum()
            
            # 💡 총 연차 계산 (자동 부여분 + 관리자 수동 부여분)
            auto_leave = calculate_annual_leave(user['입사일'], selected_year)
            
            # TODO: 관리자 페이지 완성 시 DB에서 1년 미만자의 수동 부여(월차) 연차를 가져올 변수
            manual_granted_leave = 0.0 
            
            total_leave = auto_leave + manual_granted_leave
            remain_leave = total_leave - used_leave
            
            # 프로그레스 바 (모바일 커스텀)
            progress_percent = min((used_leave / total_leave) * 100, 100) if total_leave > 0 else 0
            
            st.markdown("<b>연차 사용 현황</b>", unsafe_allow_html=True)
            st.markdown(f"""
            <div class="progress-bg">
                <div class="progress-fill" style="width: {progress_percent}%;"></div>
            </div>
            """, unsafe_allow_html=True)
            
            # 텍스트 정보 (깔끔한 정렬)
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"<div style='text-align:center; font-size:0.85rem; color:#666;'>총 연차<br><span style='font-size:1.2rem; font-weight:bold; color:#222;'>{total_leave}</span>일</div>", unsafe_allow_html=True)
            c2.markdown(f"<div style='text-align:center; font-size:0.85rem; color:#666;'>사용<br><span style='font-size:1.2rem; font-weight:bold; color:#007bff;'>{used_leave}</span>일</div>", unsafe_allow_html=True)
            c3.markdown(f"<div style='text-align:center; font-size:0.85rem; color:#666;'>잔여<br><span style='font-size:1.2rem; font-weight:bold; color:#28a745;'>{remain_leave}</span>일</div>", unsafe_allow_html=True)
            
            # 1년 미만 분리 표기 안내 (해당자만)
            if manual_granted_leave > 0:
                st.caption(f"* 포함된 관리자 수동 부여(월차): {manual_granted_leave}일")
            
            st.divider()
            
            # 하단 상세 내역 (카드형 1줄 리스트)
            st.markdown("<b>상세 내역</b>", unsafe_allow_html=True)
            if not my_leaves.empty:
                for _, row in my_leaves.iterrows():
                    l_type = row.get('휴가구분', '연차')
                    l_date = pd.to_datetime(row['연차시작일']).strftime('%y.%m.%d')
                    l_days = row.get('연차기간', 0)
                    
                    # 깔끔한 1줄 디자인 출력
                    st.markdown(f"""
                    <div class="history-item">
                        <div>
                            <div class="history-type">{l_type}</div>
                            <div class="history-date">{l_date}</div>
                        </div>
                        <div class="history-days">-{l_days}일</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown("<div style='text-align:center; color:#888; padding: 20px 0; font-size:0.9rem;'>사용 내역이 없습니다.</div>", unsafe_allow_html=True)
                
        except Exception as e:
            st.error("연차 데이터 처리 중 오류 발생")
    else:
        st.warning("데이터가 아직 업로드되지 않았습니다.")
    
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("로그아웃", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()
