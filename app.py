import streamlit as st
import pandas as pd
import requests

st.set_page_config(
    page_title="A股量化选股助手",
    page_icon="📈",
    layout="wide"
)

st.title("📈 A股量化选股助手")
st.caption("V1.2 · 东方财富行情 + MA + MACD")


# =========================
# 判断股票所属市场
# =========================

def get_market(code):
    """
    6开头：上海
    0/3开头：深圳
    """

    if code.startswith(("6", "68")):
        return "1"

    if code.startswith(("0", "3")):
        return "0"

    return None


# =========================
# 获取东方财富历史K线
# =========================

@st.cache_data(ttl=300)
def get_stock_data(code):

    market = get_market(code)

    if market is None:
        raise ValueError(
            "暂时只支持沪深A股，例如 600900、600519、000001、300750"
        )

    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"

    params = {
        "secid": f"{market}.{code}",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "1",
        "beg": "0",
        "end": "20500101",
        "lmt": "500"
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        ),
        "Referer": "https://quote.eastmoney.com/"
    }

    response = requests.get(
        url,
        params=params,
        headers=headers,
        timeout=15
    )

    response.raise_for_status()

    data = response.json()

    if not data.get("data"):
        raise ValueError(
            "没有获取到该股票的数据，请检查股票代码。"
        )

    klines = data["data"].get("klines")

    if not klines:
        raise ValueError(
            "该股票没有返回历史K线数据。"
        )

    rows = []

    for item in klines:

        values = item.split(",")

        if len(values) < 11:
            continue

        rows.append(values)

    if not rows:
        raise ValueError("K线数据解析失败。")

    columns = [
        "日期",
        "开盘",
        "收盘",
        "最高",
        "最低",
        "成交量",
        "成交额",
        "振幅",
        "涨跌幅",
        "涨跌额",
        "换手率"
    ]

    df = pd.DataFrame(
        rows,
        columns=columns
    )

    # 数字字段
    number_columns = [
        "开盘",
        "收盘",
        "最高",
        "最低",
        "成交量",
        "成交额",
        "振幅",
        "涨跌幅",
        "涨跌额",
        "换手率"
    ]

    for column in number_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    df["日期"] = pd.to_datetime(df["日期"])

    df = df.sort_values("日期")
    df = df.reset_index(drop=True)

    # =========================
    # 均线
    # =========================

    df["MA5"] = df["收盘"].rolling(5).mean()
    df["MA10"] = df["收盘"].rolling(10).mean()
    df["MA20"] = df["收盘"].rolling(20).mean()

    # =========================
    # MACD
    # =========================

    ema12 = df["收盘"].ewm(
        span=12,
        adjust=False
    ).mean()

    ema26 = df["收盘"].ewm(
        span=26,
        adjust=False
    ).mean()

    df["DIF"] = ema12 - ema26

    df["DEA"] = df["DIF"].ewm(
        span=9,
        adjust=False
    ).mean()

    df["MACD"] = (
        df["DIF"] - df["DEA"]
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
# 页面
# =========================

st.subheader("🔎 股票分析")

stock_code = st.text_input(
    "请输入A股股票代码",
    value="600900",
    placeholder="例如：600519"
).strip()


if st.button("开始分析", type="primary"):

    # =========================
    # 检查代码
    # =========================

    if not stock_code.isdigit():

        st.error(
            "股票代码必须是数字。"
        )

        st.stop()

    if len(stock_code) != 6:

        st.error(
            "请输入6位股票代码，例如：600519"
        )

        st.stop()

    # =========================
    # 获取数据
    # =========================

    with st.spinner(
        "正在获取A股历史行情，请稍等……"
    ):

        try:

            df = get_stock_data(
                stock_code
            )

        except requests.exceptions.Timeout:

            st.error(
                "行情接口连接超时。"
            )

            st.info(
                "请稍等几十秒后重新点击「开始分析」。"
            )

            st.stop()

        except requests.exceptions.RequestException as e:

            st.error(
                "行情接口连接失败。"
            )

            st.code(
                str(e)
            )

            st.stop()

        except Exception as e:

            st.error(
                "获取行情失败。"
            )

            st.warning(
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
        f"最新交易日："
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
            "🟢 MACD：DIF 位于 DEA 上方"
        )

    else:

        st.warning(
            "🔴 MACD：DIF 位于 DEA 下方"
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
            "🟢 今日成交量高于20日平均"
        )

    else:

        st.info(
            "⚪ 今日成交量低于20日平均"
        )

    # =========================
    # 综合信号
    # =========================

    st.subheader("🤖 量化信号")

    ma_signal = ma5 > ma20
    macd_signal = dif > dea
    volume_signal = volume > volume20

    score = sum([
        ma_signal,
        macd_signal,
        volume_signal
    ])

    if score == 3:

        st.success(
            "🟢 强势信号：3 / 3 条件满足"
        )

    elif score == 2:

        st.info(
            "🟡 偏强信号：2 / 3 条件满足"
        )

    elif score == 1:

        st.warning(
            "🟠 偏弱信号：1 / 3 条件满足"
        )

    else:

        st.error(
            "🔴 弱势信号：0 / 3 条件满足"
        )

    # =========================
    # K线 + 均线
    # =========================

    st.subheader("📉 最近120个交易日")

    chart_df = df.tail(120).copy()

    chart_df = chart_df[
        [
            "日期",
            "收盘",
            "MA5",
            "MA10",
            "MA20"
        ]
    ]

    chart_df = chart_df.set_index(
        "日期"
    )

    st.line_chart(
        chart_df
    )

    # =========================
    # MACD走势图
    # =========================

    st.subheader("📊 MACD走势图")

    macd_chart = df.tail(120)[
        [
            "日期",
            "DIF",
            "DEA",
            "MACD"
        ]
    ].set_index("日期")

    st.line_chart(
        macd_chart
    )

    # =========================
    # 最近30日数据
    # =========================

    st.subheader("📋 最近30个交易日")

    table = df.tail(30)[
        [
            "日期",
            "开盘",
            "最高",
            "最低",
            "收盘",
            "涨跌幅",
            "成交量",
            "换手率",
            "MA5",
            "MA20",
            "DIF",
            "DEA"
        ]
    ].copy()

    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "输入股票代码，然后点击「开始分析」。"
    )


st.divider()

st.caption(
    "⚠️ 本程序仅用于量化研究、学习和历史数据分析，"
    "不构成投资建议。"
)
