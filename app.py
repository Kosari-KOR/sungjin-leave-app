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

        # 💡 세션 상태에 '수정 모드' 변수 초기화
        if "edit_leave_mode" not in st.session_state:
            st.session_state.edit_leave_mode = False

        # 👑 관리자가 수정 버튼을 눌렀을 때의 뷰 (입력창으로 변신)
        if is_admin and st.session_state.edit_leave_mode:
            st.markdown("<div class='admin-box'>", unsafe_allow_html=True)
            st.markdown("<div style='font-size: 1.1rem; font-weight: 700; color: #3182f6; margin-bottom: 10px;'>✏️ 총 연차 숫자 직접 수정</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size: 0.9rem; color: #6b7684; margin-bottom: 10px;'>시스템 자동 계산 결과: {auto_days}일</div>", unsafe_allow_html=True)
            
            new_total = st.number_input("이 직원의 올해 총 연차", value=float(total_days), step=0.5, label_visibility="collapsed")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ 저장하기", type="primary", use_container_width=True):
                    save_manual_leave(user_row['사번'], selected_year, new_total)
                    st.session_state.edit_leave_mode = False # 저장 후 다시 카드 뷰로 돌아감
                    st.rerun()
            with col2:
                if st.button("❌ 취소", use_container_width=True):
                    st.session_state.edit_leave_mode = False # 취소해도 카드 뷰로 돌아감
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        # 👨‍💻 일반 사용자 뷰 & 관리자 평상시 뷰 (예쁜 토스 카드)
        else:
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
            
            # 관리자일 때만 예쁜 수정 버튼을 카드 바로 밑에 붙여주기
            if is_admin:
                if st.button("✏️ 총 연차 숫자 수정하기", use_container_width=True):
                    st.session_state.edit_leave_mode = True # 클릭 시 위쪽의 입력창 UI로 상태 변경
                    st.rerun()
        
        # --- 연차 내역 출력 ---
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
