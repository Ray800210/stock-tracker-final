import streamlit as st
import pandas as pd
import yfinance as yf
import sqlite3

# --- 1. 頁面設定 ---
st.set_page_config(page_title="股票資金統計系統", layout="wide")

# --- 2. 資料庫初始化 ---
conn = sqlite3.connect('stock_data_v2.db', check_same_thread=False)
c = conn.cursor()
# 增加一個 ID 欄位方便單筆刪除
c.execute('''
    CREATE TABLE IF NOT EXISTS investments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT, 
        initial_funds REAL, 
        stock_id TEXT, 
        amount INTEGER, 
        cost REAL
    )
''')
conn.commit()

# --- 3. 側邊欄 ---
st.sidebar.title("📊 投資管理系統")
current_user = st.sidebar.text_input("請輸入使用者名稱", value="Ray")
menu = ["📈 資產概況與管理", "➕ 新增投資紀錄"]
choice = st.sidebar.selectbox("功能選單", menu)

# --- 4. 功能：新增資料 ---
if choice == "➕ 新增投資紀錄":
    st.header(f"新增 {current_user} 的投資紀錄")
    with st.form("add_form", clear_on_submit=True):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            funds = st.number_input("設定初始總資金 (本金)", min_value=0.0, value=1000000.0)
            stock_id = st.text_input("股票代號", placeholder="例: 2330.TW").upper()
        with col_f2:
            amount = st.number_input("持股數量", min_value=0, step=1)
            cost = st.number_input("每股平均成本", min_value=0.0)
        
        submit = st.form_submit_button("確認新增")
        if submit and stock_id:
            c.execute('INSERT INTO investments (username, initial_funds, stock_id, amount, cost) VALUES (?,?,?,?,?)', 
                      (current_user, funds, stock_id, amount, cost))
            conn.commit()
            st.success(f"✅ {stock_id} 已成功加入紀錄")

# --- 5. 功能：資產概況與單筆刪除 ---
elif choice == "📈 資產概況與管理":
    st.header(f"{current_user} 的投資即時看板")
    
    # 讀取資料
    user_df = pd.read_sql_query(f"SELECT * FROM investments WHERE username='{current_user}'", conn)
    
    if not user_df.empty:
        # 取得最後設定的初始資金
        initial_total_funds = user_df['initial_funds'].iloc[-1]
        
        summary_data = []
        with st.spinner('連線交易所抓取現價中...'):
            for _, row in user_df.iterrows():
                try:
                    tk = yf.Ticker(row['stock_id'])
                    hist = tk.history(period="2d")
                    if not hist.empty:
                        now_p = hist['Close'].iloc[-1]
                        last_p = hist['Close'].iloc[-2] if len(hist) > 1 else now_p
                        
                        invested = row['amount'] * row['cost']
                        current_mval = row['amount'] * now_p
                        pnl = current_mval - invested
                        
                        summary_data.append({
                            "ID": row['id'],
                            "股票代號": row['stock_id'],
                            "持股數量": row['amount'],
                            "平均成本": row['cost'],
                            "目前現價": round(now_p, 2),
                            "投入金額": invested,
                            "總市值": current_mval,
                            "獲利總額": pnl,
                            "當日損益": (now_p - last_p) * row['amount']
                        })
                except:
                    continue

        if summary_data:
            res_df = pd.DataFrame(summary_data)
            
            # --- 數據匯總資訊 ---
            total_invested = res_df['投入金額'].sum()     # 投入總額
            total_market_val = res_df['總市值'].sum()     # 總市值
            total_pnl = res_df['獲利總額'].sum()          # 獲利總額
            total_daily_pnl = res_df['當日損益'].sum()    # 當日損益總額
            cash_balance = initial_total_funds - total_invested # 所剩餘額
            roi = (total_pnl / total_invested * 100) if total_invested != 0 else 0

            # 第一排：資金水位
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("初始總資金", f"${initial_total_funds:,.0f}")
            k2.metric("投入總額", f"${total_invested:,.0f}")
            k3.metric("所剩餘額 (現金)", f"${cash_balance:,.0f}")
            k4.metric("總資產 (市值+現金)", f"${(total_market_val + cash_balance):,.0f}")

            # 第二排：損益表現
            st.divider()
            p1, p2, p3, p4 = st.columns(4)
            p1.metric("總市值", f"${total_market_val:,.0f}")
            p2.metric("獲利總額", f"${total_pnl:,.0f}", delta=f"{roi:.2f}% (總報酬)")
            p3.metric("今日合計損益", f"${total_daily_pnl:,.0f}")
            
            # 收盤建議邏輯
            with p4:
                st.subheader("💡 收盤建議")
                if total_daily_pnl < 0:
                    st.caption("🚨 盤勢較弱，請落實停損計畫。")
                elif roi > 10:
                    st.caption("🎉 獲利良好，可考慮部分入袋為安。")
                else:
                    st.caption("⚖️ 表現平穩，建議維持原定策略。")

            st.divider()

            # --- 持股明細與刪除功能 ---
            st.subheader("📂 持股明細管理")
            # 建立一個表格顯示，並在每一行後面放一個刪除按鈕
            for index, row in res_df.iterrows():
                col_data, col_btn = st.columns([0.85, 0.15])
                with col_data:
                    # 使用 Markdown 讓文字整齊
                    st.write(f"**{row['股票代號']}** | 持股: {row['持股數量']} | 成本: {row['平均成本']} | 現價: {row['目前現價']} | 獲利: :red[${row['獲利總額']:,.0f}]")
                with col_btn:
                    if st.button(f"🗑️ 刪除", key=f"del_{row['ID']}"):
                        c.execute(f"DELETE FROM investments WHERE id={row['ID']}")
                        conn.commit()
                        st.rerun() # 重新整理頁面
                st.write("---") # 分隔線
            
    else:
        st.info("目前尚無投資資料，請先前往「新增投資紀錄」。")

# 關閉資料庫連線建議放在最後（但在 Streamlit 中通常維持開啟）
