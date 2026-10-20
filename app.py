import streamlit as st
import pandas as pd
import sqlite3
import hashlib
from datetime import datetime

DB = "sheet.db"
FACTOR = 47                     # 倍数，想改成别的数改这里

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ---------- 数据层 ----------
def init_db():
    conn = sqlite3.connect(DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS data(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        col_a INTEGER,          # 第一列：手输数字
        col_b INTEGER,          # 第二列：自动 = col_a × 47
        updated_at TEXT)""")
    conn.commit(); conn.close()

def load_df():
    conn = sqlite3.connect(DB)
    df = pd.read_sql("SELECT id, col_a, col_b, updated_at FROM data", conn)
    conn.close(); return df

def auto_compute(df):
    """核心：第二列自动 = 第一列 × 47，用户改第一列即可"""
    df["col_b"] = df["col_a"] * FACTOR
    return df

def get_snapshot():
    df = load_df()
    return {int(r["id"]): r["updated_at"] for _, r in df.iterrows()}

def save_df(edited, session_open):
    edited = auto_compute(edited)          # 保存前再算一次，保证正确
    now = now_str()
    snapshot = get_snapshot()
    edited_ids = set()
    overwritten = []
    conn = sqlite3.connect(DB)
    for _, row in edited.iterrows():
        rid = row.get("id")
        if pd.isna(rid):
            conn.execute("INSERT INTO data(col_a,col_b,updated_at) VALUES(?,?,?)",
                         (int(row["col_a"]), int(row["col_b"]), now))
        else:
            rid = int(rid); edited_ids.add(rid)
            old_t = snapshot.get(rid)
            if old_t and old_t > session_open:
                overwritten.append((rid, old_t))
            conn.execute("UPDATE data SET col_a=?, col_b=?, updated_at=? WHERE id=?",
                         (int(row["col_a"]), int(row["col_b"]), now, rid))
    for rid in snapshot:
        if rid not in edited_ids:
            conn.execute("DELETE FROM data WHERE id=?", (rid,))
    conn.commit(); conn.close()
    return overwritten

# ---------- 登录逻辑 ----------
def check_login(user, pwd):
    users = st.secrets.get("passwords", {})
    if user in users:
        return hashlib.sha256(pwd.encode()).hexdigest() == \
               hashlib.sha256(users[user].encode()).hexdigest()
    return False

def show_login():
    st.title("共享表格 · 登录")
    with st.form("login"):
        user = st.text_input("用户名")
        pwd = st.text_input("密码", type="password")
        if st.form_submit_button("登录"):
            if check_login(user, pwd):
                st.session_state["logged_in"] = True
                st.session_state["user"] = user
                st.session_state["session_open"] = now_str()
                st.rerun()
            else:
                st.error("用户名或密码错误")

def logout():
    if st.sidebar.button("退出登录"):
        st.session_state.pop("logged_in", None); st.rerun()

# ---------- 主流程 ----------
init_db()
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if not st.session_state["logged_in"]:
    show_login(); st.stop()

logout()
st.sidebar.write(f"当前用户：{st.session_state['user']}")
st.title("共享表格（第二列自动 = 第一列 × 47）")
st.caption("第一列输入数字，第二列自动生成，无需手填")

# 表格初始数据（先自动算好倍数）
df = st.session_state.get("df", auto_compute(load_df()))
st.session_state["df"] = df

# 编辑表格：第一列可改，第二列只读自动生成
def on_edit():
    st.session_state["df"] = auto_compute(st.session_state["df"])  # 编辑后立刻重算

edited = st.data_editor(
    st.session_state["df"], num_rows="dynamic", hide_index=True,
    use_container_width=True, on_change=on_edit,
    column_config={
        "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
        "col_a": st.column_config.NumberColumn("数字", step=1),
        "col_b": st.column_config.NumberColumn("×47 结果", disabled=True),
        "updated_at": st.column_config.TextColumn("最后修改", disabled=True, width="medium"),
    },
)

if st.button("保存"):
    overwritten = save_df(edited, st.session_state.get("session_open", now_str()))
    st.session_state["session_open"] = now_str()
    if overwritten:
        rows = "、".join(f"第{r[0]}行(曾被{r[1]}改)" for r in overwritten)
        st.warning(f"已保存。覆盖了他人的修改：{rows}")
    else:
        st.success("已保存")
