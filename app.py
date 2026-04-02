import streamlit as st
import pandas as pd
import json
import io
import math
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# ══════════════════════════════════════════════════════════════
# 설정
# ══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="성진정밀 연차관리",
    layout="centered",
    initial_sidebar_state="collapsed"
)

ADMIN_ID = "admin"
ADMIN_PW = "admin1234"   # ← 원하는 비번으로 변경

EMP_FILE   = "1. 성진정밀_직원목록.xlsm"
LEAVE_FILE = "2026 연차.xlsm"

# ══════════════════════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════════════════════
st.markdown("""
<style>
    header, footer, [data-testid="stToolbar"],
    [data-testid="stDecoration"], .viewerBadge_container__1QSob
    { visibility: hidden !important; display: none !important; }

    .stApp { background-color: #f2f4f6; }
    .block-container { padding-top: 3rem !important; padding-bottom: 2rem !important; }

    .card {
        background: #fff; border-radius: 20px;
        padding: 22px 20px; margin-bottom: 14px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.04);
    }
    .card-title  { font-size: 1.15rem; font-weight: 800; color: #191f28; margin-bottom: 4px; }
    .card-sub    { font-size: 0.95rem; font-weight: 600; color: #6b7684; margin-top: 4px; }
    .section-hdr { font-size: 1.1rem; font-weight: 700; color: #191f28; margin-bottom: 14px; }

    /* 프로그레스 바 */
    .prog-bg   { background:#f2f4f6; border-radius:10px; height:13px; margin:6px 0 18px; }
    .prog-fill { background:#3182f6; height:100%; border-radius:10px; }

    /* 연차 3칸 */
    .metric-row { display:flex; gap:10px; margin-bottom:4px; }
    .metric-box {
        flex:1; background:#f9fafb; border-radius:12px;
        padding:13px 0; text-align:center;
    }
    .metric-lbl { font-size:0.82rem; font-weight:600; color:#6b7684; }
    .metric-val { font-size:1.25rem; font-weight:800; color:#191f28; }
    .metric-val.blue { color:#3182f6; }
    .metric-val.red  { color:#e53e3e; }

    /* 내역 행 */
    .hist-row {
        display:flex; align-items:center;
        border-bottom:1px solid #f2f4f6; padding:14px 4px;
    }
    .hist-row:last-child { border-bottom:none; }
    .hist-type { flex:1; font-size:1rem; font-weight:700; color:#191f28; }
    .hist-date { flex:1; text-align:center; font-size:0.9rem; color:#8b95a1; }
    .hist-days { flex:1; text-align:right; font-size:1rem; font-weight:800; color:#3182f6; }

    /* 관리자 테이블 */
    .adm-table { width:100%; border-collapse:collapse; font-size:0.9rem; }
    .adm-table th {
        background:#f2f4f6; padding:10px 8px;
        text-align:left; font-weight:700; color:#505967;
        border-bottom:2px solid #e5e8ec;
    }
    .adm-table td { padding:10px 8px; border-bottom:1px solid #f2f4f6; color:#191f28; }
    .adm-table tr:hover td { background:#fafbfc; }

    .badge-on  { background:#e6f4ea; color:#2d6a4f; padding:3px 10px; border-radius:20px; font-size:0.8rem; font-weight:700; }
    .badge-off { background:#f2f4f6; color:#8b95a1; padding:3px 10px; border-radius:20px; font-size:0.8rem; font-weight:700; }

    /* 버튼 */
    button[kind="primary"] {
        background:#3182f6 !important; color:#fff !important;
        border-radius:14px !important; height:3.2rem !important;
        font-weight:700 !important; font-size:1.05rem !important;
        border:none !important;
    }
    button[kind="secondary"] {
        background:transparent !important; color:#8b95a1 !important;
        border:none !important; box-shadow:none !important;
        font-size:0.88rem !important; font-weight:600 !important;
        padding:0 !important; height:auto !important;
        text-decoration:underline;
    }
    div[data-testid="stSelectbox"] {
        background:#fff; border-radius:16px;
        padding:14px 18px; margin-bottom:14px;
        box-shadow:0 2px 10px rgba(0,0,0,0.04);
    }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# Google Drive 연결
# ══════════════════════════════════════════════════════════════
@st.cache_resource
def get_drive():
    key = json.loads(st.secrets["GCP_KEY"])
    creds = service_account.Credentials.from_service_account_info(
        key, scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    return build("drive", "v3", credentials=creds)


def drive_read_excel(filename, sheet_name, skiprows=0, usecols=None):
    """구글 드라이브에서 엑셀 파일 읽기"""
    try:
        svc = get_drive()
        res = svc.files().list(
            q=f"name='{filename}' and trashed=false",
            spaces="drive", fields="files(id)"
        ).execute()
        items = res.get("files", [])
        if not items:
            return None, f"파일 '{filename}'을 드라이브에서 찾을 수 없습니다."

        fid = items[0]["id"]
        req = svc.files().get_media(fileId=fid)
        buf = io.BytesIO()
        dl = MediaIoBaseDownload(buf, req)
        done = False
        while not done:
            _, done = dl.next_chunk()
        buf.seek(0)

        df = pd.read_excel(buf, sheet_name=sheet_name,
                           skiprows=skiprows, usecols=usecols, engine="openpyxl")
        df.columns = df.columns.astype(str).str.replace(r"\s+", "", regex=True)
        return df, None
    except Exception as e:
        return None, str(e)


# ══════════════════════════════════════════════════════════════
# 데이터 로딩 (캐시 5분)
# ══════════════════════════════════════════════════════════════
@st.cache_data(ttl=300)
def load_employees():
    """직원 목록 로딩 — 현재직원 시트"""
    df, err = drive_read_excel(EMP_FILE, sheet_name="현재직원", skiprows=7, usecols="B:O")
    if df is None:
        return None, err
    # 컬럼 정리
    df = df.dropna(subset=[df.columns[0]])           # 성명 없는 행 제거
    df = df[df.iloc[:, 0].astype(str).str.strip() != "성명"]  # 헤더 중복 제거
    df.columns = [
        "성명","부서","직책","생년월일","나이","성별","연락처",
        "주소","입사일","퇴사일","재직기간","주민등록번호","비자만료일","사번"
    ]
    df["사번"] = df["사번"].astype(str).str.replace(r"\.0$","",regex=True).str.zfill(4)
    df["입사일"] = pd.to_datetime(df["입사일"], errors="coerce")
    df["퇴사일"] = pd.to_datetime(df["퇴사일"], errors="coerce")
    return df, None


@st.cache_data(ttl=300)
def load_leave_history():
    """연차 사용 내역 로딩 — 연차입력 시트"""
    df, err = drive_read_excel(LEAVE_FILE, sheet_name="연차입력", skiprows=13, usecols="B:K")
    if df is None:
        return None, err
    df = df.dropna(subset=[df.columns[0]])
    df = df[df.iloc[:, 0].astype(str).str.strip() != "사원번호"]
    df.columns = ["사원번호","부서","성명","휴가구분","직책","입사일","연차반차","연차시작일","연차종료일","연차기간"]
    df["사원번호"] = df["사원번호"].astype(str).str.replace(r"\.0$","",regex=True).str.zfill(4)
    df["연차기간"] = pd.to_numeric(df["연차기간"].astype(str).str.extract(r"([\d.]+)")[0], errors="coerce").fillna(0)
    df["연차시작일"] = pd.to_datetime(df["연차시작일"], errors="coerce")
    return df, None


@st.cache_data(ttl=300)
def load_leave_summary():
    """연차 정산 — 연차정산서(연차수당) 시트에서 총연차 가져오기"""
    df, err = drive_read_excel(LEAVE_FILE, sheet_name="연차정산서(연차수당)", skiprows=8, usecols="B:K")
    if df is None:
        return None, err
    df = df.dropna(subset=[df.columns[0]])
    df = df[df.iloc[:, 0].astype(str).str.strip() != "사원번호"]
    df.columns = ["사원번호","부서","성명","직책","입사일","월평균임금","일평균임금","연차일수","사용일수","미사용일수"]
    df["사원번호"] = df["사원번호"].astype(str).str.replace(r"\.0$","",regex=True).str.zfill(4)
    df["연차일수"] = pd.to_numeric(df["연차일수"], errors="coerce").fillna(0)
    return df, None


# ══════════════════════════════════════════════════════════════
# 세션 초기화
# ══════════════════════════════════════════════════════════════
for key, val in {
    "logged_in": False,
    "is_admin": False,
    "user_id": None,
    "user_info": None,
    "admin_edit_id": None,
    "leave_overrides": {},   # {사번: {"totalLeave": x, "usedLeave": y}}
}.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ══════════════════════════════════════════════════════════════
# 헬퍼
# ══════════════════════════════════════════════════════════════
def get_total_leave(emp_id, summary_df):
    """총 연차 — 정산 시트 우선, 없으면 0"""
    if summary_df is None:
        return 0
    row = summary_df[summary_df["사원번호"] == emp_id]
    if row.empty:
        return 0
    return float(row.iloc[0]["연차일수"])


def get_used_leave(emp_id, history_df):
    """사용 연차 — 내역 합산"""
    if history_df is None:
        return 0
    rows = history_df[history_df["사원번호"] == emp_id]
    return float(rows["연차기간"].sum())


def get_leave_values(emp_id, summary_df, history_df):
    """총연차/사용연차 반환 — 관리자 수동 수정값 우선"""
    override = st.session_state.leave_overrides.get(emp_id, {})
    total = override.get("totalLeave", get_total_leave(emp_id, summary_df))
    used  = override.get("usedLeave",  get_used_leave(emp_id, history_df))
    return float(total), float(used)


def fmt_date(dt):
    if pd.isna(dt):
        return "-"
    return pd.Timestamp(dt).strftime("%y.%m.%d")


def is_active(row):
    return pd.isna(row["퇴사일"])


# ══════════════════════════════════════════════════════════════
# 로그인 화면
# ══════════════════════════════════════════════════════════════
def page_login():
    st.markdown("<div style='text-align:center;font-size:1.5rem;font-weight:800;color:#191f28;margin-bottom:28px;'>🏢 성진정밀 연차조회</div>", unsafe_allow_html=True)

    name   = st.text_input("👤 이름",  placeholder="성함을 입력하세요")
    emp_id = st.text_input("🔑 사번",  placeholder="사번을 입력하세요")

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("로그인", type="primary", use_container_width=True):
        # 관리자 체크
        if emp_id.strip() == ADMIN_ID and name.strip() == ADMIN_PW:
            st.session_state.logged_in = True
            st.session_state.is_admin  = True
            st.rerun()
            return

        with st.spinner("확인 중..."):
            df_emp, err = load_employees()

        if df_emp is None:
            st.error(f"직원 데이터를 불러올 수 없습니다: {err}")
            return

        norm_id = str(emp_id).strip().zfill(4)
        match = df_emp[
            (df_emp["성명"].astype(str).str.strip() == name.strip()) &
            (df_emp["사번"] == norm_id)
        ]

        if match.empty:
            st.error("이름 또는 사번이 일치하지 않습니다.")
            return

        row = match.iloc[0]
        if not is_active(row):
            st.error("퇴사 처리된 계정입니다.")
            return

        st.session_state.logged_in = True
        st.session_state.is_admin  = False
        st.session_state.user_id   = norm_id
        st.session_state.user_info = row
        st.rerun()


# ══════════════════════════════════════════════════════════════
# 직원 메인 화면
# ══════════════════════════════════════════════════════════════
def page_employee():
    user    = st.session_state.user_info
    emp_id  = st.session_state.user_id

    with st.spinner("데이터 불러오는 중..."):
        hist_df, _    = load_leave_history()
        summary_df, _ = load_leave_summary()

    total, used = get_leave_values(emp_id, summary_df, hist_df)
    remain = max(total - used, 0)
    pct    = min((used / total * 100) if total > 0 else 0, 100)

    # ── 인사말 카드 ──
    st.markdown(f"""
<div class="card">
    <div class="card-title">👋 {user['성명']} {user['직책']}님, 반갑습니다.</div>
    <div class="card-sub">📅 입사일 : {fmt_date(user['입사일'])}</div>
</div>
""", unsafe_allow_html=True)

    # ── 연차 현황 카드 ──
    remain_cls = "red" if remain <= 3 else "blue"
    st.markdown(f"""
<div class="card">
    <div class="section-hdr">📊 2026년 연차 현황</div>
    <div class="prog-bg"><div class="prog-fill" style="width:{pct:.1f}%"></div></div>
    <div class="metric-row">
        <div class="metric-box">
            <div class="metric-lbl">총 연차</div>
            <div class="metric-val">{total:.1f}<span style="font-size:.9rem">일</span></div>
        </div>
        <div class="metric-box">
            <div class="metric-lbl">사용</div>
            <div class="metric-val blue">{used:.1f}<span style="font-size:.9rem">일</span></div>
        </div>
        <div class="metric-box">
            <div class="metric-lbl">잔여</div>
            <div class="metric-val {remain_cls}">{remain:.1f}<span style="font-size:.9rem">일</span></div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

    # ── 연차 내역 카드 ──
    my_hist = pd.DataFrame()
    if hist_df is not None:
        my_hist = hist_df[hist_df["사원번호"] == emp_id].sort_values("연차시작일", ascending=False)

    rows_html = ""
    if my_hist.empty:
        rows_html = "<div style='text-align:center;padding:20px;color:#8b95a1;'>사용 내역이 없습니다.</div>"
    else:
        for _, r in my_hist.iterrows():
            ltype = str(r["휴가구분"]).replace("소진","").strip()
            ldate = fmt_date(r["연차시작일"])
            ldays = r["연차기간"]
            days_str = f"{int(ldays)}" if ldays == int(ldays) else f"{ldays}"
            rows_html += f"""
<div class="hist-row">
    <span class="hist-type">{ltype}</span>
    <span class="hist-date">{ldate}</span>
    <span class="hist-days">{days_str}일</span>
</div>"""

    st.markdown(f"""
<div class="card">
    <div class="section-hdr">📂 연차 사용 내역</div>
    {rows_html}
</div>
""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("로그아웃", type="secondary", use_container_width=True):
        for k in ["logged_in","is_admin","user_id","user_info"]:
            st.session_state[k] = False if k == "logged_in" else None
        st.rerun()


# ══════════════════════════════════════════════════════════════
# 관리자 화면
# ══════════════════════════════════════════════════════════════
def page_admin():
    st.markdown("<div class='card'><div class='card-title'>🔧 관리자 페이지</div><div class='card-sub'>성진정밀 연차관리 시스템</div></div>", unsafe_allow_html=True)

    with st.spinner("데이터 불러오는 중..."):
        emp_df, err1     = load_employees()
        hist_df, err2    = load_leave_history()
        summary_df, err3 = load_leave_summary()

    if emp_df is None:
        st.error(f"직원 데이터 오류: {err1}"); return

    # 탭
    tab1, tab2 = st.tabs(["👥 직원 목록 / 연차수정", "📋 연차 내역 조회"])

    # ── 탭1: 직원 목록 + 연차 수정 ──
    with tab1:
        search = st.text_input("🔍 검색 (이름 또는 사번)", placeholder="이름 또는 사번 입력")

        active_df = emp_df[emp_df["퇴사일"].isna()].copy()
        if search.strip():
            active_df = active_df[
                active_df["성명"].str.contains(search.strip()) |
                active_df["사번"].str.contains(search.strip())
            ]

        # 직원 선택
        options = [f"{r['사번']} | {r['성명']} | {r['부서']} | {r['직책']}"
                   for _, r in active_df.iterrows()]

        if not options:
            st.info("검색 결과가 없습니다.")
            return

        selected = st.selectbox("직원 선택", options)
        sel_id   = selected.split("|")[0].strip()
        sel_row  = active_df[active_df["사번"] == sel_id].iloc[0]

        total, used = get_leave_values(sel_id, summary_df, hist_df)
        remain = max(total - used, 0)

        # 직원 정보 카드
        st.markdown(f"""
<div class="card">
    <div class="card-title">{sel_row['성명']} {sel_row['직책']}</div>
    <div class="card-sub">사번: {sel_id} &nbsp;|&nbsp; 부서: {sel_row['부서']} &nbsp;|&nbsp; 입사: {fmt_date(sel_row['입사일'])}</div>
    <div style="margin-top:14px">
    <div class="metric-row">
        <div class="metric-box"><div class="metric-lbl">총 연차</div><div class="metric-val">{total:.1f}일</div></div>
        <div class="metric-box"><div class="metric-lbl">사용</div><div class="metric-val blue">{used:.1f}일</div></div>
        <div class="metric-box"><div class="metric-lbl">잔여</div><div class="metric-val {'red' if remain<=3 else 'blue'}">{remain:.1f}일</div></div>
    </div>
    </div>
</div>
""", unsafe_allow_html=True)

        # 연차 수정
        with st.expander("✏️ 연차 수동 수정", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                new_total = st.number_input("총 연차", value=float(total), min_value=0.0, step=0.5, format="%.1f")
            with col2:
                new_used  = st.number_input("사용 연차", value=float(used),  min_value=0.0, step=0.5, format="%.1f")

            if st.button("💾 저장", type="primary", use_container_width=True):
                st.session_state.leave_overrides[sel_id] = {
                    "totalLeave": new_total,
                    "usedLeave":  new_used,
                }
                st.success(f"✅ {sel_row['성명']}님 연차 수정 완료 (총 {new_total}일 / 사용 {new_used}일 / 잔여 {new_total - new_used:.1f}일)")
                st.rerun()

        # 수정 이력 표시
        if sel_id in st.session_state.leave_overrides:
            ov = st.session_state.leave_overrides[sel_id]
            st.info(f"🖊 수동 수정값 적용 중 — 총 {ov['totalLeave']}일 / 사용 {ov['usedLeave']}일")
            if st.button("↩ 수정값 초기화 (엑셀 원본으로)", use_container_width=True):
                del st.session_state.leave_overrides[sel_id]
                st.rerun()

    # ── 탭2: 연차 내역 조회 ──
    with tab2:
        if hist_df is None:
            st.error(f"연차 내역 오류: {err2}"); return

        # 직원 선택
        active_df2 = emp_df[emp_df["퇴사일"].isna()].copy()
        opts2 = [f"{r['사번']} | {r['성명']}" for _, r in active_df2.iterrows()]
        sel2  = st.selectbox("직원 선택", opts2, key="hist_sel")
        sel_id2 = sel2.split("|")[0].strip()
        sel_name = sel2.split("|")[1].strip()

        my_hist = hist_df[hist_df["사원번호"] == sel_id2].sort_values("연차시작일", ascending=False)
        total2, used2 = get_leave_values(sel_id2, summary_df, hist_df)
        remain2 = max(total2 - used2, 0)

        # 요약
        st.markdown(f"""
<div class="card">
    <div class="section-hdr">📊 {sel_name} 연차 현황</div>
    <div class="metric-row">
        <div class="metric-box"><div class="metric-lbl">총 연차</div><div class="metric-val">{total2:.1f}일</div></div>
        <div class="metric-box"><div class="metric-lbl">사용</div><div class="metric-val blue">{used2:.1f}일</div></div>
        <div class="metric-box"><div class="metric-lbl">잔여</div><div class="metric-val {'red' if remain2<=3 else 'blue'}">{remain2:.1f}일</div></div>
    </div>
</div>
""", unsafe_allow_html=True)

        # 내역 테이블
        if my_hist.empty:
            st.info("사용 내역이 없습니다.")
        else:
            rows2 = ""
            for _, r in my_hist.iterrows():
                ltype = str(r["휴가구분"]).replace("소진","").strip()
                ldate = fmt_date(r["연차시작일"])
                ldays = r["연차기간"]
                days_str = f"{int(ldays)}" if ldays == int(ldays) else f"{ldays}"
                rows2 += f"""
<div class="hist-row">
    <span class="hist-type">{ltype}</span>
    <span class="hist-date">{ldate}</span>
    <span class="hist-days">{days_str}일</span>
</div>"""
            st.markdown(f"""
<div class="card">
    <div class="section-hdr">📂 연차 사용 내역 ({len(my_hist)}건)</div>
    {rows2}
</div>
""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("로그아웃", type="secondary", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.is_admin  = False
        st.rerun()


# ══════════════════════════════════════════════════════════════
# 라우팅
# ══════════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    page_login()
elif st.session_state.is_admin:
    page_admin()
else:
    page_employee()
