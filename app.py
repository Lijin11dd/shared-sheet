import streamlit as st
import pandas as pd
import sqlite3
import hashlib
from datetime import datetime

DB = "sheet.db"

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ---------- 数据层 ----------
def init_db():
    conn = sqlite3.connect(DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS data(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        col_a TEXT, col_b TEXT, col_c TEXT,
        updated_at TEXT)""")
    conn.commit(); conn.close()

def load_df():
    conn = sqlite3.connect(DB)
    df = pd.read_sql("SELECT id, col_a, col_b, col_c, updated_at FROM data", conn)
    conn.close(); return df

def get_snapshot():
    """数据库当前每行最后修改时间：{id: updated_at}"""
    df = load_df()
    return {int(r["id"]): r["updated_at"] for _, r in df.iterrows()}

def save_df(edited, session_open):
    """行级合并保存：后保存者生效，并返回被覆盖的行清单"""
    now = now_str()
    snapshot = get_snapshot()          # 保存瞬间的库状态
    edited_ids = set()
    overwritten = []                   # 被本次覆盖的他人修改

    conn = sqlite3.connect(DB)
    for _, row in edited.iterrows():
        rid = row.get("id")
        col_a, col_b, col_c = row["col_a"], row["col_b"], row["col_c"]

        if pd.isna(rid):               # 新增行
            conn.execute("INSERT INTO data(col_a,col_b,col_c,updated_at) VALUES(?,?,?,?)",
                         (col_a, col_b, col_c, now))
        else:
            rid = int(rid)
            edited_ids.add(rid)
            old_t = snapshot.get(rid)
            # 我打开表格之后，这行被别人改过 -> 记录下来（本次仍以后保存者为准覆盖）
            if old_t and old_t > session_open:
                overwritten.append((rid, old_t))
            conn.execute("UPDATE data SET col_a=?, col_b=?, col_c=?, updated_at=? WHERE id=?",
                         (col_a, col_b, col_c, now, rid))

    # 编辑里没有了、但库里还在的行 = 被删除，同步删掉
    for rid in snapshot:
        if rid not in edited_ids:
            conn.execute("DELETE FROM data WHERE id=?", (rid,))

    conn.commit(); conn.close()
    return overwritten

# ---------- 登录逻辑（沿用上一版） ----------
def check_login(user, pwd):
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
            st.session_state["session_open"] = now_str()   # 记录本次打开时刻
            st.rerun()
        else:
            st.error("用户名或密码错误")

def logout():
    if st.sidebar.button("退出登录"):
        st.session_state.pop("logged_in", None)
        st.rerun()

# ---------- 主流程 ----------
init_db()
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    show_login(); st.stop()

logout()
st.sidebar.write(f"当前用户：{st.session_state['user']}")
st.title("多人协作共享表格")
st.caption("后保存的人生效；被覆盖的他人修改会明确提示，不会静默丢失")

df = load_df()
edited = st.data_editor(
    df, num_rows="dynamic", hide_index=True, use_container_width=True,
    column_config={
        "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
        "updated_at": st.column_config.TextColumn("最后修改", disabled=True, width="medium"),
    },
)

if st.button("保存"):
    session_open = st.session_state.get("session_open", now_str())
    overwritten = save_df(edited, session_open)
    st.session_state["session_open"] = now_str()   # 保存后刷新"打开时刻"
    if overwritten:
        rows = "、".join(f"第{r[0]}行(曾被{r[1]}改)" for r in overwritten)
        st.warning(f"已保存。注意：以下行在我打开期间被他人修改过，已按【后保存生效】覆盖：{rows}")
    else:
        st.success("已保存")
