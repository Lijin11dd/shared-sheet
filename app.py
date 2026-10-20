# -*- coding: utf-8 -*-
"""
多人协作共享表格（Streamlit）
- 登录保护
- 第一列手动输入数字，第二列自动 = 第一列 × 47
- 每行带"最后修改时间"，后保存者生效，并提示被覆盖的他人修改
- 表格下方实时合计
"""
import streamlit as st
import pandas as pd
import sqlite3
import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo

DB = "sheet.db"
FACTOR = 47                     # 倍数，想改这里


# ---------- 通用 ----------
def now_str():
    """返回北京时间（Asia/Shanghai），不受服务器时区影响"""
    return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")


# ---------- 数据层 ----------
def init_db():
    conn = sqlite3.connect(DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS data(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        col_a REAL,
        col_b REAL,
        updated_at TEXT)""")
    conn.commit()
    conn.close()


def load_df():
    conn = sqlite3.connect(DB)
    df = pd.read_sql("SELECT id, col_a, col_b, updated_at FROM data", conn)
    conn.close()
    return df


def auto_compute(df):
    """第二列自动 = 第一列 × 47（空值填 0，避免 NaN 报错）"""
    df = df.copy()
    df["col_a"] = pd.to_numeric(df["col_a"], errors="coerce").fillna(0)
    df["col_b"] = df["col_a"] * FACTOR
    return df


def get_snapshot():
    """数据库当前每行最后修改时间 {id: updated_at}"""
    df = load_df()
    return {int(r["id"]): r["updated_at"] for _, r in df.iterrows()}


def save_df(edited, session_open):
    """行级合并保存，后保存者生效，返回被覆盖的行清单"""
    edited = auto_compute(edited)      # 保存前再算一遍倍数，保证正确
    now = now_str()
    snapshot = get_snapshot()
    edited_ids = set()
    overwritten = []

    conn = sqlite3.connect(DB)
    for _, row in edited.iterrows():
        a = row["col_a"]
        if pd.isna(a) or a == 0:       # 空行跳过，避免崩溃
            continue
        b = float(a) * FACTOR
        rid = row.get("id")

        if pd.isna(rid):               # 新增行
            conn.execute(
                "INSERT INTO data(col_a, col_b, updated_at) VALUES(?,?,?)",
                (float(a), b, now))
        else:                          # 已有行
            rid = int(rid)
            edited_ids.add(rid)
            old_t = snapshot.get(rid)
            if old_t and old_t > session_open:      # 我打开后被别人改过
                overwritten.append((rid, old_t))
            conn.execute(
                "UPDATE data SET col_a=?, col_b=?, updated_at=? WHERE id=?",
                (float(a), b, now, rid))

    # 编辑里没有、但库里还在的行 = 被删除，同步删除
    for rid in snapshot:
        if rid not in edited_ids:
            conn.execute("DELETE FROM data WHERE id=?", (rid,))

    conn.commit()
    conn.close()
    return overwritten


# ---------- 登录逻辑 ----------
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
        st.session_state.pop("logged_in", None)
        st.rerun()


# ---------- 主流程 ----------
init_db()

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    show_login()
    st.stop()

logout()
st.sidebar.write(f"当前用户：{st.session_state['user']}")
st.title("共享表格（第二列自动 = 第一列 × 47）")
st.caption("第一列输入数字 → 点【保存】→ 第二列自动生成并入库")

# 载入数据并自动算好倍数（空行填 0）
df = auto_compute(load_df())

edited = st.data_editor(
    df,
    num_rows="dynamic",
    hide_index=True,
    use_container_width=True,
    column_config={
        "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
        "col_a": st.column_config.NumberColumn("数字", step=1),
        "col_b": st.column_config.NumberColumn("×47 结果", disabled=True),
        "updated_at": st.column_config.TextColumn("最后修改", disabled=True, width="medium"),
    },
)

# ---- 合计统计（基于当前编辑数据实时计算，不入库）----
col_a_total = pd.to_numeric(edited["col_a"], errors="coerce").fillna(0).sum()
total = col_a_total * FACTOR
st.markdown(
    f"### 合计：**{total:,.0f}**　（第一列合计 {col_a_total:,.0f} × {FACTOR}）"
)

if st.button("保存"):
    overwritten = save_df(edited, st.session_state.get("session_open", now_str()))
    st.session_state["session_open"] = now_str()
    if overwritten:
        rows = "、".join(f"第{r[0]}行(曾被{r[1]}改)" for r in overwritten)
        st.warning(f"已保存。覆盖了他人修改：{rows}")
    else:
        st.success("已保存")
    st.rerun()
