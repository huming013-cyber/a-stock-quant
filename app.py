import streamlit as st
import pandas as pd
import numpy as np
import os
from itertools import product


# =========================================================
# 页面设置
# =========================================================

st.set_page_config(
    page_title="A股量化选股助手 V5.4",
    page_icon="📈",
    layout="wide"
)

st.title("📈 A股量化选股助手 V5.4")

st.caption(
    "V5.4 · 中文名称 · 多因子评分 · 自动优化 · "
    "Walk-Forward · 样本外回测 · 加速版"
)


# =========================================================
# 文件
# =========================================================

STOCK_LIST_FILE = "stock_list.csv"


# =========================================================
# 股票列表
# =========================================================

@st.cache_data
def load_stock_list():

    if not os.path.exists(STOCK_LIST_FILE):
        return pd.DataFrame(
            columns=["code", "name"]
        )

    df = pd.read_csv(
        STOCK_LIST_FILE,
        dtype={"code": str}
    )

    if "code" not in df.columns:
        raise ValueError(
            "stock_list.csv 必须包含 code 列"
        )

    df["code"] = (
        df["code"]
        .astype(str)
        .str.extract(r"(\d{6})")[0]
    )

    if "name" not in df.columns:

        if "名称" in df.columns:
            df["name"] = df["名称"]

        elif "股票名称" in df.columns:
            df["name"] = df["股票名称"]

        else:
            df["name"] = "未知股票"

    df["name"] = (
        df["name"]
        .fillna("未知股票")
        .astype(str)
    )

    df = df.dropna(
        subset=["code"]
    )

    df = df.drop_duplicates(
        subset=["code"]
    )

    return df[
        ["code", "name"]
    ].reset_index(drop=True)


stock_list = load_stock_list()

STOCK_NAMES = dict(
    zip(
        stock_list["code"],
        stock_list["name"]
    )
)

ALL_STOCKS = stock_list[
    "code"
].tolist()


# =========================================================
# 行情读取
# =========================================================

@st.cache_data
def load_stock_data(code):

    filename = f"data/{code}.csv"

    if not os.path.exists(filename):

        raise FileNotFoundError(
            f"没有找到 {code}.csv"
        )

    df = pd.read_csv(
        filename
    )

    required = [
        "日期",
        "开盘",
        "收盘",
        "最高",
        "最低",
        "成交量"
    ]

    missing = [
        x
        for x in required
        if x not in df.columns
    ]

    if missing:

        raise ValueError(
            f"{code}.csv 缺少字段：{missing}"
        )

    df["日期"] = pd.to_datetime(
        df["日期"],
        errors="coerce"
    )

    for column in [
        "开盘",
        "收盘",
        "最高",
        "最低",
        "成交量"
    ]:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

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
        subset=["日期"]
    )

    df = df.reset_index(
        drop=True
    )

    return df


# =========================================================
# 技术指标
# =========================================================

@st.cache_data
def calculate_indicators(df):

    df = df.copy()

    close = df["收盘"]

    volume = df["成交量"]

    # -----------------------------------------------------
    # 收益率
    # -----------------------------------------------------

    df["涨跌幅"] = (
        close.pct_change()
        * 100
    )

    df["RETURN5"] = (
        close.pct_change(5)
        * 100
    )

    df["RETURN20"] = (
        close.pct_change(20)
        * 100
    )

    df["RETURN60"] = (
        close.pct_change(60)
        * 100
    )

    # -----------------------------------------------------
    # MA
    # -----------------------------------------------------

    df["MA5"] = (
        close
        .rolling(5)
        .mean()
    )

    df["MA10"] = (
        close
        .rolling(10)
        .mean()
    )

    df["MA20"] = (
        close
        .rolling(20)
        .mean()
    )

    df["MA60"] = (
        close
        .rolling(60)
        .mean()
    )

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

    # -----------------------------------------------------
    # MACD
    # -----------------------------------------------------

    ema12 = (
        close
        .ewm(
            span=12,
            adjust=False
        )
        .mean()
    )

    ema26 = (
        close
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

    df["MACD_CHANGE"] = (
        df["MACD"].diff()
    )

    # -----------------------------------------------------
    # 成交量
    # -----------------------------------------------------

    df["VOL5"] = (
        volume
        .rolling(5)
        .mean()
    )

    df["VOL20"] = (
        volume
        .rolling(20)
        .mean()
    )

    df["VOL_RATIO"] = (
        volume
        / df["VOL20"]
    )

    # -----------------------------------------------------
    # 突破
    # -----------------------------------------------------

    df["HIGH20"] = (
        df["最高"]
        .rolling(20)
        .max()
        .shift(1)
    )

    df["DIST_HIGH20"] = (
        close
        / df["HIGH20"]
        - 1
    ) * 100

    # -----------------------------------------------------
    # 波动率
    # -----------------------------------------------------

    df["VOLATILITY20"] = (
        df["涨跌幅"]
        .rolling(20)
        .std()
    )

    # -----------------------------------------------------
    # ATR
    # -----------------------------------------------------

    previous_close = (
        close.shift(1)
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
    ).max(axis=1)

    df["ATR14"] = (
        true_range
        .rolling(14)
        .mean()
    )

    df["ATR_PERCENT"] = (
        df["ATR14"]
        / close
        * 100
    )

    return df


# =========================================================
# 向量化因子
# =========================================================

def create_factor_scores(df):

    result = pd.DataFrame(
        index=df.index
    )

    # -----------------------------------------------------
    # 趋势
    # -----------------------------------------------------

    trend = np.zeros(
        len(df)
    )

    trend += np.where(
        df["MA5"] > df["MA20"],
        7,
        0
    )

    trend += np.where(
        df["MA20"] > df["MA60"],
        7,
        0
    )

    trend += np.where(
        df["收盘"] > df["MA60"],
        5,
        0
    )

    trend += np.where(
        df["MA20_SLOPE"] > 0,
        3,
        0
    )

    trend += np.where(
        df["MA60_SLOPE"] > 0,
        3,
        0
    )

    result["trend"] = trend

    # -----------------------------------------------------
    # 动量
    # -----------------------------------------------------

    momentum = np.zeros(
        len(df)
    )

    momentum += np.where(
        df["RETURN5"] > 0,
        5,
        0
    )

    momentum += np.where(
        df["RETURN5"] > 3,
        2,
        0
    )

    momentum += np.where(
        df["RETURN20"] > 0,
        6,
        0
    )

    momentum += np.where(
        df["RETURN20"] > 5,
        2,
        0
    )

    momentum += np.where(
        df["RETURN60"] > 0,
        5,
        0
    )

    result["momentum"] = np.minimum(
        momentum,
        20
    )

    # -----------------------------------------------------
    # MACD
    # -----------------------------------------------------

    macd = np.zeros(
        len(df)
    )

    macd += np.where(
        df["DIF"] > df["DEA"],
        7,
        0
    )

    macd += np.where(
        df["DIF"] > 0,
        5,
        0
    )

    macd += np.where(
        df["MACD_CHANGE"] > 0,
        3,
        0
    )

    result["macd"] = np.minimum(
        macd,
        15
    )

    # -----------------------------------------------------
    # 成交量
    # -----------------------------------------------------

    volume_score = np.zeros(
        len(df)
    )

    volume_score += np.where(
        df["VOL_RATIO"] > 1,
        5,
        0
    )

    volume_score += np.where(
        df["VOL_RATIO"] >= 1.2,
        5,
        0
    )

    volume_score += np.where(
        (
            (df["涨跌幅"] > 0)
            &
            (df["VOL_RATIO"] >= 1.2)
        ),
        5,
        0
    )

    result["volume"] = np.minimum(
        volume_score,
        15
    )

    # -----------------------------------------------------
    # 突破
    # -----------------------------------------------------

    breakout = np.zeros(
        len(df)
    )

    ratio = (
        df["收盘"]
        / df["HIGH20"]
    )

    breakout += np.where(
        ratio >= 1,
        10,
        0
    )

    breakout += np.where(
        (
            (ratio >= 0.97)
            &
            (ratio < 1)
        ),
        6,
        0
    )

    breakout += np.where(
        (
            (ratio >= 0.93)
            &
            (ratio < 0.97)
        ),
        3,
        0
    )

    breakout += np.where(
        (
            (breakout >= 10)
            &
            (df["VOL_RATIO"] >= 1.2)
        ),
        5,
        0
    )

    result["breakout"] = np.minimum(
        breakout,
        15
    )

    # -----------------------------------------------------
    # 风险
    # -----------------------------------------------------

    risk = np.zeros(
        len(df)
    )

    risk += np.where(
        df["VOLATILITY20"] > 8,
        8,
        np.where(
            df["VOLATILITY20"] > 6,
            5,
            np.where(
                df["VOLATILITY20"] > 4,
                2,
                0
            )
        )
    )

    risk += np.where(
        df["ATR_PERCENT"] > 7,
        5,
        np.where(
            df["ATR_PERCENT"] > 5,
            3,
            0
        )
    )

    risk += np.where(
        df["RETURN5"] > 15,
        6,
        np.where(
            df["RETURN5"] > 10,
            4,
            np.where(
                df["RETURN5"] > 7,
                2,
                0
            )
        )
    )

    risk += np.where(
        df["DIST_HIGH20"] < -15,
        5,
        np.where(
            df["DIST_HIGH20"] < -10,
            3,
            0
        )
    )

    result["risk"] = np.minimum(
        risk,
        20
    )

    return result


# =========================================================
# 计算综合评分
# =========================================================

def calculate_score(
    factors,
    weights
):

    positive = (

        factors["trend"]
        * weights[0]

        +

        factors["momentum"]
        * weights[1]

        +

        factors["macd"]
        * weights[2]

        +

        factors["volume"]
        * weights[3]

        +

        factors["breakout"]
        * weights[4]
    )

    risk_penalty = (
        factors["risk"]
        * weights[5]
    )

    raw = (
        positive
        - risk_penalty
    )

    max_score = (

        25 * weights[0]
        +

        20 * weights[1]
        +

        15 * weights[2]
        +

        15 * weights[3]
        +

        15 * weights[4]
    )

    score = (
        raw
        / max_score
        * 100
    )

    return score


# =========================================================
# 权重候选
# =========================================================

def create_weight_candidates():

    candidates = []

    # V5.4 不再生成数万种组合
    # 使用少量有意义的组合

    presets = [

        (1.2, 1.0, 1.0, 0.8, 1.0, 1.0),

        (1.0, 1.2, 1.0, 0.8, 1.0, 1.0),

        (1.0, 1.0, 1.2, 0.8, 1.0, 1.0),

        (1.0, 1.0, 1.0, 1.2, 1.0, 1.0),

        (1.0, 1.0, 1.0, 1.0, 1.2, 1.0),

        (1.2, 1.2, 1.0, 0.8, 1.0, 1.0),

        (1.2, 1.0, 1.2, 0.8, 1.0, 1.0),

        (1.0, 1.2, 1.2, 1.0, 1.0, 1.0),

        (1.1, 1.1, 1.0, 1.0, 1.1, 1.0),

        (1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
    ]

    for p in presets:

        candidates.append(
            np.array(
                p,
                dtype=float
            )
        )

    return candidates


# =========================================================
# 自动优化
# =========================================================

def optimize_weights(
    samples,
    minimum_samples=20
):

    if samples.empty:

        return None

    best = None

    factor_matrix = samples[
        [
            "trend",
            "momentum",
            "macd",
            "volume",
            "breakout",
            "risk"
        ]
    ].values

    future_returns = (
        samples[
            "未来收益"
        ].values
    )

    for weights in create_weight_candidates():

        scores = calculate_score(
            {
                "trend":
                    factor_matrix[:, 0],

                "momentum":
                    factor_matrix[:, 1],

                "macd":
                    factor_matrix[:, 2],

                "volume":
                    factor_matrix[:, 3],

                "breakout":
                    factor_matrix[:, 4],

                "risk":
                    factor_matrix[:, 5]
            },
            weights
        )

        selected = (
            scores >= 75
        )

        if (
            selected.sum()
            < minimum_samples
        ):
            continue

        returns = (
            future_returns[
                selected
            ]
        )

        avg_return = (
            np.mean(returns)
        )

        median_return = (
            np.median(returns)
        )

        win_rate = (
            np.mean(
                returns > 0
            )
            * 100
        )

        objective = (
            avg_return * 0.45
            +
            median_return * 0.20
            +
            win_rate * 0.25
        )

        if (
            best is None
            or objective
            > best["objective"]
        ):

            best = {

                "objective":
                    objective,

                "平均收益":
                    avg_return,

                "中位数收益":
                    median_return,

                "胜率":
                    win_rate,

                "样本数":
                    int(
                        selected.sum()
                    ),

                "weights":
                    weights
            }

    return best


# =========================================================
# 建立回测样本
# =========================================================

def create_samples(
    df,
    code,
    holding_days,
    start,
    end
):

    if end <= start:

        return pd.DataFrame()

    future_close = (
        df["收盘"]
        .shift(
            -holding_days
        )
    )

    future_return = (
        future_close
        / df["收盘"]
        - 1
    ) * 100

    factors = create_factor_scores(
        df
    )

    samples = factors.copy()

    samples["代码"] = code

    samples["日期"] = (
        df["日期"]
    )

    samples["未来收益"] = (
        future_return
    )

    samples = samples.iloc[
        start:end
    ]

    samples = samples.dropna()

    return samples


# =========================================================
# 单股票 Walk Forward
# =========================================================

def walk_forward_stock(
    code,
    holding_days,
    train_ratio,
    minimum_samples,
    fee,
    slippage
):

    try:

        df = load_stock_data(
            code
        )

        df = calculate_indicators(
            df
        )

    except Exception:

        return (
            pd.DataFrame(),
            None
        )

    total = len(df)

    if total < 250:

        return (
            pd.DataFrame(),
            None
        )

    train_end = int(
        total
        * train_ratio
    )

    validation_start = train_end

    validation_end = (
        total
        - holding_days
    )

    train_samples = create_samples(
        df,
        code,
        holding_days,
        60,
        train_end
    )

    if (
        len(train_samples)
        < minimum_samples
    ):

        return (
            pd.DataFrame(),
            None
        )

    best = optimize_weights(
        train_samples,
        minimum_samples
    )

    if best is None:

        return (
            pd.DataFrame(),
            None
        )

    validation_samples = create_samples(
        df,
        code,
        holding_days,
        validation_start,
        validation_end
    )

    if validation_samples.empty:

        return (
            pd.DataFrame(),
            best
        )

    factors = {

        "trend":
            validation_samples[
                "trend"
            ].values,

        "momentum":
            validation_samples[
                "momentum"
            ].values,

        "macd":
            validation_samples[
                "macd"
            ].values,

        "volume":
            validation_samples[
                "volume"
            ].values,

        "breakout":
            validation_samples[
                "breakout"
            ].values,

        "risk":
            validation_samples[
                "risk"
            ].values
    }

    scores = calculate_score(
        factors,
        best["weights"]
    )

    validation_samples[
        "评分"
    ] = scores

    validation_samples = (
        validation_samples[
            validation_samples["评分"]
            >= 75
        ]
        .copy()
    )

    if validation_samples.empty:

        return (
            pd.DataFrame(),
            best
        )

    cost = (
        fee * 2
        +
        slippage * 2
    ) * 100

    validation_samples[
        "净收益"
    ] = (
        validation_samples[
            "未来收益"
        ]
        - cost
    )

    validation_samples[
        "股票名称"
    ] = STOCK_NAMES.get(
        code,
        "未知股票"
    )

    return (
        validation_samples,
        best
    )


# =========================================================
# 全股票回测
# =========================================================

def run_backtest(
    selected_stocks,
    holding_days,
    train_ratio,
    minimum_samples,
    fee,
    slippage
):

    all_results = []

    weight_records = []

    progress = st.progress(
        0
    )

    status = st.empty()

    total = len(
        selected_stocks
    )

    for index, code in enumerate(
        selected_stocks
    ):

        status.write(
            f"正在分析："
            f"{STOCK_NAMES.get(code, '未知股票')} "
            f"({code}) "
            f"{index + 1}/{total}"
        )

        result, best = (
            walk_forward_stock(
                code,
                holding_days,
                train_ratio,
                minimum_samples,
                fee,
                slippage
            )
        )

        if not result.empty:

            all_results.append(
                result
            )

        if best is not None:

            weights = best[
                "weights"
            ]

            weight_records.append({

                "代码":
                    code,

                "股票名称":
                    STOCK_NAMES.get(
                        code,
                        "未知股票"
                    ),

                "训练样本":
                    best["样本数"],

                "训练胜率":
                    best["胜率"],

                "训练平均收益":
                    best["平均收益"],

                "趋势":
                    weights[0],

                "动量":
                    weights[1],

                "MACD":
                    weights[2],

                "成交量":
                    weights[3],

                "突破":
                    weights[4],

                "风险":
                    weights[5]
            })

        progress.progress(
            int(
                (
                    index + 1
                )
                / total
                * 100
            )
        )

    status.write(
        "✅ 分析完成"
    )

    if all_results:

        results = pd.concat(
            all_results,
            ignore_index=True
        )

    else:

        results = pd.DataFrame()

    weights_df = pd.DataFrame(
        weight_records
    )

    return (
        results,
        weights_df
    )


# =========================================================
# 回测统计
# =========================================================

def calculate_performance(
    results
):

    if results.empty:

        return None

    returns = (
        results[
            "净收益"
        ]
        / 100
    )

    equity = (
        1 + returns
    ).cumprod()

    peak = (
        equity
        .cummax()
    )

    drawdown = (
        equity
        / peak
        - 1
    )

    volatility = (
        returns.std()
    )

    if (
        pd.isna(volatility)
        or volatility == 0
    ):

        sharpe = 0

    else:

        sharpe = (
            returns.mean()
            / volatility
            * np.sqrt(
                len(returns)
            )
        )

    return {

        "样本数":
            len(results),

        "胜率":
            (
                returns > 0
            ).mean() * 100,

        "平均收益":
            returns.mean() * 100,

        "中位数收益":
            returns.median() * 100,

        "累计收益":
            (
                equity.iloc[-1]
                - 1
            ) * 100,

        "最大回撤":
            drawdown.min() * 100,

        "夏普":
            sharpe,

        "最大盈利":
            results[
                "净收益"
            ].max(),

        "最大亏损":
            results[
                "净收益"
            ].min()
    }


# =========================================================
# 页面：股票池
# =========================================================

st.sidebar.header(
    "📋 股票池"
)

st.sidebar.write(
    f"CSV股票数量：{len(ALL_STOCKS)}"
)

if len(ALL_STOCKS) > 0:

    mode = st.sidebar.radio(
        "选择分析方式",
        [
            "全部股票",
            "前20只",
            "前50只",
            "自定义股票"
        ]
    )

else:

    mode = "全部股票"


if mode == "全部股票":

    selected_stocks = ALL_STOCKS

elif mode == "前20只":

    selected_stocks = (
        ALL_STOCKS[:20]
    )

elif mode == "前50只":

    selected_stocks = (
        ALL_STOCKS[:50]
    )

else:

    selected_stocks = st.sidebar.multiselect(
        "选择股票",
        ALL_STOCKS,
        format_func=lambda x:
            f"{STOCK_NAMES.get(x, '未知股票')} ({x})"
    )


st.sidebar.write(
    f"本次选择：**{len(selected_stocks)}** 只"
)


# =========================================================
# 单只股票
# =========================================================

st.subheader(
    "🔎 单只股票分析"
)

single_code = st.text_input(
    "输入股票代码",
    value="600900"
).strip()


if st.button(
    "开始单股分析",
    type="primary"
):

    if (
        not single_code.isdigit()
        or len(single_code) != 6
    ):

        st.error(
            "请输入6位股票代码，例如600900"
        )

        st.stop()

    try:

        df = load_stock_data(
            single_code
        )

        df = calculate_indicators(
            df
        )

    except Exception as e:

        st.error(
            "读取股票数据失败"
        )

        st.code(
            str(e)
        )

        st.stop()

    factors_df = create_factor_scores(
        df
    )

    latest_factors = (
        factors_df.iloc[-1]
    )

    weights = np.array(
        [
            1,
            1,
            1,
            1,
            1,
            1
        ]
    )

    score = calculate_score(
        {
            "trend":
                np.array(
                    [latest_factors["trend"]]
                ),

            "momentum":
                np.array(
                    [latest_factors["momentum"]]
                ),

            "macd":
                np.array(
                    [latest_factors["macd"]]
                ),

            "volume":
                np.array(
                    [latest_factors["volume"]]
                ),

            "breakout":
                np.array(
                    [latest_factors["breakout"]]
                ),

            "risk":
                np.array(
                    [latest_factors["risk"]]
                )
        },
        weights
    )[0]

    latest = df.iloc[-1]

    name = STOCK_NAMES.get(
        single_code,
        "未知股票"
    )

    st.success(
        f"📌 {name}（{single_code}）"
        f" · {latest['日期'].strftime('%Y-%m-%d')}"
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "收盘价",
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
            "MACD",
            f"{latest['MACD']:.3f}"
        )

    with col4:

        st.metric(
            "量化评分",
            f"{score:.1f}"
        )

    if score >= 80:

        st.success(
            "🟢 强势"
        )

    elif score >= 70:

        st.info(
            "🟡 偏强"
        )

    elif score >= 60:

        st.warning(
            "🟠 中性"
        )

    else:

        st.error(
            "🔴 偏弱"
        )

    st.subheader(
        "📈 均线"
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


# =========================================================
# V5.4 回测
# =========================================================

st.divider()

st.subheader(
    "🧠 V5.4 自动优化 + Walk-Forward"
)

col1, col2, col3 = st.columns(3)

with col1:

    holding_days = st.selectbox(
        "持有周期",
        [5, 10, 20],
        index=0
    )

with col2:

    train_ratio = st.slider(
        "训练比例",
        0.5,
        0.8,
        0.6,
        0.05
    )

with col3:

    minimum_samples = st.number_input(
        "最低训练样本",
        min_value=10,
        max_value=100,
        value=20,
        step=5
    )


col1, col2 = st.columns(2)

with col1:

    fee = st.number_input(
        "单边手续费",
        min_value=0.0,
        max_value=0.01,
        value=0.0003,
        step=0.0001,
        format="%.4f"
    )

with col2:

    slippage = st.number_input(
        "单边滑点",
        min_value=0.0,
        max_value=0.02,
        value=0.001,
        step=0.0005,
        format="%.4f"
    )


if st.button(
    "🚀 开始 V5.4 回测",
    type="primary",
    use_container_width=True
):

    if len(selected_stocks) == 0:

        st.error(
            "请先选择股票"
        )

        st.stop()

    with st.spinner(
        "正在进行加速回测……"
    ):

        results, weights_df = (
            run_backtest(
                selected_stocks,
                holding_days,
                train_ratio,
                minimum_samples,
                fee,
                slippage
            )
        )

    if results.empty:

        st.error(
            "没有得到有效的样本外结果。"
        )

        st.stop()

    performance = (
        calculate_performance(
            results
        )
    )

    st.success(
        "✅ V5.4 样本外回测完成"
    )

    # -----------------------------------------------------
    # 总体指标
    # -----------------------------------------------------

    st.subheader(
        "📊 样本外表现"
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "样本数",
            performance["样本数"]
        )

    with col2:

        st.metric(
            "胜率",
            f"{performance['胜率']:.2f}%"
        )

    with col3:

        st.metric(
            "平均净收益",
            f"{performance['平均收益']:.2f}%"
        )

    with col4:

        st.metric(
            "累计收益",
            f"{performance['累计收益']:.2f}%"
        )

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "中位数收益",
            f"{performance['中位数收益']:.2f}%"
        )

    with col2:

        st.metric(
            "最大回撤",
            f"{performance['最大回撤']:.2f}%"
        )

    with col3:

        st.metric(
            "夏普比率",
            f"{performance['夏普']:.2f}"
        )

    with col4:

        st.metric(
            "最大亏损",
            f"{performance['最大亏损']:.2f}%"
        )

    # -----------------------------------------------------
    # 模型评价
    # -----------------------------------------------------

    st.subheader(
        "🧠 模型评价"
    )

    if (
        performance["平均收益"] > 0.5
        and performance["胜率"] >= 55
        and performance["夏普"] >= 1
        and performance["最大回撤"] > -25
    ):

        st.success(
            "🟢 模型表现较好："
            "样本外收益、胜率和风险控制均较合理。"
        )

    elif (
        performance["平均收益"] > 0
        and performance["胜率"] >= 50
    ):

        st.info(
            "🟡 模型存在一定优势，"
            "但还需要更多市场阶段进行验证。"
        )

    else:

        st.warning(
            "🔴 当前样本外表现较弱，"
            "暂时不建议把模型结果直接用于实盘决策。"
        )

    # -----------------------------------------------------
    # 累计净值
    # -----------------------------------------------------

    st.subheader(
        "📈 样本外累计净值"
    )

    equity = (
        1
        + results[
            "净收益"
        ] / 100
    ).cumprod()

    equity_df = pd.DataFrame(
        {
            "累计净值":
                equity.values
        }
    )

    st.line_chart(
        equity_df
    )

    # -----------------------------------------------------
    # 回撤
    # -----------------------------------------------------

    st.subheader(
        "📉 回撤"
    )

    peak = (
        equity
        .cummax()
    )

    drawdown = (
        equity
        / peak
        - 1
    ) * 100

    drawdown_df = pd.DataFrame(
        {
            "回撤":
                drawdown.values
        }
    )

    st.line_chart(
        drawdown_df
    )

    # -----------------------------------------------------
    # 各股票
    # -----------------------------------------------------

    st.subheader(
        "🏆 股票表现"
    )

    stock_stats = (
        results
        .groupby(
            [
                "代码",
                "股票名称"
            ]
        )
        .agg(
            样本数=(
                "净收益",
                "count"
            ),

            胜率=(
                "净收益",
                lambda x:
                    (
                        x > 0
                    ).mean() * 100
            ),

            平均收益=(
                "净收益",
                "mean"
            ),

            最大收益=(
                "净收益",
                "max"
            ),

            最大亏损=(
                "净收益",
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
        ascending=False
    )

    st.dataframe(
        stock_stats,
        use_container_width=True,
        hide_index=True
    )

    # -----------------------------------------------------
    # 自动权重
    # -----------------------------------------------------

    if not weights_df.empty:

        st.subheader(
            "⚙️ 自动优化权重"
        )

        average_weights = pd.DataFrame(
            {
                "平均权重":
                    weights_df[
                        [
                            "趋势",
                            "动量",
                            "MACD",
                            "成交量",
                            "突破",
                            "风险"
                        ]
                    ].mean()
            }
        )

        st.dataframe(
            average_weights,
            use_container_width=True
        )

        st.dataframe(
            weights_df,
            use_container_width=True,
            hide_index=True
        )

    # -----------------------------------------------------
    # 交易记录
    # -----------------------------------------------------

    st.subheader(
        "📋 样本外交易记录"
    )

    display_results = results[
        [
            "股票名称",
            "代码",
            "日期",
            "评分",
            "未来收益",
            "净收益"
        ]
    ].copy()

    display_results = (
        display_results
        .sort_values(
            "日期",
            ascending=False
        )
    )

    st.dataframe(
        display_results.head(500),
        use_container_width=True,
        hide_index=True
    )

    # -----------------------------------------------------
    # 下载
    # -----------------------------------------------------

    csv = (
        display_results
        .to_csv(
            index=False,
            encoding="utf-8-sig"
        )
    )

    st.download_button(
        "⬇️ 下载回测结果",
        data=csv,
        file_name=(
            f"V5.4_回测结果_"
            f"{holding_days}日.csv"
        ),
        mime="text/csv",
        use_container_width=True
    )


# =========================================================
# 当前股票池
# =========================================================

st.divider()

st.subheader(
    "📋 当前股票池"
)

if stock_list.empty:

    st.warning(
        "没有读取到 stock_list.csv"
    )

else:

    st.dataframe(
        stock_list,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# 页脚
# =========================================================

st.divider()

st.caption(
    "⚠️ 本程序仅用于量化研究、学习和历史数据分析，"
    "不构成投资建议。历史回测结果不代表未来收益。"
)
