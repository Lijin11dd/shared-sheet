import streamlit as st
import pandas as pd
import sqlite3
import hashlib

DB = "sheet.db"

# ---------- 数据层 ----------
def init_db():
    conn = sqlite3.connect(DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS data(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        col_a TEXT, col_b TEXT, col_c TEXT)""")
    conn.commit(); conn.close()

def load_df():
    conn = sqlite3.connect(DB)
    df = pd.read_sql("SELECT * FROM data", conn)
    conn.close(); return df

def save_df(df):
    conn = sqlite3.connect(DB)
    conn.execute("DELETE FROM data")
    df.to_sql("data", conn, if_exists="append", index=False)
    conn.commit(); conn.close()

# ---------- 登录逻辑 ----------
def check_login(user, pwd):
    """校验账号密码，密码做哈希比对"""
    users = st.secrets.get("passwords", {})
    if user in users:
        saved = users[user]
        return hashlib.sha256(pwd.encode()).hexdigest() == \
               hashlib.sha256(saved.encode()).hexdigest()
    return False

def show_login():
    st.title("共享表格 · 登录")
    with st.form("login"):
        user = st.text_input("用户名")
        pwd = st.text_input("密码", type="password")
        ok = st.form_submit_button("登录")
    if ok:
        if check_login(user, pwd):
            st.session_state["logged_in"] = True
            st.session_state["user"] = user
            st.rerun()
        else:
            st.error("用户名或密码错误")

def logout():
    if st.sidebar.button("退出登录"):
        st.session_state.pop("logged_in", None)
        st.rerun()

# ---------- 主流程 ----------
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    show_login()
    st.stop()          # 未登录就停在这里

# 已登录才显示表格
logout()
st.sidebar.write(f"当前用户：{st.session_state['user']}")
st.title("多人协作")
st.caption("大家改完点【保存】，数据写入共享数据库")

df = load_df()
edited = st.data_editor(df, num_rows="dynamic", use_container_width=True)
if st.button("保存"):
    save_df(edited)
    st.success("已保存")
