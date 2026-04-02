import streamlit as st
import pandas as pd
import json
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# 1. 웹앱 기본 설정
st.set_page_config(page_title="성진정밀 연차관리", page_icon="🏢", layout="centered")

# 2. 구글 드라이브 로봇 접속 기능
@st.cache_resource
def get_drive_service():
    # 스트림릿 금고에서 열쇠(JSON) 꺼내기
    key_dict = json.loads(st.secrets["GCP_KEY"])
    creds = service_account.Credentials.from_service_account_info(
        key_dict, scopes=['https://www.googleapis.com/auth/drive.readonly']
    )
    return build('drive', 'v3', credentials=creds)

# 3. 엑셀 파일 다운로드 및 읽기 기능
@st.cache_data(ttl=600) # 10분마다 새로고침 (속도 향상)
def load_excel_from_drive(file_name, sheet_name, skiprows):
    service = get_drive_service()
    # 파일 이름으로 검색
    results = service.files().list(q=f"name='{file_name}' and trashed=false", spaces='drive', fields='files(id, name)').execute()
    items = results.get('files', [])
    
    if not items:
        return None # 파일이 없으면 에러 방지
    
    file_id = items[0]['id']
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    
    done = False
    while done is False:
        status, done = downloader.next_chunk()
        
    fh.seek(0)
    # 지정한 시트와 시작 줄(B9, B15 등)에 맞춰 엑셀 읽기
    return pd.read_excel(fh, sheet_name=sheet_name, skiprows=skiprows, engine='openpyxl')

# ==========================================
# 🖥️ 실제 화면 구성 시작
# ==========================================

st.title("🔐 성진정밀 연차 조회 시스템")
st.write("로봇이 구글 드라이브에서 파일을 가져오는 중입니다...")

# 데이터 불러오기 시도 (동기화된 파일명과 정확히 일치해야 함!)
try:
    # 직원 목록 불러오기 (사원정보 시트, B9부터 시작이므로 8줄 건너뜀)
    df_emp = load_excel_from_drive('1. 성진정밀_직원목록.xlsm', sheet_name='사원정보', skiprows=8)
    
    # 2024년 연차 파일 불러오기 (연차입력 시트, B15부터 시작이므로 14줄 건너뜀)
    df_leave = load_excel_from_drive('2024 연차.xlsm', sheet_name='연차입력', skiprows=14)
    
    if df_emp is not None and df_leave is not None:
        st.success("✅ 구글 드라이브 연동 완벽 성공!")
        
        st.subheader("👥 직원 데이터 미리보기 (상위 3명)")
        st.dataframe(df_emp.head(3))
        
        st.subheader("📅 2024년 연차 데이터 미리보기 (상위 3명)")
        st.dataframe(df_leave.head(3))
        
        st.info("💡 데이터 연결이 확인되었습니다! 다음 단계에서 본격적인 로그인과 막대그래프를 붙일게요.")
    else:
        st.error("⚠️ 구글 드라이브에 접속은 했지만 파일을 찾지 못했어요. 파일 이름이 정확한지 확인해주세요!")
except Exception as e:
    st.error(f"🚨 연결 에러 발생: {e}")
