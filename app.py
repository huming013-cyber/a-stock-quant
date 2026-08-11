import streamlit as st
import pandas as pd
import os


# =========================
# 页面设置
# =========================

st.set_page_config(
    page_title="A股量化选股助手",
    page_icon="📈",
    layout="wide"
)


st.title("📈 A股量化选股助手")
st.caption("V2.0 · 一键量化 · MA + MACD + 成交量")


# =========================
# 股票列表
# =========================

STOCK_LIST_FILE = "stock_list.csv"


@st.cache_data
def load_stock_list():

    if not os.path.exists(STOCK_LIST_FILE):

        raise FileNotFoundError(
            f"找不到 {STOCK_LIST_FILE}"
        )

    df = pd.read_csv(
        STOCK_LIST_FILE,
        dtype={"code": str},
        encoding="utf-8-sig"
    )

    if "code" not in df.columns:

        raise ValueError(
            "stock_list.csv 中没有找到 code 列"
        )

    stocks = (
        df["code"]
        .dropna()
        .astype(str)
        .str.strip()
        .str.zfill(6)
        .tolist()
    )

    return stocks


# =========================
# 读取股票行情
# =========================

@st.cache_data
def load_stock_data(code):

    filename = f"data/{code}.csv"

    if not os.path.exists(filename):

        return None

    df = pd.read_csv(
        filename,
        encoding="utf-8-sig"
    )

    if df.empty:

        return None

    # 日期

    if "日期" not in df.columns:

        return None

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

        if column in df.columns:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

    # 删除无效数据

    df = df.dropna(
        subset=["日期", "收盘"]
    )

    df = df.sort_values(
        "日期"
    )

    df = df.reset_index(
        drop=True
    )

    if len(df) < 30:

        return None

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
    # 成交量
    # =========================

    if "成交量" in df.columns:

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

    else:

        df["VOL5"] = 0
        df["VOL20"] = 0

    return df


# =========================
# 单只股票量化
# =========================

def analyze_stock(code):

    df = load_stock_data(code)

    if df is None:

        return None

    latest = df.iloc[-1]

    price = latest["收盘"]

    change = latest["涨跌幅"]

    ma5 = latest["MA5"]

    ma20 = latest["MA20"]

    dif = latest["DIF"]

    dea = latest["DEA"]

    volume = latest["成交量"]

    volume20 = latest["VOL20"]


    # =========================
    # 量化评分
    # =========================

    score = 0


    # MA趋势

    if pd.notna(ma5) and pd.notna(ma20):

        if ma5 > ma20:

            score += 1


    # MACD

    if pd.notna(dif) and pd.notna(dea):

        if dif > dea:

            score += 1


    # 成交量

    if pd.notna(volume) and pd.notna(volume20):

        if volume > volume20:

            score += 1


    # =========================
    # 信号
    # =========================

    if score == 3:

        signal = "🟢 强势"

    elif score == 2:

        signal = "🟡 偏强"

    elif score == 1:

        signal = "🟠 偏弱"

    else:

        signal = "🔴 弱势"


    return {

        "代码": code,

        "日期": latest["日期"],

        "收盘价": price,

        "涨跌幅": change,

        "MA5": ma5,

        "MA20": ma20,

        "DIF": dif,

        "DEA": dea,

        "成交量": volume,

        "成交量20日": volume20,

        "评分": score,

        "信号": signal

    }


# =========================
# 加载股票列表
# =========================

try:

    STOCKS = load_stock_list()

except Exception as e:

    st.error(
        "股票列表读取失败"
    )

    st.code(
        str(e)
    )

    st.stop()


# =========================
# 股票数量
# =========================

st.info(
    f"📋 当前股票池：{len(STOCKS)} 只股票"
)


# =========================
# 一键量化
# =========================

st.subheader("🚀 一键量化")


if st.button(
    "🚀 开始一键量化",
    type="primary",
    use_container_width=True
):

    results = []

    failed = []


    progress = st.progress(0)

    status = st.empty()


    total = len(STOCKS)


    for i, code in enumerate(STOCKS):

        status.write(
            f"正在分析 {code} "
            f"（{i + 1} / {total}）"
        )


        try:

            result = analyze_stock(code)

            if result is not None:

                results.append(result)

            else:

                failed.append(code)

        except Exception:

            failed.append(code)


        progress.progress(
            (i + 1) / total
        )


    status.success(
        "🎉 一键量化完成！"
    )


    # =========================
    # 量化结果
    # =========================

    if results:

        result_df = pd.DataFrame(
            results
        )


        # 按评分排序

        result_df = result_df.sort_values(
            by=[
                "评分",
                "涨跌幅"
            ],
            ascending=[
                False,
                False
            ]
        )


        st.subheader(
            "🏆 量化选股结果"
        )


        # =========================
        # 强势股票
        # =========================

        strong = result_df[
            result_df["评分"] == 3
        ]


        if not strong.empty:

            st.success(
                f"🟢 强势股票：{len(strong)} 只"
            )


            st.dataframe(
                strong[
                    [
                        "代码",
                        "日期",
                        "收盘价",
                        "涨跌幅",
                        "MA5",
                        "MA20",
                        "DIF",
                        "DEA",
                        "评分",
                        "信号"
                    ]
                ],
                use_container_width=True,
                hide_index=True
            )


        # =========================
        # 全部结果
        # =========================

        st.subheader(
            "📊 全部量化结果"
        )


        st.dataframe(
            result_df[
                [
                    "代码",
                    "日期",
                    "收盘价",
                    "涨跌幅",
                    "MA5",
                    "MA20",
                    "DIF",
                    "DEA",
                    "成交量",
                    "成交量20日",
                    "评分",
                    "信号"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )


        # =========================
        # 结果统计
        # =========================

        col1, col2, col3, col4 = st.columns(4)


        with col1:

            st.metric(
                "分析成功",
                len(results)
            )


        with col2:

            st.metric(
                "强势",
                len(
                    result_df[
                        result_df["评分"] == 3
                    ]
                )
            )


        with col3:

            st.metric(
                "偏强",
                len(
                    result_df[
                        result_df["评分"] == 2
                    ]
                )
            )


        with col4:

            st.metric(
                "无法分析",
                len(failed)
            )


        # =========================
        # 下载结果
        # =========================

        csv = result_df.to_csv(
            index=False,
            encoding="utf-8-sig"
        )


        st.download_button(
            "⬇️ 下载量化结果 CSV",
            data=csv,
            file_name="quant_result.csv",
            mime="text/csv",
            use_container_width=True
        )


        # =========================
        # 没有行情数据的股票
        # =========================

        if failed:

            with st.expander(
                "⚠️ 没有行情数据的股票"
            ):

                st.write(
                    failed
                )


    else:

        st.error(
            "❌ 没有成功分析任何股票。"
        )

        st.info(
            "请检查 GitHub 的 data/ 文件夹是否存在行情 CSV。"
        )


# =========================
# 单只股票详细分析
# =========================

st.divider()

st.subheader(
    "🔎 单只股票详细分析"
)


stock_code = st.text_input(
    "输入6位A股代码",
    value="600900"
).strip()


if st.button(
    "📊 分析这只股票"
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


    df = load_stock_data(
        stock_code
    )


    if df is None:

        st.error(
            f"没有找到 {stock_code} 的行情数据。"
        )

        st.stop()


    latest = df.iloc[-1]


    # =========================
    # 最新行情
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
            f"{latest['收盘']:.2f}",
            f"{latest['涨跌幅']:.2f}%"
        )


    with col2:

        st.metric(
            "MA5",
            f"{latest['MA5']:.2f}"
        )


    with col3:

        st.metric(
            "MA20",
            f"{latest['MA20']:.2f}"
        )


    # =========================
    # 趋势
    # =========================

    st.subheader(
        "📈 均线分析"
    )


    if latest["MA5"] > latest["MA20"]:

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

    st.subheader(
        "📊 MACD"
    )


    col1, col2, col3 = st.columns(3)


    with col1:

        st.metric(
            "DIF",
            f"{latest['DIF']:.3f}"
        )


    with col2:

        st.metric(
            "DEA",
            f"{latest['DEA']:.3f}"
        )


    with col3:

        st.metric(
            "MACD",
            f"{latest['MACD']:.3f}"
        )


    if latest["DIF"] > latest["DEA"]:

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

    st.subheader(
        "🔊 成交量"
    )


    col1, col2 = st.columns(2)


    with col1:

        st.metric(
            "最新成交量",
            f"{latest['成交量']:,.0f}"
        )


    with col2:

        st.metric(
            "20日平均成交量",
            f"{latest['VOL20']:,.0f}"
        )


    # =========================
    # K线趋势图
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
    # MACD走势图
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


# =========================
# 页脚
# =========================

st.divider()


st.caption(
    "⚠️ 本程序仅用于量化研究、学习和历史数据分析，"
    "不构成投资建议。"
)
