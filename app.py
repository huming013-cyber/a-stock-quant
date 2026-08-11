import streamlit as st
import pandas as pd
import os


st.set_page_config(
    page_title="A股量化选股助手",
    page_icon="📈",
    layout="wide"
)


st.title("📈 A股量化选股助手")
st.caption("V1.3 · 本地行情数据 + MA + MACD")


# =========================
# 读取 GitHub 中的 CSV
# =========================

@st.cache_data
def load_stock_data(code):

    filename = f"data/{code}.csv"

    if not os.path.exists(filename):

        raise FileNotFoundError(
            f"暂时没有 {code} 的行情数据。"
        )

    df = pd.read_csv(
        filename
    )

    if df.empty:

        raise ValueError(
            "行情数据为空。"
        )

    # 日期
    df["日期"] = pd.to_datetime(
        df["日期"],
        errors="coerce"
    )

    # 数字字段
    number_columns = [
        "开盘",
        "收盘",
        "最高",
        "最低",
        "成交量"
    ]

    for column in number_columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    df = df.dropna(
        subset=["日期", "收盘"]
    )

    df = df.sort_values(
        "日期"
    )

    df = df.reset_index(
        drop=True
    )

    # =========================
    # 涨跌幅
    # =========================

    df["涨跌幅"] = (
        df["收盘"]
        .pct_change()
        * 100
    )

    # =========================
    # 均线
    # =========================

    df["MA5"] = (
        df["收盘"]
        .rolling(5)
        .mean()
    )

    df["MA10"] = (
        df["收盘"]
        .rolling(10)
        .mean()
    )

    df["MA20"] = (
        df["收盘"]
        .rolling(20)
        .mean()
    )

    # =========================
    # MACD
    # =========================

    ema12 = (
        df["收盘"]
        .ewm(
            span=12,
            adjust=False
        )
        .mean()
    )

    ema26 = (
        df["收盘"]
        .ewm(
            span=26,
            adjust=False
        )
        .mean()
    )

    df["DIF"] = (
        ema12 - ema26
    )

    df["DEA"] = (
        df["DIF"]
        .ewm(
            span=9,
            adjust=False
        )
        .mean()
    )

    df["MACD"] = (
        df["DIF"]
        - df["DEA"]
    ) * 2

    # =========================
    # 成交量均线
    # =========================

    df["VOL5"] = (
        df["成交量"]
        .rolling(5)
        .mean()
    )

    df["VOL20"] = (
        df["成交量"]
        .rolling(20)
        .mean()
    )

    return df


# =========================
# 股票输入
# =========================

st.subheader("🔎 股票分析")

stock_code = st.text_input(
    "请输入A股股票代码",
    value="600900"
).strip()


if st.button(
    "开始分析",
    type="primary"
):

    if not stock_code.isdigit():

        st.error(
            "请输入数字股票代码。"
        )

        st.stop()

    if len(stock_code) != 6:

        st.error(
            "请输入6位股票代码，例如 600900。"
        )

        st.stop()

    # =========================
    # 读取数据
    # =========================

    try:

        with st.spinner(
            "正在读取行情数据……"
        ):

            df = load_stock_data(
                stock_code
            )

    except FileNotFoundError as e:

        st.error(
            "没有找到这只股票的行情文件。"
        )

        st.info(
            "请先让 GitHub Actions 更新行情数据。"
        )

        st.code(
            str(e)
        )

        st.stop()

    except Exception as e:

        st.error(
            "读取行情数据失败。"
        )

        st.code(
            str(e)
        )

        st.stop()

    # =========================
    # 最新数据
    # =========================

    latest = df.iloc[-1]

    price = latest["收盘"]

    change = latest["涨跌幅"]

    ma5 = latest["MA5"]

    ma10 = latest["MA10"]

    ma20 = latest["MA20"]

    dif = latest["DIF"]

    dea = latest["DEA"]

    macd = latest["MACD"]

    volume = latest["成交量"]

    volume20 = latest["VOL20"]


    # =========================
    # 基础行情
    # =========================

    st.success(
        f"{stock_code} · "
        f"数据日期："
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


    # =========================
    # 均线
    # =========================

    st.subheader("📈 均线分析")


    col1, col2, col3 = st.columns(3)


    with col1:

        st.metric(
            "MA5",
            f"{ma5:.2f}"
        )


    with col2:

        st.metric(
            "MA10",
            f"{ma10:.2f}"
        )


    with col3:

        st.metric(
            "MA20",
            f"{ma20:.2f}"
        )


    if ma5 > ma20:

        st.success(
            "🟢 MA5 > MA20：短期趋势偏强"
        )

    else:

        st.warning(
            "🔴 MA5 < MA20：短期趋势偏弱"
        )


    # =========================
    # MACD
    # =========================

    st.subheader("📊 MACD")


    col1, col2, col3 = st.columns(3)


    with col1:

        st.metric(
            "DIF",
            f"{dif:.3f}"
        )


    with col2:

        st.metric(
            "DEA",
            f"{dea:.3f}"
        )


    with col3:

        st.metric(
            "MACD",
            f"{macd:.3f}"
        )


    if dif > dea:

        st.success(
            "🟢 DIF > DEA：MACD偏强"
        )

    else:

        st.warning(
            "🔴 DIF < DEA：MACD偏弱"
        )


    # =========================
    # 成交量
    # =========================

    st.subheader("🔊 成交量")


    col1, col2 = st.columns(2)


    with col1:

        st.metric(
            "最新成交量",
            f"{volume:,.0f}"
        )


    with col2:

        st.metric(
            "20日平均成交量",
            f"{volume20:,.0f}"
        )


    if volume > volume20:

        st.success(
            "🟢 成交量高于20日平均"
        )

    else:

        st.info(
            "⚪ 成交量低于20日平均"
        )


    # =========================
    # 综合量化评分
    # =========================

    st.subheader("🤖 量化评分")


    score = 0


    if ma5 > ma20:

        score += 1


    if dif > dea:

        score += 1


    if volume > volume20:

        score += 1


    if score == 3:

        st.success(
            "🟢 强势：3 / 3"
        )

    elif score == 2:

        st.info(
            "🟡 偏强：2 / 3"
        )

    elif score == 1:

        st.warning(
            "🟠 偏弱：1 / 3"
        )

    else:

        st.error(
            "🔴 弱势：0 / 3"
        )


    # =========================
    # 收盘价 + 均线
    # =========================

    st.subheader(
        "📉 最近120个交易日"
    )


    chart = df.tail(120)[
        [
            "日期",
            "收盘",
            "MA5",
            "MA10",
            "MA20"
        ]
    ].set_index(
        "日期"
    )


    st.line_chart(
        chart
    )


    # =========================
    # MACD图
    # =========================

    st.subheader(
        "📊 MACD走势"
    )


    macd_chart = df.tail(120)[
        [
            "日期",
            "DIF",
            "DEA",
            "MACD"
        ]
    ].set_index(
        "日期"
    )


    st.line_chart(
        macd_chart
    )


    # =========================
    # 最近30日
    # =========================

    st.subheader(
        "📋 最近30个交易日"
    )


    table = df.tail(30)[
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
        table,
        use_container_width=True,
        hide_index=True
    )


st.divider()


st.caption(
    "⚠️ 本程序仅用于量化研究、学习和历史数据分析，"
    "不构成投资建议。"
)
