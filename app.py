import os
import streamlit as st
import pandas as pd


st.set_page_config(
    page_title="A股量化助手",
    page_icon="📈",
    layout="wide"
)


# =========================
# 页面标题
# =========================

st.title("📈 A股量化助手")

st.caption(
    "股票 + ETF · MA · MACD · 成交量 · 综合评分"
)


# =========================
# 股票池
# =========================

@st.cache_data
def load_list(filename):

    if not os.path.exists(filename):
        return pd.DataFrame(
            columns=["code", "name"]
        )

    return pd.read_csv(
        filename,
        dtype={"code": str}
    )


stocks = load_list(
    "stock_list.csv"
)

etfs = load_list(
    "etf_list.csv"
)


# =========================
# 读取行情
# =========================

@st.cache_data
def load_data(
    code,
    asset_type
):

    filename = (
        f"data/{asset_type}_{code}.csv"
    )

    if not os.path.exists(filename):

        raise FileNotFoundError(
            f"没有找到行情文件：{filename}"
        )

    df = pd.read_csv(
        filename
    )

    df["日期"] = pd.to_datetime(
        df["日期"]
    )

    number_columns = [
        "开盘",
        "最高",
        "最低",
        "收盘",
        "成交量"
    ]

    for column in number_columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    df = df.dropna(
        subset=["收盘"]
    )

    df = df.sort_values(
        "日期"
    )

    # =====================
    # 涨跌幅
    # =====================

    df["涨跌幅"] = (
        df["收盘"]
        .pct_change()
        * 100
    )

    # =====================
    # 均线
    # =====================

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

    # =====================
    # MACD
    # =====================

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

    # =====================
    # 成交量
    # =====================

    df["VOL20"] = (
        df["成交量"]
        .rolling(20)
        .mean()
    )

    return df


# =========================
# 资产类型
# =========================

asset_type = st.radio(
    "选择分析类型",
    [
        "股票",
        "ETF"
    ],
    horizontal=True
)


if asset_type == "股票":

    asset_key = "stock"

    asset_list = stocks

else:

    asset_key = "etf"

    asset_list = etfs


# =========================
# 股票选择
# =========================

if not asset_list.empty:

    options = (
        asset_list["code"]
        + " - "
        + asset_list["name"]
    ).tolist()

    selected = st.selectbox(
        "选择品种",
        options
    )

    code = selected.split(
        " - "
    )[0]

else:

    code = st.text_input(
        "输入代码"
    )


# =========================
# 开始分析
# =========================

if st.button(
    "🚀 开始分析",
    type="primary"
):

    try:

        df = load_data(
            code,
            asset_key
        )

    except Exception as e:

        st.error(
            "读取行情失败"
        )

        st.code(
            str(e)
        )

        st.stop()

    latest = df.iloc[-1]

    price = latest["收盘"]

    change = latest["涨跌幅"]

    ma5 = latest["MA5"]

    ma20 = latest["MA20"]

    dif = latest["DIF"]

    dea = latest["DEA"]

    volume = latest["成交量"]

    volume20 = latest["VOL20"]

    # =====================
    # 基础行情
    # =====================

    st.success(
        f"{selected if 'selected' in locals() else code}"
        f" · "
        f"{latest['日期'].strftime('%Y-%m-%d')}"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "最新价格",
            f"{price:.3f}",
            f"{change:.2f}%"
        )

    with col2:

        st.metric(
            "MA5",
            f"{ma5:.3f}"
        )

    with col3:

        st.metric(
            "MA20",
            f"{ma20:.3f}"
        )

    # =====================
    # 评分
    # =====================

    score = 0

    if ma5 > ma20:
        score += 1

    if dif > dea:
        score += 1

    if volume > volume20:
        score += 1

    st.subheader(
        "🤖 综合量化评分"
    )

    if score == 3:

        st.success(
            "🟢 强势 · 3 / 3"
        )

    elif score == 2:

        st.info(
            "🟡 偏强 · 2 / 3"
        )

    elif score == 1:

        st.warning(
            "🟠 偏弱 · 1 / 3"
        )

    else:

        st.error(
            "🔴 弱势 · 0 / 3"
        )

    # =====================
    # 指标
    # =====================

    st.subheader(
        "📊 技术指标"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "DIF",
            f"{dif:.4f}"
        )

    with col2:

        st.metric(
            "DEA",
            f"{dea:.4f}"
        )

    with col3:

        st.metric(
            "成交量",
            f"{volume:,.0f}"
        )

    # =====================
    # 价格走势图
    # =====================

    st.subheader(
        "📈 价格与均线"
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

    # =====================
    # MACD
    # =====================

    st.subheader(
        "📊 MACD"
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

    # =====================
    # 最近数据
    # =====================

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
