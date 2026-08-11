import streamlit as st
import pandas as pd
import os


# =========================================================
# 页面设置
# =========================================================

st.set_page_config(
    page_title="A股量化选股助手 V3.1",
    page_icon="📈",
    layout="wide"
)

st.title("📈 A股量化选股助手")
st.caption("V3.1 · 中文名称 · 综合评分 0-100 · 自动排名 · Top 10")


# =========================================================
# 股票列表文件
# =========================================================

STOCK_LIST_FILE = "stock_list.csv"


# =========================================================
# 读取股票列表 + 中文名称
# =========================================================

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

    # 检查 code

    if "code" not in df.columns:

        raise ValueError(
            "stock_list.csv 中没有找到 code 列"
        )

    # 检查 name

    if "name" not in df.columns:

        raise ValueError(
            "stock_list.csv 中没有找到 name 列"
        )

    # 股票代码统一为6位

    df["code"] = (
        df["code"]
        .astype(str)
        .str.strip()
        .str.zfill(6)
    )

    # 股票名称

    df["name"] = (
        df["name"]
        .fillna("未知股票")
        .astype(str)
        .str.strip()
    )

    # 删除重复股票

    df = df.drop_duplicates(
        subset=["code"]
    )

    return df[
        [
            "code",
            "name"
        ]
    ]


# =========================================================
# 读取行情数据
# =========================================================

@st.cache_data
def load_stock_data(code):

    filename = f"data/{code}.csv"

    if not os.path.exists(filename):

        return None

    try:

        df = pd.read_csv(
            filename,
            encoding="utf-8-sig"
        )

    except Exception:

        return None

    if df.empty:

        return None

    # 必须有日期和收盘

    if "日期" not in df.columns:

        return None

    if "收盘" not in df.columns:

        return None

    # =====================================================
    # 日期
    # =====================================================

    df["日期"] = pd.to_datetime(
        df["日期"],
        errors="coerce"
    )

    # =====================================================
    # 数值
    # =====================================================

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
        subset=[
            "日期",
            "收盘"
        ]
    )

    # 按日期排序

    df = df.sort_values(
        "日期"
    )

    df = df.reset_index(
        drop=True
    )

    # 至少需要30个交易日

    if len(df) < 30:

        return None

    # =====================================================
    # 涨跌幅
    # =====================================================

    df["涨跌幅"] = (
        df["收盘"]
        .pct_change()
        * 100
    )

    # =====================================================
    # 均线
    # =====================================================

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

    df["MA60"] = (
        df["收盘"]
        .rolling(60)
        .mean()
    )

    # =====================================================
    # MACD
    # =====================================================

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

    # =====================================================
    # 成交量
    # =====================================================

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

    # =====================================================
    # 动量
    # =====================================================

    df["RETURN5"] = (
        df["收盘"]
        .pct_change(5)
        * 100
    )

    df["RETURN20"] = (
        df["收盘"]
        .pct_change(20)
        * 100
    )

    # =====================================================
    # 20日波动率
    # =====================================================

    df["VOLATILITY20"] = (
        df["涨跌幅"]
        .rolling(20)
        .std()
    )

    return df


# =========================================================
# 读取股票池
# =========================================================

try:

    STOCK_LIST = load_stock_list()

except Exception as e:

    st.error(
        "股票列表读取失败"
    )

    st.code(
        str(e)
    )

    st.stop()


# 股票代码

STOCKS = (
    STOCK_LIST["code"]
    .tolist()
)


# 股票名称字典

STOCK_NAMES = dict(
    zip(
        STOCK_LIST["code"],
        STOCK_LIST["name"]
    )
)


# =========================================================
# 股票数量
# =========================================================

st.info(
    f"📋 当前股票池：{len(STOCKS)} 只股票"
)


# =========================================================
# 单只股票量化
# =========================================================

def analyze_stock(code):

    df = load_stock_data(code)

    if df is None:

        return None

    latest = df.iloc[-1]

    price = latest["收盘"]

    change = latest["涨跌幅"]

    ma5 = latest["MA5"]

    ma10 = latest["MA10"]

    ma20 = latest["MA20"]

    ma60 = latest["MA60"]

    dif = latest["DIF"]

    dea = latest["DEA"]

    volume = latest["成交量"]

    volume20 = latest["VOL20"]

    return5 = latest["RETURN5"]

    return20 = latest["RETURN20"]

    volatility = latest["VOLATILITY20"]


    # =====================================================
    # 1. 趋势评分 30分
    # =====================================================

    trend_score = 0


    if pd.notna(ma5) and pd.notna(ma20):

        if ma5 > ma20:

            trend_score += 10


    if pd.notna(ma10) and pd.notna(ma20):

        if ma10 > ma20:

            trend_score += 10


    if pd.notna(price) and pd.notna(ma60):

        if price > ma60:

            trend_score += 10


    # =====================================================
    # 2. MACD评分 25分
    # =====================================================

    macd_score = 0


    if pd.notna(dif) and pd.notna(dea):

        if dif > dea:

            macd_score += 15

        if dif > 0:

            macd_score += 10


    # =====================================================
    # 3. 成交量评分 15分
    # =====================================================

    volume_score = 0


    if (
        pd.notna(volume)
        and pd.notna(volume20)
    ):

        if volume > volume20:

            volume_score += 15


    # =====================================================
    # 4. 动量评分 20分
    # =====================================================

    momentum_score = 0


    if pd.notna(return5):

        if return5 > 0:

            momentum_score += 10


    if pd.notna(return20):

        if return20 > 0:

            momentum_score += 10


    # =====================================================
    # 5. 稳定性评分 10分
    # =====================================================

    stability_score = 0


    if pd.notna(volatility):

        if volatility < 3:

            stability_score = 10

        elif volatility < 5:

            stability_score = 7

        elif volatility < 8:

            stability_score = 4

        else:

            stability_score = 1


    # =====================================================
    # 综合评分
    # =====================================================

    score = (
        trend_score
        + macd_score
        + volume_score
        + momentum_score
        + stability_score
    )


    # =====================================================
    # 信号
    # =====================================================

    if score >= 80:

        signal = "🟢 强势"

    elif score >= 65:

        signal = "🟡 偏强"

    elif score >= 50:

        signal = "🟠 观察"

    else:

        signal = "🔴 偏弱"


    # =====================================================
    # 返回结果
    # =====================================================

    return {

        "股票名称": STOCK_NAMES.get(
            code,
            "未知股票"
        ),

        "代码": code,

        "日期": latest["日期"],

        "收盘价": price,

        "涨跌幅": change,

        "趋势": trend_score,

        "MACD": macd_score,

        "成交量": volume_score,

        "动量": momentum_score,

        "稳定性": stability_score,

        "综合评分": score,

        "信号": signal,

        "MA5": ma5,

        "MA20": ma20,

        "DIF": dif,

        "DEA": dea,

        "5日涨幅": return5,

        "20日涨幅": return20,

        "波动率": volatility

    }


# =========================================================
# 一键量化
# =========================================================

st.subheader(
    "🚀 一键量化"
)


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
            f"正在量化："
            f"{STOCK_NAMES.get(code, '未知股票')} "
            f"({code}) "
            f"（{i + 1} / {total}）"
        )


        try:

            result = analyze_stock(
                code
            )

            if result is not None:

                results.append(
                    result
                )

            else:

                failed.append(
                    code
                )

        except Exception:

            failed.append(
                code
            )


        progress.progress(
            (i + 1) / total
        )


    status.success(
        "🎉 一键量化完成！"
    )


    # =====================================================
    # 有结果
    # =====================================================

    if results:

        result_df = pd.DataFrame(
            results
        )


        # 按综合评分 + 20日涨幅排序

        result_df = result_df.sort_values(
            by=[
                "综合评分",
                "20日涨幅"
            ],
            ascending=[
                False,
                False
            ]
        )


        result_df = result_df.reset_index(
            drop=True
        )


        # =================================================
        # 排名
        # =================================================

        result_df.insert(
            0,
            "排名",
            range(
                1,
                len(result_df) + 1
            )
        )


        # =================================================
        # Top 10
        # =================================================

        st.subheader(
            "🏆 今日量化 Top 10"
        )


        top10 = result_df.head(10)


        st.dataframe(
            top10[
                [
                    "排名",
                    "股票名称",
                    "代码",
                    "日期",
                    "收盘价",
                    "涨跌幅",
                    "趋势",
                    "MACD",
                    "成交量",
                    "动量",
                    "稳定性",
                    "综合评分",
                    "信号"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )


        # =================================================
        # Top 10 简洁展示
        # =================================================

        st.subheader(
            "⭐ Top 10"
        )


        for _, row in top10.iterrows():

            st.write(
                f"**#{int(row['排名'])} "
                f"{row['股票名称']} "
                f"({row['代码']})** · "
                f"综合评分 **{row['综合评分']:.0f}** · "
                f"{row['信号']}"
            )


        # =================================================
        # 全部结果
        # =================================================

        st.subheader(
            "📊 全部量化结果"
        )


        st.dataframe(
            result_df[
                [
                    "排名",
                    "股票名称",
                    "代码",
                    "日期",
                    "收盘价",
                    "涨跌幅",
                    "趋势",
                    "MACD",
                    "成交量",
                    "动量",
                    "稳定性",
                    "综合评分",
                    "信号"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )


        # =================================================
        # 统计
        # =================================================

        st.subheader(
            "📌 量化统计"
        )


        col1, col2, col3, col4 = st.columns(4)


        with col1:

            st.metric(
                "成功分析",
                len(results)
            )


        with col2:

            st.metric(
                "≥80 强势",
                len(
                    result_df[
                        result_df["综合评分"] >= 80
                    ]
                )
            )


        with col3:

            st.metric(
                "65-79 偏强",
                len(
                    result_df[
                        (
                            result_df["综合评分"] >= 65
                        )
                        &
                        (
                            result_df["综合评分"] < 80
                        )
                    ]
                )
            )


        with col4:

            st.metric(
                "无法分析",
                len(failed)
            )


        # =================================================
        # 下载结果
        # =================================================

        csv = result_df.to_csv(
            index=False,
            encoding="utf-8-sig"
        )


        st.download_button(
            "⬇️ 下载完整量化结果",
            data=csv,
            file_name="quant_result_v3_1.csv",
            mime="text/csv",
            use_container_width=True
        )


        # =================================================
        # 无行情数据
        # =================================================

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
            "请检查 GitHub 的 data/ 文件夹中是否存在行情 CSV。"
        )


# =========================================================
# 单只股票详细分析
# =========================================================

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

    if (
        not stock_code.isdigit()
        or len(stock_code) != 6
    ):

        st.error(
            "请输入6位数字股票代码，例如 600900。"
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


    stock_name = STOCK_NAMES.get(
        stock_code,
        "未知股票"
    )


    st.success(
        f"{stock_name} "
        f"({stock_code}) · "
        f"数据日期："
        f"{latest['日期'].strftime('%Y-%m-%d')}"
    )


    # =====================================================
    # 基础行情
    # =====================================================

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


    # =====================================================
    # 均线趋势
    # =====================================================

    st.subheader(
        "📈 均线趋势"
    )


    if latest["MA5"] > latest["MA20"]:

        st.success(
            "🟢 MA5 > MA20：短期趋势偏强"
        )

    else:

        st.warning(
            "🔴 MA5 < MA20：短期趋势偏弱"
        )


    # =====================================================
    # MACD
    # =====================================================

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


    # =====================================================
    # 动量
    # =====================================================

    st.subheader(
        "🚀 动量"
    )


    col1, col2 = st.columns(2)


    with col1:

        st.metric(
            "5日涨幅",
            f"{latest['RETURN5']:.2f}%"
        )


    with col2:

        st.metric(
            "20日涨幅",
            f"{latest['RETURN20']:.2f}%"
        )


    # =====================================================
    # 成交量
    # =====================================================

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


    # =====================================================
    # 收盘价 + 均线
    # =====================================================

    st.subheader(
        "📉 最近120个交易日"
    )


    chart = df.tail(120)[
        [
            "日期",
            "收盘",
            "MA5",
            "MA10",
            "MA20",
            "MA60"
        ]
    ].set_index(
        "日期"
    )


    st.line_chart(
        chart
    )


    # =====================================================
    # MACD走势
    # =====================================================

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


    # =====================================================
    # 最近30日
    # =====================================================

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
            "DEA",
            "MACD"
        ]
    ]


    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# 页脚
# =========================================================

st.divider()

st.caption(
    "⚠️ 本程序仅用于量化研究、学习和历史数据分析，"
    "不构成投资建议。"
)
