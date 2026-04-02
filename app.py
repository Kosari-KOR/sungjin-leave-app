# ==========================================
# 3. 화면 렌더링 로직
# ==========================================
def render_user_dashboard(user_row, selected_year):
    df_leave = load_file_from_drive(f"{selected_year} 연차.xlsm", 'excel', '연차입력', 14)
    df_total = load_file_from_drive('1. 성진정밀_직원목록.xlsm', 'excel', '연차')
    
    target_emp_id = str(user_row['사번']).replace('.0', '').zfill(4)
    used_days = 0.0

    # 1. 사용 내역 계산
    if df_leave is not None:
        df_leave['사원번호'] = df_leave['사원번호'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(4)
        my_leaves = df_leave[df_leave['사원번호'] == target_emp_id]
        used_days = pd.to_numeric(my_leaves['연차기간'], errors='coerce').sum()
    else:
        my_leaves = pd.DataFrame()

    # 2. 총 연차 계산 (엑셀의 '연차' 시트에서 가져오기)
    total_days = 0.0
    if df_total is not None and not df_total.empty:
        # 🛡️ 깐깐한 파이썬 에러 해결: iloc 대신 열(Column) 이름을 직접 추출해서 글자로 변환 후 덮어씌우기
        emp_id_col = df_total.columns[1] # 두 번째 열(B열)의 이름을 가져옴 (보통 'Unnamed: 1'로 됨)
        df_total[emp_id_col] = df_total[emp_id_col].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(4)
        
        # 내 사번과 일치하는 줄 찾기
        match_total = df_total[df_total[emp_id_col] == target_emp_id]
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
