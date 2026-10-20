import streamlit as st
import pandas as pd
import sqlite3

DB = "sheet.db"

def init_db():
    """首次运行建表"""
    conn = sqlite3.connect(DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS data(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        col_a TEXT, col_b TEXT, col_c TEXT)""")
    conn.commit()
    conn.close()

def load_df():
    conn = sqlite3.connect(DB)
    df = pd.read_sql("SELECT * FROM data", conn)
    conn.close()
    return df

def save_df(df):
    conn = sqlite3.connect(DB)
    conn.execute("DELETE FROM data")          # 覆盖式保存，简单够用
    df.to_sql("data", conn, if_exists="append", index=False)
    conn.commit()
    conn.close()

init_db()

st.title("多人协作共享表格")
st.caption("大家改完点【保存】，数据写入共享数据库")

df = load_df()
edited = st.data_editor(df, num_rows="dynamic", use_container_width=True)

if st.button("保存"):
    save_df(edited)
    st.success("已保存")
