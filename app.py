import streamlit as st

st.set_page_config(
    page_title="A股量化选股助手",
    page_icon="📈",
    layout="wide"
)

st.title("📈 A股量化选股助手")
st.write("欢迎使用我们的第一个版本！")

st.divider()

st.subheader("🔎 股票查询")

stock_code = st.text_input(
    "请输入A股股票代码",
    placeholder="例如：600519"
)

if st.button("开始分析"):
    if not stock_code:
        st.warning("请先输入股票代码。")
    else:
        st.success(f"已经收到股票代码：{stock_code}")
        st.info("下一步我们会接入真实A股行情数据。")

st.divider()

st.subheader("📊 量化策略")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("MA5", "--")

with col2:
    st.metric("MA20", "--")

with col3:
    st.metric("MACD", "--")

st.divider()

st.caption("V1.0 · A股量化研究工具")
