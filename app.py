import streamlit as st
import pandas as pd
import numpy as np
import os


# =========================================================
# 页面设置
# =========================================================

st.set_page_config(
    page_title="A股量化选股助手 V5.0",
    page_icon="📈",
    layout="wide"
)

st.title("📈 A股量化选股助手 V5.0")
st.caption(
    "多因子模型 · 趋势 + 动量 + MACD + 成交量 + 突破 + 风险控制"
)


# =========================================================
# 文件
# =========================================================

STOCK_LIST_FILE = "stock_list.csv"


# =========================================================
# 读取股票池
# =========================================================

@st.cache_data
def load_stock_list():

    if not os.path.exists(STOCK_LIST_FILE):

        return pd.DataFrame(
            columns=["code", "name"]
        )

    df = pd.read_csv(
        STOCK_LIST_FILE,
        dtype={"code": str},
        encoding="utf-8-sig"
    )

    if "code" not in df.columns:

        raise ValueError(
            "stock_list.csv 缺少 code 列"
        )

    if "name" not in df.columns:

        df["name"] = "未知股票"

    df["code"] = (
        df["code"]
        .astype(str)
        .str.strip()
        .str.zfill(6)
    )

    df["name"] = (
        df["name"]
        .fillna("未知股票")
        .astype(str)
        .str.strip()
    )

    df = df[
        [
            "code",
            "name"
        ]
    ]

    df = df.drop_duplicates(
        subset=["code"]
    )

    return df


# =========================================================
# 保存股票池
# =========================================================

def save_stock_list(df):

    df = df.copy()

    df["code"] = (
        df["code"]
        .astype(str)
        .str.strip()
        .str.zfill(6)
    )

    df["name"] = (
        df["name"]
        .fillna("未知股票")
        .astype(str)
        .str.strip()
    )

    df = df.drop_duplicates(
        subset=["code"]
    )

    df.to_csv(
        STOCK_LIST_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    st.cache_data.clear()


# =========================================================
# 初始化股票池
# =========================================================

if "stock_pool" not in st.session_state:

    st.session_state.stock_pool = (
        load_stock_list()
    )


# =========================================================
# 股票池管理
# =========================================================

st.subheader("📋 股票池管理")

st.write(
    "可以直接在这里修改股票代码和中文名称。"
)

edited_pool = st.data_editor(
    st.session_state.stock_pool,
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    column_config={

        "code": st.column_config.TextColumn(
            "股票代码",
            help="6位股票代码"
        ),

        "name": st.column_config.TextColumn(
            "股票名称",
            help="股票中文名称"
        )
    }
)


col1, col2, col3 = st.columns(3)


with col1:

    if st.button(
        "💾 保存股票池",
        type="primary",
        use_container_width=True
    ):

        edited_pool = edited_pool.copy()

        edited_pool["code"] = (
            edited_pool["code"]
            .astype(str)
            .str.strip()
            .str.zfill(6)
        )

        edited_pool["name"] = (
            edited_pool["name"]
            .fillna("未知股票")
            .astype(str)
            .str.strip()
        )

        invalid = edited_pool[
            ~edited_pool["code"].str.match(
                r"^\d{6}$"
            )
        ]

        if not invalid.empty:

            st.error(
                "❌ 股票代码必须是6位数字。"
            )

        else:

            edited_pool = edited_pool.drop_duplicates(
                subset=["code"]
            )

            save_stock_list(
                edited_pool
            )

            st.session_state.stock_pool = (
                edited_pool
            )

            st.success(
                f"✅ 股票池已保存，共 "
                f"{len(edited_pool)} 只股票。"
            )

            st.rerun()


with col2:

    if st.button(
        "🔄 重新读取",
        use_container_width=True
    ):

        st.session_state.stock_pool = (
            load_stock_list()
        )

        st.rerun()


with col3:

    if st.button(
        "🗑️ 清空股票池",
        use_container_width=True
    ):

        st.session_state.stock_pool = pd.DataFrame(
            columns=[
                "code",
                "name"
            ]
        )

        st.rerun()


# =========================================================
# 股票池
# =========================================================

STOCK_LIST = st.session_state.stock_pool.copy()

STOCKS = (
    STOCK_LIST["code"]
    .tolist()
)

STOCK_NAMES = dict(
    zip(
        STOCK_LIST["code"],
        STOCK_LIST["name"]
    )
)

st.info(
    f"📊 当前股票池：{len(STOCKS)} 只股票"
)


# =========================================================
# 读取行情
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

    # -----------------------------------------------------
    # 检查字段
    # -----------------------------------------------------

    required = [
        "日期",
        "收盘"
    ]

    for column in required:

        if column not in df.columns:

            return None

    # -----------------------------------------------------
    # 日期
    # -----------------------------------------------------

    df["日期"] = pd.to_datetime(
        df["日期"],
        errors="coerce"
    )

    # -----------------------------------------------------
    # 数值
    # -----------------------------------------------------

    numeric_columns = [
        "开盘",
        "收盘",
        "最高",
        "最低",
        "成交量"
    ]

    for column in numeric_columns:

        if column in df.columns:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

    # -----------------------------------------------------
    # 如果没有成交量
    # -----------------------------------------------------

    if "成交量" not in df.columns:

        df["成交量"] = np.nan

    # -----------------------------------------------------
    # 清洗
    # -----------------------------------------------------

    df = df.dropna(
        subset=[
            "日期",
            "收盘"
        ]
    )

    df = df.sort_values(
        "日期"
    )

    df = df.drop_duplicates(
        subset=["日期"],
        keep="last"
    )

    df = df.reset_index(
        drop=True
    )

    if len(df) < 60:

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
    # 均线斜率
    # =====================================================

    df["MA20_SLOPE"] = (
        df["MA20"]
        .pct_change(5)
        * 100
    )

    df["MA60_SLOPE"] = (
        df["MA60"]
        .pct_change(10)
        * 100
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

    # MACD柱变化

    df["MACD_CHANGE"] = (
        df["MACD"]
        - df["MACD"].shift(1)
    )

    # =====================================================
    # 成交量
    # =====================================================

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

    df["VOL_RATIO"] = (
        df["成交量"]
        / df["VOL20"]
    )

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

    df["RETURN60"] = (
        df["收盘"]
        .pct_change(60)
        * 100
    )

    # =====================================================
    # 20日最高价
    # =====================================================

    df["HIGH20"] = (
        df["收盘"]
        .rolling(20)
        .max()
        .shift(1)
    )

    # =====================================================
    # 距离20日高点
    # =====================================================

    df["DIST_HIGH20"] = (
        (
            df["收盘"]
            / df["HIGH20"]
        )
        - 1
    ) * 100

    # =====================================================
    # 20日波动率
    # =====================================================

    df["VOLATILITY20"] = (
        df["涨跌幅"]
        .rolling(20)
        .std()
    )

    # =====================================================
    # ATR近似
    # =====================================================

    if all(
        column in df.columns
        for column in [
            "最高",
            "最低"
        ]
    ):

        previous_close = (
            df["收盘"]
            .shift(1)
        )

        tr1 = (
            df["最高"]
            - df["最低"]
        )

        tr2 = (
            df["最高"]
            - previous_close
        ).abs()

        tr3 = (
            df["最低"]
            - previous_close
        ).abs()

        true_range = pd.concat(
            [
                tr1,
                tr2,
                tr3
            ],
            axis=1
        ).max(
            axis=1
        )

        df["ATR14"] = (
            true_range
            .rolling(14)
            .mean()
        )

        df["ATR_PERCENT"] = (
            df["ATR14"]
            / df["收盘"]
            * 100
        )

    else:

        df["ATR14"] = np.nan

        df["ATR_PERCENT"] = np.nan

    return df


# =========================================================
# 安全取值
# =========================================================

def value(row, column, default=np.nan):

    try:

        result = row[column]

        if pd.isna(result):

            return default

        return float(result)

    except Exception:

        return default


# =========================================================
# V5.0 多因子模型
# =========================================================

def analyze_stock(code):

    df = load_stock_data(code)

    if df is None:

        return None

    latest = df.iloc[-1]

    price = value(
        latest,
        "收盘"
    )

    change = value(
        latest,
        "涨跌幅",
        0
    )

    ma5 = value(
        latest,
        "MA5"
    )

    ma20 = value(
        latest,
        "MA20"
    )

    ma60 = value(
        latest,
        "MA60"
    )

    ma20_slope = value(
        latest,
        "MA20_SLOPE"
    )

    ma60_slope = value(
        latest,
        "MA60_SLOPE"
    )

    dif = value(
        latest,
        "DIF"
    )

    dea = value(
        latest,
        "DEA"
    )

    macd = value(
        latest,
        "MACD"
    )

    macd_change = value(
        latest,
        "MACD_CHANGE"
    )

    volume = value(
        latest,
        "成交量"
    )

    volume20 = value(
        latest,
        "VOL20"
    )

    volume_ratio = value(
        latest,
        "VOL_RATIO"
    )

    return5 = value(
        latest,
        "RETURN5"
    )

    return20 = value(
        latest,
        "RETURN20"
    )

    return60 = value(
        latest,
        "RETURN60"
    )

    high20 = value(
        latest,
        "HIGH20"
    )

    dist_high20 = value(
        latest,
        "DIST_HIGH20"
    )

    volatility = value(
        latest,
        "VOLATILITY20"
    )

    atr_percent = value(
        latest,
        "ATR_PERCENT"
    )


    # =====================================================
    # 1. 趋势因子 25分
    # =====================================================

    trend = 0

    if (
        pd.notna(ma5)
        and pd.notna(ma20)
        and ma5 > ma20
    ):

        trend += 7

    if (
        pd.notna(ma20)
        and pd.notna(ma60)
        and ma20 > ma60
    ):

        trend += 7

    if (
        pd.notna(price)
        and pd.notna(ma60)
        and price > ma60
    ):

        trend += 5

    if (
        pd.notna(ma20_slope)
        and ma20_slope > 0
    ):

        trend += 3

    if (
        pd.notna(ma60_slope)
        and ma60_slope > 0
    ):

        trend += 3


    # =====================================================
    # 2. 动量因子 20分
    # =====================================================

    momentum = 0

    if pd.notna(return5):

        if return5 > 0:

            momentum += 5

        if return5 > 3:

            momentum += 2

    if pd.notna(return20):

        if return20 > 0:

            momentum += 6

        if return20 > 5:

            momentum += 2

    if pd.notna(return60):

        if return60 > 0:

            momentum += 5


    momentum = min(
        momentum,
        20
    )


    # =====================================================
    # 3. MACD因子 15分
    # =====================================================

    macd_score = 0

    if (
        pd.notna(dif)
        and pd.notna(dea)
    ):

        if dif > dea:

            macd_score += 7

        if dif > 0:

            macd_score += 5

    if (
        pd.notna(macd_change)
        and macd_change > 0
    ):

        macd_score += 3


    macd_score = min(
        macd_score,
        15
    )


    # =====================================================
    # 4. 成交量因子 15分
    # =====================================================

    volume_score = 0

    volume_available = (
        pd.notna(volume)
        and pd.notna(volume20)
        and volume20 > 0
    )

    if volume_available:

        if volume_ratio > 1.0:

            volume_score += 5

        if volume_ratio >= 1.2:

            volume_score += 5

        if (
            change > 0
            and volume_ratio >= 1.2
        ):

            volume_score += 5

    else:

        # 没有成交量数据时，
        # 不奖励，也不惩罚

        volume_score = 0


    volume_score = min(
        volume_score,
        15
    )


    # =====================================================
    # 5. 突破因子 15分
    # =====================================================

    breakout = 0

    if (
        pd.notna(price)
        and pd.notna(high20)
        and high20 > 0
    ):

        ratio = (
            price / high20
        )

        if ratio >= 1.0:

            breakout += 10

        elif ratio >= 0.97:

            breakout += 6

        elif ratio >= 0.93:

            breakout += 3


    # 突破同时放量

    if (
        breakout >= 10
        and volume_available
        and volume_ratio >= 1.2
    ):

        breakout += 5


    breakout = min(
        breakout,
        15
    )


    # =====================================================
    # 6. 风险因子
    #
    # 风险不是简单加分，而是从总分中扣除
    # =====================================================

    risk_penalty = 0


    # 波动率过高

    if pd.notna(volatility):

        if volatility > 8:

            risk_penalty += 8

        elif volatility > 6:

            risk_penalty += 5

        elif volatility > 4:

            risk_penalty += 2


    # ATR过高

    if pd.notna(atr_percent):

        if atr_percent > 7:

            risk_penalty += 5

        elif atr_percent > 5:

            risk_penalty += 3


    # 短期涨幅过大，防止追高

    if pd.notna(return5):

        if return5 > 15:

            risk_penalty += 6

        elif return5 > 10:

            risk_penalty += 4

        elif return5 > 7:

            risk_penalty += 2


    # 距离20日高点过远

    if pd.notna(dist_high20):

        if dist_high20 < -15:

            risk_penalty += 5

        elif dist_high20 < -10:

            risk_penalty += 3


    risk_penalty = min(
        risk_penalty,
        20
    )


    # =====================================================
    # 最终评分
    # =====================================================

    raw_score = (
        trend
        + momentum
        + macd_score
        + volume_score
        + breakout
    )

    score = max(
        0,
        min(
            100,
            raw_score
            - risk_penalty
        )
    )


    # =====================================================
    # 信号
    # =====================================================

    if score >= 85:

        signal = "🟢 强势"

    elif score >= 75:

        signal = "🟢 偏强"

    elif score >= 60:

        signal = "🟡 观察"

    elif score >= 45:

        signal = "🟠 偏弱"

    else:

        signal = "🔴 弱势"


    # =====================================================
    # 综合判断
    # =====================================================

    if (
        score >= 75
        and trend >= 18
        and macd_score >= 10
    ):

        quality = "⭐⭐⭐⭐ 高质量"

    elif score >= 65:

        quality = "⭐⭐⭐ 中高质量"

    elif score >= 50:

        quality = "⭐⭐ 一般"

    else:

        quality = "⭐ 较弱"


    return {

        "股票名称": STOCK_NAMES.get(
            code,
            "未知股票"
        ),

        "代码": code,

        "日期": latest["日期"],

        "收盘价": price,

        "涨跌幅": change,

        "趋势": trend,

        "动量": momentum,

        "MACD": macd_score,

        "成交量": volume_score,

        "突破": breakout,

        "风险扣分": risk_penalty,

        "综合评分": score,

        "质量": quality,

        "信号": signal,

        "5日涨幅": return5,

        "20日涨幅": return20,

        "60日涨幅": return60,

        "成交量比": volume_ratio,

        "20日波动率": volatility,

        "距离20日高点": dist_high20,

        "MA5": ma5,

        "MA20": ma20,

        "MA60": ma60,

        "DIF": dif,

        "DEA": dea,

        "MACD柱": macd

    }


# =========================================================
# 一键量化
# =========================================================

st.divider()

st.subheader(
    "🚀 V5.0 多因子一键量化"
)

st.write(
    "模型：趋势 25% + 动量 20% + MACD 15% + "
    "成交量 15% + 突破 15% − 风险扣分"
)


if st.button(
    "🚀 开始一键量化",
    type="primary",
    use_container_width=True
):

    if not STOCKS:

        st.error(
            "❌ 股票池为空，请先添加股票。"
        )

        st.stop()


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
            f"— {i + 1}/{total}"
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
        "🎉 V5.0 量化完成！"
    )


    # =====================================================
    # 结果
    # =====================================================

    if results:

        result_df = pd.DataFrame(
            results
        )


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
            "🏆 V5.0 量化 Top 10"
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
                    "综合评分",
                    "质量",
                    "信号",
                    "趋势",
                    "动量",
                    "MACD",
                    "成交量",
                    "突破",
                    "风险扣分"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )


        # =================================================
        # Top 10 快速查看
        # =================================================

        st.subheader(
            "⭐ 强势股票"
        )


        for _, row in top10.iterrows():

            st.write(
                f"**#{int(row['排名'])} "
                f"{row['股票名称']} "
                f"({row['代码']})** · "
                f"评分 **{row['综合评分']:.0f}** · "
                f"{row['质量']} · "
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
                    "综合评分",
                    "质量",
                    "信号",
                    "趋势",
                    "动量",
                    "MACD",
                    "成交量",
                    "突破",
                    "风险扣分",
                    "5日涨幅",
                    "20日涨幅",
                    "60日涨幅",
                    "成交量比",
                    "20日波动率",
                    "距离20日高点"
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
                "≥85 强势",
                len(
                    result_df[
                        result_df["综合评分"] >= 85
                    ]
                )
            )


        with col3:

            st.metric(
                "≥75 偏强",
                len(
                    result_df[
                        result_df["综合评分"] >= 75
                    ]
                )
            )


        with col4:

            st.metric(
                "无法分析",
                len(failed)
            )


        # =================================================
        # 下载
        # =================================================

        csv = result_df.to_csv(
            index=False,
            encoding="utf-8-sig"
        )


        st.download_button(
            "⬇️ 下载完整量化结果",
            data=csv,
            file_name="quant_result_v5.csv",
            mime="text/csv",
            use_container_width=True
        )


        # =================================================
        # 无数据股票
        # =================================================

        if failed:

            with st.expander(
                "⚠️ 没有成功分析的股票"
            ):

                failed_names = [
                    f"{STOCK_NAMES.get(code, '未知股票')} ({code})"
                    for code in failed
                ]

                st.write(
                    failed_names
                )


    else:

        st.error(
            "❌ 没有成功分析任何股票。"
        )

        st.info(
            "请检查 data/ 文件夹中的行情 CSV。"
        )


# =========================================================
# 单股详细分析
# =========================================================

st.divider()

st.subheader(
    "🔎 单只股票详细分析"
)


stock_code = st.text_input(
    "输入6位股票代码",
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
            "请输入6位股票代码。"
        )

        st.stop()


    df = load_stock_data(
        stock_code
    )


    if df is None:

        st.error(
            f"没有找到 {stock_code} 的有效行情数据。"
        )

        st.stop()


    latest = df.iloc[-1]


    stock_name = STOCK_NAMES.get(
        stock_code,
        "未知股票"
    )


    st.success(
        f"{stock_name} ({stock_code}) · "
        f"数据日期："
        f"{latest['日期'].strftime('%Y-%m-%d')}"
    )


    # =====================================================
    # 单股评分
    # =====================================================

    result = analyze_stock(
        stock_code
    )


    if result:

        col1, col2, col3, col4 = st.columns(4)


        with col1:

            st.metric(
                "综合评分",
                f"{result['综合评分']:.0f}"
            )


        with col2:

            st.metric(
                "信号",
                result["信号"]
            )


        with col3:

            st.metric(
                "质量",
                result["质量"]
            )


        with col4:

            st.metric(
                "风险扣分",
                f"{result['风险扣分']:.0f}"
            )


    # =====================================================
    # 基础行情
    # =====================================================

    st.subheader(
        "📈 基础行情"
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
            "MA20",
            f"{latest['MA20']:.2f}"
        )


    with col3:

        st.metric(
            "MA60",
            f"{latest['MA60']:.2f}"
        )


    # =====================================================
    # 多周期趋势
    # =====================================================

    st.subheader(
        "📈 多周期趋势"
    )


    trend_text = []


    if latest["MA5"] > latest["MA20"]:

        trend_text.append(
            "🟢 MA5 > MA20"
        )

    else:

        trend_text.append(
            "🔴 MA5 < MA20"
        )


    if latest["MA20"] > latest["MA60"]:

        trend_text.append(
            "🟢 MA20 > MA60"
        )

    else:

        trend_text.append(
            "🔴 MA20 < MA60"
        )


    if latest["收盘"] > latest["MA60"]:

        trend_text.append(
            "🟢 股价 > MA60"
        )

    else:

        trend_text.append(
            "🔴 股价 < MA60"
        )


    for text in trend_text:

        st.write(text)


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
            "🟢 DIF > DEA"
        )

    else:

        st.warning(
            "🔴 DIF < DEA"
        )


    # =====================================================
    # 动量
    # =====================================================

    st.subheader(
        "🚀 动量"
    )


    col1, col2, col3 = st.columns(3)


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


    with col3:

        st.metric(
            "60日涨幅",
            f"{latest['RETURN60']:.2f}%"
        )


    # =====================================================
    # 成交量
    # =====================================================

    st.subheader(
        "🔊 成交量"
    )


    if (
        pd.notna(latest["VOL20"])
        and latest["VOL20"] > 0
    ):

        col1, col2 = st.columns(2)


        with col1:

            st.metric(
                "最新成交量",
                f"{latest['成交量']:,.0f}"
            )


        with col2:

            st.metric(
                "成交量 / 20日均量",
                f"{latest['VOL_RATIO']:.2f}x"
            )


        if latest["VOL_RATIO"] >= 1.2:

            st.success(
                "🟢 成交量明显放大"
            )

        elif latest["VOL_RATIO"] >= 1:

            st.info(
                "🟡 成交量高于20日均量"
            )

        else:

            st.warning(
                "⚪ 成交量低于20日均量"
            )

    else:

        st.warning(
            "⚠️ 当前行情数据没有有效成交量，"
            "因此成交量因子不会加分。"
        )


    # =====================================================
    # 风险
    # =====================================================

    st.subheader(
        "⚠️ 风险指标"
    )


    col1, col2, col3 = st.columns(3)


    with col1:

        st.metric(
            "20日波动率",
            f"{latest['VOLATILITY20']:.2f}%"
        )


    with col2:

        st.metric(
            "ATR%",
            f"{latest['ATR_PERCENT']:.2f}%"
        )


    with col3:

        st.metric(
            "距离20日高点",
            f"{latest['DIST_HIGH20']:.2f}%"
        )


    # =====================================================
    # 价格 + 均线
    # =====================================================

    st.subheader(
        "📉 最近120个交易日"
    )


    chart = df.tail(120)[
        [
            "日期",
            "收盘",
            "MA5",
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
    # MACD
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
            "MA60",
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

# =========================================================
# V5.1 历史回测
# =========================================================

st.divider()

st.subheader("🧪 V5.1 历史回测")

st.write(
    "测试历史上出现不同量化评分后，"
    "未来5/10/20个交易日的实际表现。"
)


# =========================================================
# 历史评分函数
# =========================================================

def calculate_historical_score(df, i):

    if i < 60:

        return np.nan

    row = df.iloc[i]

    price = value(
        row,
        "收盘"
    )

    ma5 = value(
        row,
        "MA5"
    )

    ma20 = value(
        row,
        "MA20"
    )

    ma60 = value(
        row,
        "MA60"
    )

    ma20_slope = value(
        row,
        "MA20_SLOPE"
    )

    ma60_slope = value(
        row,
        "MA60_SLOPE"
    )

    dif = value(
        row,
        "DIF"
    )

    dea = value(
        row,
        "DEA"
    )

    macd_change = value(
        row,
        "MACD_CHANGE"
    )

    volume = value(
        row,
        "成交量"
    )

    volume20 = value(
        row,
        "VOL20"
    )

    volume_ratio = value(
        row,
        "VOL_RATIO"
    )

    return5 = value(
        row,
        "RETURN5"
    )

    return20 = value(
        row,
        "RETURN20"
    )

    return60 = value(
        row,
        "RETURN60"
    )

    high20 = value(
        row,
        "HIGH20"
    )

    dist_high20 = value(
        row,
        "DIST_HIGH20"
    )

    volatility = value(
        row,
        "VOLATILITY20"
    )

    atr_percent = value(
        row,
        "ATR_PERCENT"
    )


    # =====================================================
    # 趋势 25
    # =====================================================

    trend = 0

    if (
        pd.notna(ma5)
        and pd.notna(ma20)
        and ma5 > ma20
    ):

        trend += 7

    if (
        pd.notna(ma20)
        and pd.notna(ma60)
        and ma20 > ma60
    ):

        trend += 7

    if (
        pd.notna(price)
        and pd.notna(ma60)
        and price > ma60
    ):

        trend += 5

    if (
        pd.notna(ma20_slope)
        and ma20_slope > 0
    ):

        trend += 3

    if (
        pd.notna(ma60_slope)
        and ma60_slope > 0
    ):

        trend += 3


    # =====================================================
    # 动量 20
    # =====================================================

    momentum = 0

    if pd.notna(return5):

        if return5 > 0:

            momentum += 5

        if return5 > 3:

            momentum += 2

    if pd.notna(return20):

        if return20 > 0:

            momentum += 6

        if return20 > 5:

            momentum += 2

    if pd.notna(return60):

        if return60 > 0:

            momentum += 5

    momentum = min(
        momentum,
        20
    )


    # =====================================================
    # MACD 15
    # =====================================================

    macd_score = 0

    if (
        pd.notna(dif)
        and pd.notna(dea)
    ):

        if dif > dea:

            macd_score += 7

        if dif > 0:

            macd_score += 5

    if (
        pd.notna(macd_change)
        and macd_change > 0
    ):

        macd_score += 3

    macd_score = min(
        macd_score,
        15
    )


    # =====================================================
    # 成交量 15
    # =====================================================

    volume_score = 0

    volume_available = (
        pd.notna(volume)
        and pd.notna(volume20)
        and volume20 > 0
    )

    if volume_available:

        if volume_ratio > 1:

            volume_score += 5

        if volume_ratio >= 1.2:

            volume_score += 5

        if (
            row["涨跌幅"] > 0
            and volume_ratio >= 1.2
        ):

            volume_score += 5


    # =====================================================
    # 突破 15
    # =====================================================

    breakout = 0

    if (
        pd.notna(price)
        and pd.notna(high20)
        and high20 > 0
    ):

        ratio = price / high20

        if ratio >= 1:

            breakout += 10

        elif ratio >= 0.97:

            breakout += 6

        elif ratio >= 0.93:

            breakout += 3


    if (
        breakout >= 10
        and volume_available
        and volume_ratio >= 1.2
    ):

        breakout += 5

    breakout = min(
        breakout,
        15
    )


    # =====================================================
    # 风险扣分
    # =====================================================

    risk_penalty = 0

    if pd.notna(volatility):

        if volatility > 8:

            risk_penalty += 8

        elif volatility > 6:

            risk_penalty += 5

        elif volatility > 4:

            risk_penalty += 2


    if pd.notna(atr_percent):

        if atr_percent > 7:

            risk_penalty += 5

        elif atr_percent > 5:

            risk_penalty += 3


    if pd.notna(return5):

        if return5 > 15:

            risk_penalty += 6

        elif return5 > 10:

            risk_penalty += 4

        elif return5 > 7:

            risk_penalty += 2


    if pd.notna(dist_high20):

        if dist_high20 < -15:

            risk_penalty += 5

        elif dist_high20 < -10:

            risk_penalty += 3


    risk_penalty = min(
        risk_penalty,
        20
    )


    # =====================================================
    # 最终评分
    # =====================================================

    score = (
        trend
        + momentum
        + macd_score
        + volume_score
        + breakout
        - risk_penalty
    )

    return max(
        0,
        min(
            100,
            score
        )
    )


# =========================================================
# 单只股票历史回测
# =========================================================

def backtest_stock(
    code,
    holding_days
):

    df = load_stock_data(
        code
    )

    if df is None:

        return pd.DataFrame()


    df = df.copy()

    records = []


    # 至少需要60天指标
    # 同时需要未来 holding_days 天数据

    last_index = (
        len(df)
        - holding_days
    )


    for i in range(
        60,
        last_index
    ):

        score = calculate_historical_score(
            df,
            i
        )


        if pd.isna(score):

            continue


        buy_price = (
            df.iloc[i]["收盘"]
        )

        future_price = (
            df.iloc[
                i + holding_days
            ]["收盘"]
        )


        if (
            pd.isna(buy_price)
            or pd.isna(future_price)
            or buy_price <= 0
        ):

            continue


        future_return = (
            future_price
            / buy_price
            - 1
        ) * 100


        records.append({

            "股票名称": STOCK_NAMES.get(
                code,
                "未知股票"
            ),

            "代码": code,

            "买入日期":
                df.iloc[i]["日期"],

            "评分": score,

            "买入价":
                buy_price,

            "未来收益":
                future_return

        })


    return pd.DataFrame(
        records
    )


# =========================================================
# 运行全部历史回测
# =========================================================

def run_backtest(
    holding_days
):

    all_results = []


    progress = st.progress(
        0
    )

    status = st.empty()


    total = len(STOCKS)


    if total == 0:

        return pd.DataFrame()


    for i, code in enumerate(STOCKS):

        status.write(
            f"正在回测："
            f"{STOCK_NAMES.get(code, '未知股票')} "
            f"({code}) "
            f"— {i + 1}/{total}"
        )


        try:

            result = backtest_stock(
                code,
                holding_days
            )


            if not result.empty:

                all_results.append(
                    result
                )


        except Exception:

            pass


        progress.progress(
            (i + 1) / total
        )


    status.success(
        "✅ 历史回测完成"
    )


    if not all_results:

        return pd.DataFrame()


    return pd.concat(
        all_results,
        ignore_index=True
    )


# =========================================================
# 回测设置
# =========================================================

col1, col2 = st.columns(2)


with col1:

    holding_days = st.selectbox(
        "📅 持有周期",
        [
            5,
            10,
            20
        ],
        format_func=lambda x:
            f"{x}个交易日"
    )


with col2:

    min_score = st.slider(
        "🎯 最低评分",
        min_value=50,
        max_value=90,
        value=70,
        step=5
    )


# =========================================================
# 开始回测
# =========================================================

if st.button(
    "🧪 开始历史回测",
    type="primary",
    use_container_width=True
):

    if not STOCKS:

        st.error(
            "❌ 股票池为空。"
        )

        st.stop()


    with st.spinner(
        "正在进行历史回测，请稍候……"
    ):

        backtest_df = run_backtest(
            holding_days
        )


    if backtest_df.empty:

        st.error(
            "❌ 没有足够的历史数据进行回测。"
        )

        st.stop()


    # =====================================================
    # 筛选评分
    # =====================================================

    selected = backtest_df[
        backtest_df["评分"] >= min_score
    ].copy()


    if selected.empty:

        st.warning(
            f"历史上没有找到评分 ≥ {min_score} "
            f"的样本。"
        )

        st.stop()


    # =====================================================
    # 核心指标
    # =====================================================

    total_trades = len(
        selected
    )


    win_rate = (
        selected["未来收益"] > 0
    ).mean() * 100


    avg_return = (
        selected["未来收益"]
        .mean()
    )


    median_return = (
        selected["未来收益"]
        .median()
    )


    max_return = (
        selected["未来收益"]
        .max()
    )


    min_return = (
        selected["未来收益"]
        .min()
    )


    # =====================================================
    # 显示
    # =====================================================

    st.subheader(
        "📊 回测核心结果"
    )


    col1, col2, col3, col4, col5 = st.columns(5)


    with col1:

        st.metric(
            "历史样本",
            f"{total_trades}"
        )


    with col2:

        st.metric(
            "胜率",
            f"{win_rate:.2f}%"
        )


    with col3:

        st.metric(
            "平均收益",
            f"{avg_return:.2f}%"
        )


    with col4:

        st.metric(
            "中位数收益",
            f"{median_return:.2f}%"
        )


    with col5:

        st.metric(
            "最大收益",
            f"{max_return:.2f}%"
        )


    st.write(
        f"最低收益：**{min_return:.2f}%**"
    )


    # =====================================================
    # 评分分组回测
    # =====================================================

    st.subheader(
        "🎯 不同评分的历史表现"
    )


    bins = [
        0,
        50,
        60,
        70,
        75,
        80,
        85,
        90,
        101
    ]


    labels = [
        "0-49",
        "50-59",
        "60-69",
        "70-74",
        "75-79",
        "80-84",
        "85-89",
        "90-100"
    ]


    backtest_df["评分区间"] = pd.cut(
        backtest_df["评分"],
        bins=bins,
        labels=labels,
        right=False
    )


    grouped = (
        backtest_df
        .groupby(
            "评分区间",
            observed=False
        )
        .agg(
            样本数=("未来收益", "count"),

            胜率=(
                "未来收益",
                lambda x:
                    (x > 0).mean() * 100
            ),

            平均收益=(
                "未来收益",
                "mean"
            ),

            中位数收益=(
                "未来收益",
                "median"
            ),

            最大收益=(
                "未来收益",
                "max"
            ),

            最小收益=(
                "未来收益",
                "min"
            )
        )
        .reset_index()
    )


    st.dataframe(
        grouped,
        use_container_width=True,
        hide_index=True
    )


    # =====================================================
    # 收益曲线
    # =====================================================

    st.subheader(
        "📈 历史收益分布"
    )


    st.bar_chart(
        grouped.set_index(
            "评分区间"
        )[
            [
                "平均收益"
            ]
        ]
    )


    # =====================================================
    # 按股票统计
    # =====================================================

    st.subheader(
        "🏆 各股票历史表现"
    )


    stock_stats = (
        selected
        .groupby(
            [
                "股票名称",
                "代码"
            ]
        )
        .agg(

            样本数=(
                "未来收益",
                "count"
            ),

            胜率=(
                "未来收益",
                lambda x:
                    (x > 0).mean() * 100
            ),

            平均收益=(
                "未来收益",
                "mean"
            ),

            中位数收益=(
                "未来收益",
                "median"
            ),

            最大收益=(
                "未来收益",
                "max"
            ),

            最小收益=(
                "未来收益",
                "min"
            )
        )
        .reset_index()
    )


    stock_stats = stock_stats.sort_values(
        [
            "胜率",
            "平均收益"
        ],
        ascending=[
            False,
            False
        ]
    )


    st.dataframe(
        stock_stats,
        use_container_width=True,
        hide_index=True
    )


    # =====================================================
    # 最近历史信号
    # =====================================================

    st.subheader(
        "🔎 历史高分信号样本"
    )


    recent_signals = (
        selected
        .sort_values(
            "买入日期",
            ascending=False
        )
        .head(50)
    )


    st.dataframe(
        recent_signals[
            [
                "股票名称",
                "代码",
                "买入日期",
                "评分",
                "买入价",
                "未来收益"
            ]
        ],
        use_container_width=True,
        hide_index=True
    )


    # =====================================================
    # 下载
    # =====================================================

    csv = backtest_df.to_csv(
        index=False,
        encoding="utf-8-sig"
    )


    st.download_button(
        "⬇️ 下载完整历史回测数据",
        data=csv,
        file_name=(
            f"backtest_{holding_days}days.csv"
        ),
        mime="text/csv",
        use_container_width=True
    )


    # =====================================================
    # 结论提示
    # =====================================================

    st.subheader(
        "🧠 模型有效性参考"
    )


    if (
        win_rate >= 60
        and avg_return > 0
    ):

        st.success(
            f"当前筛选条件下，历史胜率 "
            f"为 {win_rate:.2f}%，"
            f"平均收益为 {avg_return:.2f}%。"
            "历史样本表现较好，可以继续进行样本外验证。"
        )

    elif (
        win_rate >= 50
        and avg_return > 0
    ):

        st.info(
            f"历史胜率 {win_rate:.2f}%，"
            f"平均收益 {avg_return:.2f}%。"
            "模型存在一定正向效果，但还需要更多样本验证。"
        )

    else:

        st.warning(
            f"历史胜率 {win_rate:.2f}%，"
            f"平均收益 {avg_return:.2f}%。"
            "目前不能证明模型具有稳定优势。"
        )


    st.caption(
        "⚠️ 历史回测不代表未来收益。"
        "回测结果会受到股票池、市场阶段、交易成本、"
        "滑点以及数据质量影响。"
    )

# =========================================================
# V5.2 自动优化因子权重
# =========================================================

st.divider()

st.subheader("🧠 V5.2 自动优化量化模型")

st.write(
    "自动测试不同的趋势、动量、MACD、成交量、突破权重，"
    "寻找训练区间表现较好的组合，并使用后续数据进行验证。"
)


# =========================================================
# V5.2 基础因子计算
# =========================================================

def calculate_factors(df, i):

    if i < 60:
        return None

    row = df.iloc[i]

    price = value(row, "收盘")
    ma5 = value(row, "MA5")
    ma20 = value(row, "MA20")
    ma60 = value(row, "MA60")

    ma20_slope = value(
        row,
        "MA20_SLOPE"
    )

    ma60_slope = value(
        row,
        "MA60_SLOPE"
    )

    dif = value(
        row,
        "DIF"
    )

    dea = value(
        row,
        "DEA"
    )

    macd_change = value(
        row,
        "MACD_CHANGE"
    )

    volume = value(
        row,
        "成交量"
    )

    volume20 = value(
        row,
        "VOL20"
    )

    volume_ratio = value(
        row,
        "VOL_RATIO"
    )

    return5 = value(
        row,
        "RETURN5"
    )

    return20 = value(
        row,
        "RETURN20"
    )

    return60 = value(
        row,
        "RETURN60"
    )

    high20 = value(
        row,
        "HIGH20"
    )

    dist_high20 = value(
        row,
        "DIST_HIGH20"
    )

    volatility = value(
        row,
        "VOLATILITY20"
    )

    atr_percent = value(
        row,
        "ATR_PERCENT"
    )


    # =====================================================
    # 趋势因子
    # =====================================================

    trend = 0

    if (
        pd.notna(ma5)
        and pd.notna(ma20)
        and ma5 > ma20
    ):
        trend += 7

    if (
        pd.notna(ma20)
        and pd.notna(ma60)
        and ma20 > ma60
    ):
        trend += 7

    if (
        pd.notna(price)
        and pd.notna(ma60)
        and price > ma60
    ):
        trend += 5

    if (
        pd.notna(ma20_slope)
        and ma20_slope > 0
    ):
        trend += 3

    if (
        pd.notna(ma60_slope)
        and ma60_slope > 0
    ):
        trend += 3


    # =====================================================
    # 动量
    # =====================================================

    momentum = 0

    if pd.notna(return5):

        if return5 > 0:
            momentum += 5

        if return5 > 3:
            momentum += 2


    if pd.notna(return20):

        if return20 > 0:
            momentum += 6

        if return20 > 5:
            momentum += 2


    if pd.notna(return60):

        if return60 > 0:
            momentum += 5


    momentum = min(
        momentum,
        20
    )


    # =====================================================
    # MACD
    # =====================================================

    macd_score = 0

    if (
        pd.notna(dif)
        and pd.notna(dea)
    ):

        if dif > dea:
            macd_score += 7

        if dif > 0:
            macd_score += 5


    if (
        pd.notna(macd_change)
        and macd_change > 0
    ):

        macd_score += 3


    macd_score = min(
        macd_score,
        15
    )


    # =====================================================
    # 成交量
    # =====================================================

    volume_score = 0

    volume_available = (
        pd.notna(volume)
        and pd.notna(volume20)
        and volume20 > 0
    )

    if volume_available:

        if volume_ratio > 1:
            volume_score += 5

        if volume_ratio >= 1.2:
            volume_score += 5

        if (
            value(
                row,
                "涨跌幅",
                0
            ) > 0
            and volume_ratio >= 1.2
        ):
            volume_score += 5


    volume_score = min(
        volume_score,
        15
    )


    # =====================================================
    # 突破
    # =====================================================

    breakout = 0

    if (
        pd.notna(price)
        and pd.notna(high20)
        and high20 > 0
    ):

        ratio = price / high20

        if ratio >= 1:
            breakout += 10

        elif ratio >= 0.97:
            breakout += 6

        elif ratio >= 0.93:
            breakout += 3


    if (
        breakout >= 10
        and volume_available
        and volume_ratio >= 1.2
    ):

        breakout += 5


    breakout = min(
        breakout,
        15
    )


    # =====================================================
    # 风险
    # =====================================================

    risk = 0


    if pd.notna(volatility):

        if volatility > 8:
            risk += 8

        elif volatility > 6:
            risk += 5

        elif volatility > 4:
            risk += 2


    if pd.notna(atr_percent):

        if atr_percent > 7:
            risk += 5

        elif atr_percent > 5:
            risk += 3


    if pd.notna(return5):

        if return5 > 15:
            risk += 6

        elif return5 > 10:
            risk += 4

        elif return5 > 7:
            risk += 2


    if pd.notna(dist_high20):

        if dist_high20 < -15:
            risk += 5

        elif dist_high20 < -10:
            risk += 3


    risk = min(
        risk,
        20
    )


    return {
        "trend": trend,
        "momentum": momentum,
        "macd": macd_score,
        "volume": volume_score,
        "breakout": breakout,
        "risk": risk
    }


# =========================================================
# 自动评分
# =========================================================

def weighted_score(
    factors,
    weights
):

    total_positive = (
        factors["trend"] * weights["trend"]
        + factors["momentum"] * weights["momentum"]
        + factors["macd"] * weights["macd"]
        + factors["volume"] * weights["volume"]
        + factors["breakout"] * weights["breakout"]
    )


    total_risk = (
        factors["risk"]
        * weights["risk"]
    )


    score = (
        total_positive
        - total_risk
    )


    return max(
        0,
        min(
            100,
            score
        )
    )


# =========================================================
# 生成历史样本
# =========================================================

def build_training_samples(
    holding_days,
    start_ratio=0.0,
    end_ratio=0.7
):

    samples = []


    for code in STOCKS:

        df = load_stock_data(
            code
        )


        if df is None:
            continue


        total = len(df)


        start = max(
            60,
            int(
                total * start_ratio
            )
        )


        end = min(
            total - holding_days,
            int(
                total * end_ratio
            )
        )


        for i in range(
            start,
            end
        ):

            factors = calculate_factors(
                df,
                i
            )


            if factors is None:
                continue


            buy_price = value(
                df.iloc[i],
                "收盘"
            )


            future_price = value(
                df.iloc[
                    i + holding_days
                ],
                "收盘"
            )


            if (
                pd.isna(buy_price)
                or pd.isna(future_price)
                or buy_price <= 0
            ):
                continue


            future_return = (
                future_price
                / buy_price
                - 1
            ) * 100


            samples.append({

                "代码": code,

                "日期":
                    df.iloc[i]["日期"],

                "未来收益":
                    future_return,

                **factors
            })


    return pd.DataFrame(
        samples
    )


# =========================================================
# 验证数据
# =========================================================

def build_validation_samples(
    holding_days,
    start_ratio=0.7
):

    samples = []


    for code in STOCKS:

        df = load_stock_data(
            code
        )


        if df is None:
            continue


        total = len(df)


        start = max(
            60,
            int(
                total * start_ratio
            )
        )


        end = (
            total
            - holding_days
        )


        for i in range(
            start,
            end
        ):

            factors = calculate_factors(
                df,
                i
            )


            if factors is None:
                continue


            buy_price = value(
                df.iloc[i],
                "收盘"
            )


            future_price = value(
                df.iloc[
                    i + holding_days
                ],
                "收盘"
            )


            if (
                pd.isna(buy_price)
                or pd.isna(future_price)
                or buy_price <= 0
            ):
                continue


            future_return = (
                future_price
                / buy_price
                - 1
            ) * 100


            samples.append({

                "代码": code,

                "日期":
                    df.iloc[i]["日期"],

                "未来收益":
                    future_return,

                **factors
            })


    return pd.DataFrame(
        samples
    )


# =========================================================
# 权重组合
# =========================================================

def generate_weight_sets():

    weight_sets = []


    # 基准组合

    base = {
        "trend": 1.0,
        "momentum": 1.0,
        "macd": 1.0,
        "volume": 1.0,
        "breakout": 1.0,
        "risk": 1.0
    }


    weight_sets.append(
        base
    )


    # =====================================================
    # 自动搜索
    #
    # 总体不允许某一个因子无限放大
    # =====================================================

    values = [
        0.6,
        0.8,
        1.0,
        1.2,
        1.4
    ]


    for trend in values:

        for momentum in values:

            for macd in values:

                for volume in values:

                    for breakout in values:

                        weights = {

                            "trend": trend,

                            "momentum": momentum,

                            "macd": macd,

                            "volume": volume,

                            "breakout": breakout,

                            "risk": 1.0
                        }


                        average = (
                            trend
                            + momentum
                            + macd
                            + volume
                            + breakout
                        ) / 5


                        # 防止所有权重同时偏高
                        if (
                            0.85
                            <= average
                            <= 1.15
                        ):

                            weight_sets.append(
                                weights
                            )


    # 去重

    unique = []

    seen = set()


    for w in weight_sets:

        key = tuple(
            round(
                w[k],
                2
            )
            for k in [
                "trend",
                "momentum",
                "macd",
                "volume",
                "breakout",
                "risk"
            ]
        )


        if key not in seen:

            seen.add(key)

            unique.append(
                w
            )


    return unique


# =========================================================
# 评价权重
# =========================================================

def evaluate_weights(
    samples,
    weights
):

    if samples.empty:

        return None


    scores = []


    returns = []


    for _, row in samples.iterrows():

        factors = {

            "trend": row["trend"],

            "momentum": row["momentum"],

            "macd": row["macd"],

            "volume": row["volume"],

            "breakout": row["breakout"],

            "risk": row["risk"]
        }


        score = weighted_score(
            factors,
            weights
        )


        scores.append(
            score
        )

        returns.append(
            row["未来收益"]
        )


    temp = samples.copy()

    temp["评分"] = scores


    # 只关注高分信号

    selected = temp[
        temp["评分"] >= 75
    ]


    if len(selected) < 10:

        return None


    avg_return = (
        selected["未来收益"]
        .mean()
    )


    win_rate = (
        selected["未来收益"] > 0
    ).mean()


    median_return = (
        selected["未来收益"]
        .median()
    )


    # 收益波动惩罚

    return_std = (
        selected["未来收益"]
        .std()
    )


    if pd.isna(return_std):

        return_std = 0


    # =====================================================
    # 综合优化目标
    #
    # 平均收益
    # + 胜率
    # + 中位数收益
    # - 收益波动
    # =====================================================

    objective = (

        avg_return * 0.45

        + win_rate * 100 * 0.35

        + median_return * 0.20

        - return_std * 0.10
    )


    return {

        "objective": objective,

        "平均收益": avg_return,

        "胜率": win_rate * 100,

        "中位数收益": median_return,

        "样本数": len(selected),

        "收益波动": return_std,

        "weights": weights
    }


# =========================================================
# V5.2 自动优化
# =========================================================

st.subheader(
    "⚙️ 自动寻找更优权重"
)


col1, col2 = st.columns(2)


with col1:

    v52_holding_days = st.selectbox(
        "回测周期",
        [
            5,
            10,
            20
        ],
        index=0,
        format_func=lambda x:
            f"{x}个交易日",
        key="v52_holding"
    )


with col2:

    v52_min_samples = st.number_input(
        "最低高分样本数",
        min_value=10,
        max_value=500,
        value=20,
        step=10
    )


if st.button(
    "🧠 开始自动优化权重",
    type="primary",
    use_container_width=True
):

    if len(STOCKS) == 0:

        st.error(
            "❌ 股票池为空。"
        )

        st.stop()


    with st.spinner(
        "正在准备历史训练数据……"
    ):

        training = build_training_samples(
            v52_holding_days,
            start_ratio=0.0,
            end_ratio=0.7
        )


    if training.empty:

        st.error(
            "❌ 没有足够的历史数据。"
        )

        st.stop()


    st.info(
        f"训练样本：{len(training)} 条"
    )


    weight_sets = (
        generate_weight_sets()
    )


    st.write(
        f"正在测试 {len(weight_sets)} "
        "组权重组合……"
    )


    optimization_results = []


    progress = st.progress(
        0
    )


    for i, weights in enumerate(
        weight_sets
    ):

        result = evaluate_weights(
            training,
            weights
        )


        if result is not None:

            optimization_results.append(
                result
            )


        progress.progress(
            (i + 1)
            / len(weight_sets)
        )


    if not optimization_results:

        st.error(
            "❌ 没有找到足够有效的权重组合。"
        )

        st.stop()


    # =====================================================
    # 排序
    # =====================================================

    optimization_results = sorted(
        optimization_results,
        key=lambda x:
            x["objective"],
        reverse=True
    )


    best = (
        optimization_results[0]
    )


    best_weights = (
        best["weights"]
    )


    # =====================================================
    # 最佳权重
    # =====================================================

    st.success(
        "🎯 自动优化完成！"
    )


    st.subheader(
        "🏆 最佳权重"
    )


    col1, col2, col3 = st.columns(3)


    with col1:

        st.metric(
            "趋势",
            f"{best_weights['trend']:.1f}"
        )


    with col2:

        st.metric(
            "动量",
            f"{best_weights['momentum']:.1f}"
        )


    with col3:

        st.metric(
            "MACD",
            f"{best_weights['macd']:.1f}"
        )


    col1, col2, col3 = st.columns(3)


    with col1:

        st.metric(
            "成交量",
            f"{best_weights['volume']:.1f}"
        )


    with col2:

        st.metric(
            "突破",
            f"{best_weights['breakout']:.1f}"
        )


    with col3:

        st.metric(
            "风险",
            f"{best_weights['risk']:.1f}"
        )


    # =====================================================
    # 训练集表现
    # =====================================================

    st.subheader(
        "📚 训练区间表现"
    )


    col1, col2, col3, col4 = st.columns(4)


    with col1:

        st.metric(
            "高分样本",
            best["样本数"]
        )


    with col2:

        st.metric(
            "胜率",
            f"{best['胜率']:.2f}%"
        )


    with col3:

        st.metric(
            "平均收益",
            f"{best['平均收益']:.2f}%"
        )


    with col4:

        st.metric(
            "中位数收益",
            f"{best['中位数收益']:.2f}%"
        )


    # =====================================================
    # 样本外验证
    # =====================================================

    st.subheader(
        "🧪 样本外验证"
    )


    with st.spinner(
        "正在使用后30%的历史数据验证最佳权重……"
    ):

        validation = (
            build_validation_samples(
                v52_holding_days,
                start_ratio=0.7
            )
        )


    if validation.empty:

        st.warning(
            "⚠️ 没有足够的样本外数据。"
        )

    else:

        validation_scores = []


        for _, row in validation.iterrows():

            factors = {

                "trend": row["trend"],

                "momentum": row["momentum"],

                "macd": row["macd"],

                "volume": row["volume"],

                "breakout": row["breakout"],

                "risk": row["risk"]
            }


            score = weighted_score(
                factors,
                best_weights
            )


            validation_scores.append(
                score
            )


        validation = validation.copy()

        validation["评分"] = (
            validation_scores
        )


        validation_selected = (
            validation[
                validation["评分"] >= 75
            ]
        )


        if len(
            validation_selected
        ) < v52_min_samples:

            st.warning(
                "⚠️ 样本外高分信号数量较少，"
                "验证结果可信度有限。"
            )


        if not validation_selected.empty:

            val_win_rate = (
                validation_selected[
                    "未来收益"
                ] > 0
            ).mean() * 100


            val_avg_return = (
                validation_selected[
                    "未来收益"
                ].mean()
            )


            val_median_return = (
                validation_selected[
                    "未来收益"
                ].median()
            )


            val_min_return = (
                validation_selected[
                    "未来收益"
                ].min()
            )


            col1, col2, col3, col4 = st.columns(4)


            with col1:

                st.metric(
                    "验证样本",
                    len(
                        validation_selected
                    )
                )


            with col2:

                st.metric(
                    "验证胜率",
                    f"{val_win_rate:.2f}%"
                )


            with col3:

                st.metric(
                    "验证平均收益",
                    f"{val_avg_return:.2f}%"
                )


            with col4:

                st.metric(
                    "验证最低收益",
                    f"{val_min_return:.2f}%"
                )


            # =================================================
            # 验证判断
            # =================================================

            if (
                val_win_rate >= 55
                and val_avg_return > 0
            ):

                st.success(
                    "🟢 样本外验证表现为正，"
                    "说明自动优化后的权重在未参与训练的数据上"
                    "仍然存在一定统计优势。"
                )

            elif (
                val_avg_return > 0
            ):

                st.info(
                    "🟡 样本外平均收益为正，"
                    "但优势较弱，需要更多数据验证。"
                )

            else:

                st.error(
                    "🔴 样本外表现没有显示稳定优势。"
                    "不要直接把训练集上的最佳权重当成最终模型。"
                )


            # =================================================
            # 验证样本
            # =================================================

            st.subheader(
                "📋 样本外验证记录"
            )


            st.dataframe(
                validation_selected.sort_values(
                    "评分",
                    ascending=False
                ).head(100)[
                    [
                        "代码",
                        "日期",
                        "评分",
                        "未来收益"
                    ]
                ],
                use_container_width=True,
                hide_index=True
            )


    # =====================================================
    # 权重排名
    # =====================================================

    st.subheader(
        "🥇 最佳权重组合 Top 10"
    )


    rows = []


    for item in optimization_results[:10]:

        w = item["weights"]


        rows.append({

            "趋势权重":
                w["trend"],

            "动量权重":
                w["momentum"],

            "MACD权重":
                w["macd"],

            "成交量权重":
                w["volume"],

            "突破权重":
                w["breakout"],

            "风险权重":
                w["risk"],

            "训练胜率":
                item["胜率"],

            "训练平均收益":
                item["平均收益"],

            "训练样本":
                item["样本数"],

            "优化得分":
                item["objective"]
        })


    top_weights_df = pd.DataFrame(
        rows
    )


    st.dataframe(
        top_weights_df,
        use_container_width=True,
        hide_index=True
    )


    # =====================================================
    # 保存最佳权重
    # =====================================================

    weights_df = pd.DataFrame([
        best_weights
    ])


    weights_csv = (
        weights_df.to_csv(
            index=False,
            encoding="utf-8-sig"
        )
    )


    st.download_button(
        "⬇️ 下载最佳权重",
        data=weights_csv,
        file_name="best_weights_v52.csv",
        mime="text/csv",
        use_container_width=True
    )


    st.caption(
        "⚠️ V5.2 使用前70%历史数据寻找权重，"
        "后30%数据进行样本外验证。"
        "这比直接用全部历史数据寻找最优权重更可靠，"
        "但仍不能保证未来收益。"
    )
