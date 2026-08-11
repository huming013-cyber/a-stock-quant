import streamlit as st
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(
    page_title="A股量化选股助手",
    page_icon="📈",
    layout="wide"
)

st.title("📈 A股量化选股助手")
st.caption("V1.1 · A股行情 + MA + MACD")

# -----------------------------
# 获取股票历史数据
# -----------------------------
@st.cache_data(ttl=300)
def get_stock_data(stock_code):

    end_date = datetime.now()
    start_date = end_date - timedelta(days=500)

    df = ak.stock_zh_a_hist(
        symbol=stock_code,
        period="daily",
        start_date=start_date.strftime("%Y%m%d"),
        end_date=end_date.strftime("%Y%m%d"),
        adjust="qfq"
    )

    if df is None or df.empty:
        return None

    df["日期"] = pd.to_datetime(df["日期"])
    df = df.sort_values("日期").reset_index(drop=True)

    # MA
    df["MA5"] = df["收盘"].rolling(5).mean()
    df["MA20"] = df["收盘"].rolling(20).mean()

    # MACD
    ema12 = df["收盘"].ewm(span=12, adjust=False).mean()
    ema26 = df["收盘"].ewm(span=26, adjust=False).mean()

    df["DIF"] = ema12 - ema26
    df["DEA"] = df["DIF"].ewm(span=9, adjust=False).mean()
    df["MACD"] = (df["DIF"] - df["DEA"]) * 2

    # 成交量20日平均
    df["VOL20"] = df["成交量"].rolling(20).mean()

    return df


# -----------------------------
# 股票输入
# -----------------------------

st.subheader("🔎 股票分析")

stock_code = st.text_input(
    "请输入A股股票代码",
    value="600900",
    placeholder="例如：600519"
).strip()

if st.button("开始分析", type="primary"):

    if not stock_code.isdigit() or len(stock_code) != 6:
        st.error("请输入6位A股股票代码，例如：600519")
        st.stop()

    with st.spinner("正在获取A股历史行情，请稍等……"):

        try:
            df = get_stock_data(stock_code)

        except Exception as e:
            st.error("获取行情失败。")
            st.warning(
                "可能是数据源暂时无法访问，请稍后再试。"
            )
            st.stop()

    if df is None or df.empty:
        st.error("没有找到该股票的历史行情。")
        st.stop()

    # 最新数据
    latest = df.iloc[-1]

    price = latest["收盘"]
    change = latest["涨跌幅"]
    ma5 = latest["MA5"]
    ma20 = latest["MA20"]
    dif = latest["DIF"]
    dea = latest["DEA"]
    macd = latest["MACD"]

    # -----------------------------
    # 基本行情
    # -----------------------------

    st.success(
        f"股票 {stock_code} · 最新交易日："
        f"{latest['日期'].strftime('%Y-%m-%d')}"
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "最新收盘价",
            f"{price:.2f}",
            f"{change:.2f}%"
        )

    with col2:
        st.metric(
            "MA5",
            f"{ma5:.2f}"
        )

    with col3:
        st.metric(
            "MA20",
            f"{ma20:.2f}"
        )

    # -----------------------------
    # MACD
    # -----------------------------

    st.subheader("📊 MACD")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("DIF", f"{dif:.3f}")

    with col2:
        st.metric("DEA", f"{dea:.3f}")

    with col3:
        st.metric("MACD", f"{macd:.3f}")

    if dif > dea:
        st.success("MACD：DIF 在 DEA 上方")
    else:
        st.warning("MACD：DIF 在 DEA 下方")

    # -----------------------------
    # 均线状态
    # -----------------------------

    st.subheader("📈 均线状态")

    if ma5 > ma20:
        st.success("MA5 > MA20：短期趋势偏强")
    else:
        st.warning("MA5 < MA20：短期趋势偏弱")

    # -----------------------------
    # 成交量
    # -----------------------------

    st.subheader("🔊 成交量")

    today_volume = latest["成交量"]
    avg_volume = latest["VOL20"]

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "今日成交量",
            f"{today_volume:,.0f} 手"
        )

    with col2:
        st.metric(
            "20日平均成交量",
            f"{avg_volume:,.0f} 手"
        )

    if today_volume > avg_volume:
        st.success("成交量：高于20日平均")
    else:
        st.info("成交量：低于20日平均")

    # -----------------------------
    # 简单策略信号
    # -----------------------------

    st.subheader("🤖 当前策略信号")

    bullish_ma = ma5 > ma20
    bullish_macd = dif > dea
    volume_up = today_volume > avg_volume

    score = sum([
        bullish_ma,
        bullish_macd,
        volume_up
    ])

    if score == 3:
        st.success(
            "🟢 强势信号：3/3 条件满足"
        )
    elif score == 2:
        st.info(
            f"🟡 偏强信号：{score}/3 条件满足"
        )
    elif score == 1:
        st.warning(
            f"🟠 偏弱信号：{score}/3 条件满足"
        )
    else:
        st.error(
            "🔴 弱势信号：0/3 条件满足"
        )

    # -----------------------------
    # 最近30个交易日
    # -----------------------------

    st.subheader("📋 最近30个交易日")

    display_df = df.tail(30).copy()

    display_df = display_df[
        [
            "日期",
            "开盘",
            "最高",
            "最低",
            "收盘",
            "涨跌幅",
            "成交量",
            "MA5",
            "MA20",
            "DIF",
            "DEA"
        ]
    ]

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )

    # -----------------------------
    # 收盘价 + 均线图
    # -----------------------------

    st.subheader("📉 收盘价与均线")

    chart_df = df.tail(120)[
        ["日期", "收盘", "MA5", "MA20"]
    ].copy()

    chart_df = chart_df.set_index("日期")

    st.line_chart(chart_df)

else:

    st.info(
        "输入股票代码后，点击「开始分析」即可获取行情。"
    )

st.divider()

st.caption(
    "⚠️ 本程序仅用于量化研究和历史数据分析，不构成投资建议。"
)
