import streamlit as st
import pandas as pd
import numpy as np
import os
import itertools


# =========================================================
# 页面设置
# =========================================================

st.set_page_config(
    page_title="A股量化选股助手 V5.3",
    page_icon="📈",
    layout="wide"
)

st.title("📈 A股量化选股助手")
st.caption(
    "V5.3 · 中文名称 · MA · MACD · 动量 · 成交量 · 突破 · "
    "自动优化 · Walk-Forward · 回测"
)


# =========================================================
# 文件
# =========================================================

STOCK_LIST_FILE = "stock_list.csv"


# =========================================================
# 安全取值
# =========================================================

def value(row, column, default=np.nan):

    try:

        if column not in row.index:
            return default

        v = row[column]

        if pd.isna(v):
            return default

        return float(v)

    except Exception:

        return default


# =========================================================
# 股票名称
# =========================================================

@st.cache_data
def load_stock_names():

    names = {}

    if not os.path.exists(STOCK_LIST_FILE):

        return names

    try:

        stock_list = pd.read_csv(
            STOCK_LIST_FILE,
            dtype={"code": str}
        )

        stock_list["code"] = (
            stock_list["code"]
            .astype(str)
            .str.extract(r"(\d{6})")[0]
        )

        name_column = None

        for column in [
            "name",
            "名称",
            "股票名称",
            "stock_name"
        ]:

            if column in stock_list.columns:

                name_column = column
                break

        if name_column is None:

            return names

        for _, row in stock_list.iterrows():

            code = str(
                row["code"]
            ).zfill(6)

            name = str(
                row[name_column]
            )

            if (
                code != "nan"
                and name != "nan"
            ):

                names[code] = name

    except Exception:

        pass

    return names


STOCK_NAMES = load_stock_names()


# =========================================================
# 股票代码
# =========================================================

@st.cache_data
def load_stock_list():

    if not os.path.exists(
        STOCK_LIST_FILE
    ):

        return []

    try:

        df = pd.read_csv(
            STOCK_LIST_FILE,
            dtype={"code": str}
        )

        if "code" not in df.columns:

            return []

        codes = (
            df["code"]
            .astype(str)
            .str.extract(r"(\d{6})")[0]
            .dropna()
            .tolist()
        )

        return list(
            dict.fromkeys(codes)
        )

    except Exception:

        return []


STOCKS = load_stock_list()


# =========================================================
# 读取行情
# =========================================================

@st.cache_data
def load_stock_data(code):

    filename = (
        f"data/{code}.csv"
    )

    if not os.path.exists(filename):

        raise FileNotFoundError(
            f"没有找到 {code} 的行情文件"
        )

    df = pd.read_csv(
        filename
    )

    if df.empty:

        raise ValueError(
            "行情数据为空"
        )

    required_columns = [
        "日期",
        "开盘",
        "收盘",
        "最高",
        "最低",
        "成交量"
    ]

    missing = [
        c
        for c in required_columns
        if c not in df.columns
    ]

    if missing:

        raise ValueError(
            f"缺少字段：{missing}"
        )

    # 日期

    df["日期"] = pd.to_datetime(
        df["日期"],
        errors="coerce"
    )

    # 数字

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

    df = df.reset_index(
        drop=True
    )

    # =====================================================
    # 涨跌幅
    # =====================================================

    df["涨跌幅"] = (
        df["收盘"]
        .pct_change()
        * 100
    )

    # =====================================================
    # MA
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
    # MA趋势
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

    df["MACD_CHANGE"] = (
        df["MACD"]
        .diff()
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
        df["最高"]
        .rolling(20)
        .max()
        .shift(1)
    )

    df["DIST_HIGH20"] = (
        df["收盘"]
        / df["HIGH20"]
        - 1
    ) * 100

    # =====================================================
    # 波动率
    # =====================================================

    df["VOLATILITY20"] = (
        df["涨跌幅"]
        .rolling(20)
        .std()
    )

    # =====================================================
    # ATR
    # =====================================================

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

    return df


# =========================================================
# 因子计算
# =========================================================

def calculate_factors(
    df,
    i
):

    if i < 60:

        return None

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

    change = value(
        row,
        "涨跌幅",
        0
    )

    # =====================================================
    # 趋势 0-25
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
    # 动量 0-20
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
    # MACD 0-15
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
    # 成交量 0-15
    # =====================================================

    volume_score = 0

    if (
        pd.notna(volume)
        and pd.notna(volume20)
        and volume20 > 0
    ):

        if volume_ratio > 1:
            volume_score += 5

        if volume_ratio >= 1.2:
            volume_score += 5

        if (
            change > 0
            and volume_ratio >= 1.2
        ):

            volume_score += 5

    volume_score = min(
        volume_score,
        15
    )

    # =====================================================
    # 突破 0-15
    # =====================================================

    breakout = 0

    if (
        pd.notna(price)
        and pd.notna(high20)
        and high20 > 0
    ):

        ratio = (
            price
            / high20
        )

        if ratio >= 1:
            breakout += 10

        elif ratio >= 0.97:
            breakout += 6

        elif ratio >= 0.93:
            breakout += 3

    if (
        breakout >= 10
        and pd.notna(volume_ratio)
        and volume_ratio >= 1.2
    ):

        breakout += 5

    breakout = min(
        breakout,
        15
    )

    # =====================================================
    # 风险 0-20
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
# 权重评分
# =========================================================

def weighted_score(
    factors,
    weights
):

    positive = (

        factors["trend"]
        * weights["trend"]

        +

        factors["momentum"]
        * weights["momentum"]

        +

        factors["macd"]
        * weights["macd"]

        +

        factors["volume"]
        * weights["volume"]

        +

        factors["breakout"]
        * weights["breakout"]
    )

    risk_penalty = (
        factors["risk"]
        * weights["risk"]
    )

    score = (
        positive
        - risk_penalty
    )

    # 将不同权重产生的结果压缩到0-100
    # 方便不同组合比较

    raw_max = (
        25 * weights["trend"]
        + 20 * weights["momentum"]
        + 15 * weights["macd"]
        + 15 * weights["volume"]
        + 15 * weights["breakout"]
    )

    if raw_max <= 0:
        return 0

    normalized = (
        score
        / raw_max
        * 100
    )

    return max(
        0,
        min(
            100,
            normalized
        )
    )


# =========================================================
# 权重组合
# =========================================================

def generate_weight_sets():

    values = [
        0.6,
        0.8,
        1.0,
        1.2,
        1.4
    ]

    combinations = itertools.product(
        values,
        repeat=5
    )

    result = []

    for combo in combinations:

        average = (
            sum(combo)
            / 5
        )

        if (
            0.85
            <= average
            <= 1.15
        ):

            result.append({

                "trend": combo[0],

                "momentum": combo[1],

                "macd": combo[2],

                "volume": combo[3],

                "breakout": combo[4],

                "risk": 1.0
            })

    return result


# =========================================================
# 建立历史样本
# =========================================================

def build_samples(
    holding_days,
    start_ratio,
    end_ratio
):

    samples = []

    total_stocks = len(
        STOCKS
    )

    for stock_index, code in enumerate(
        STOCKS
    ):

        try:

            df = load_stock_data(
                code
            )

        except Exception:

            continue

        total = len(df)

        start = max(
            60,
            int(
                total
                * start_ratio
            )
        )

        end = min(
            total - holding_days,
            int(
                total
                * end_ratio
            )
        )

        if end <= start:

            continue

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
# 自动寻找最佳权重
# =========================================================

def optimize_weights(
    samples,
    minimum_samples=20
):

    if samples.empty:

        return None

    weight_sets = (
        generate_weight_sets()
    )

    results = []

    for weights in weight_sets:

        scores = []

        for _, row in samples.iterrows():

            factors = {

                "trend": row["trend"],

                "momentum": row["momentum"],

                "macd": row["macd"],

                "volume": row["volume"],

                "breakout": row["breakout"],

                "risk": row["risk"]
            }

            scores.append(
                weighted_score(
                    factors,
                    weights
                )
            )

        temp = samples.copy()

        temp["评分"] = scores

        selected = temp[
            temp["评分"] >= 75
        ]

        if len(selected) < minimum_samples:
            continue

        returns = (
            selected["未来收益"]
        )

        avg_return = returns.mean()

        median_return = returns.median()

        win_rate = (
            returns > 0
        ).mean() * 100

        downside = (
            returns[returns < 0]
        )

        if len(downside) > 0:

            downside_avg = (
                downside.mean()
            )

        else:

            downside_avg = 0

        # 优化目标
        #
        # 不单纯追求收益
        # 同时考虑胜率、中位数以及亏损

        objective = (

            avg_return * 0.45

            + median_return * 0.20

            + win_rate * 0.25

            + downside_avg * 0.10
        )

        results.append({

            "objective": objective,

            "平均收益": avg_return,

            "中位数收益": median_return,

            "胜率": win_rate,

            "样本数": len(selected),

            "weights": weights
        })

    if not results:

        return None

    results.sort(
        key=lambda x:
            x["objective"],
        reverse=True
    )

    return {
        "best": results[0],
        "all": results
    }


# =========================================================
# 单次策略回测
# =========================================================

def backtest_with_weights(
    samples,
    weights,
    minimum_score=75,
    fee=0.0003,
    slippage=0.001
):

    if samples.empty:

        return pd.DataFrame()

    records = []

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

        if score < minimum_score:

            continue

        raw_return = row[
            "未来收益"
        ]

        # 买入+卖出成本
        total_cost = (
            fee * 2
            + slippage * 2
        ) * 100

        net_return = (
            raw_return
            - total_cost
        )

        records.append({

            "代码":
                row["代码"],

            "日期":
                row["日期"],

            "评分":
                score,

            "毛收益":
                raw_return,

            "净收益":
                net_return
        })

    return pd.DataFrame(
        records
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
        results["净收益"]
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

    max_drawdown = (
        drawdown.min()
        * 100
    )

    win_rate = (
        returns > 0
    ).mean() * 100

    avg_return = (
        returns.mean()
        * 100
    )

    median_return = (
        returns.median()
        * 100
    )

    cumulative_return = (
        equity.iloc[-1]
        - 1
    ) * 100

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
            win_rate,

        "平均收益":
            avg_return,

        "中位数收益":
            median_return,

        "累计收益":
            cumulative_return,

        "最大回撤":
            max_drawdown,

        "夏普比率":
            sharpe,

        "最大单次收益":
            results["净收益"].max(),

        "最大单次亏损":
            results["净收益"].min()
    }


# =========================================================
# Walk-Forward
# =========================================================

def run_walk_forward(
    holding_days,
    train_ratio=0.6,
    validation_ratio=0.2,
    minimum_samples=20,
    fee=0.0003,
    slippage=0.001
):

    all_validation = []

    optimization_records = []

    for code in STOCKS:

        try:

            df = load_stock_data(
                code
            )

        except Exception:

            continue

        total = len(df)

        if total < 250:

            continue

        train_end = int(
            total
            * train_ratio
        )

        validation_end = int(
            total
            * (
                train_ratio
                + validation_ratio
            )
        )

        # =================================================
        # 第一阶段：训练
        # =================================================

        train_samples = []

        for i in range(
            60,
            min(
                train_end,
                total - holding_days
            )
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

            train_samples.append({

                "代码": code,

                "日期":
                    df.iloc[i]["日期"],

                "未来收益":
                    future_return,

                **factors
            })

        train_df = pd.DataFrame(
            train_samples
        )

        if len(train_df) < minimum_samples:

            continue

        optimization = optimize_weights(
            train_df,
            minimum_samples
        )

        if optimization is None:

            continue

        best = optimization["best"]

        weights = best[
            "weights"
        ]

        # =================================================
        # 第二阶段：验证
        # =================================================

        validation_samples = []

        validation_start = train_end

        validation_end_actual = min(
            validation_end,
            total - holding_days
        )

        for i in range(
            validation_start,
            validation_end_actual
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

            validation_samples.append({

                "代码": code,

                "日期":
                    df.iloc[i]["日期"],

                "未来收益":
                    future_return,

                **factors
            })

        validation_df = pd.DataFrame(
            validation_samples
        )

        if validation_df.empty:

            continue

        validation_results = (
            backtest_with_weights(
                validation_df,
                weights,
                minimum_score=75,
                fee=fee,
                slippage=slippage
            )
        )

        if validation_results.empty:

            continue

        all_validation.append(
            validation_results
        )

        optimization_records.append({

            "代码": code,

            "训练样本":
                len(train_df),

            "训练胜率":
                best["胜率"],

            "训练平均收益":
                best["平均收益"],

            "趋势权重":
                weights["trend"],

            "动量权重":
                weights["momentum"],

            "MACD权重":
                weights["macd"],

            "成交量权重":
                weights["volume"],

            "突破权重":
                weights["breakout"]
        })

    if not all_validation:

        return (
            pd.DataFrame(),
            pd.DataFrame()
        )

    validation_all = pd.concat(
        all_validation,
        ignore_index=True
    )

    optimization_df = pd.DataFrame(
        optimization_records
    )

    return (
        validation_all,
        optimization_df
    )


# =========================================================
# 首页信息
# =========================================================

st.sidebar.header(
    "📊 股票池"
)

st.sidebar.write(
    f"股票数量：**{len(STOCKS)}**"
)

st.sidebar.write(
    f"名称数量：**{len(STOCK_NAMES)}**"
)


# =========================================================
# 单股分析
# =========================================================

st.subheader(
    "🔎 单只股票分析"
)

stock_code = st.text_input(
    "请输入6位A股代码",
    value="600900"
).strip()


if st.button(
    "开始分析",
    type="primary"
):

    if (
        not stock_code.isdigit()
        or len(stock_code) != 6
    ):

        st.error(
            "请输入6位数字股票代码，例如 600900"
        )

        st.stop()

    try:

        with st.spinner(
            "正在读取行情……"
        ):

            df = load_stock_data(
                stock_code
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

    name = STOCK_NAMES.get(
        stock_code,
        "未知股票"
    )

    price = value(
        latest,
        "收盘"
    )

    change = value(
        latest,
        "涨跌幅"
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

    volume = value(
        latest,
        "成交量"
    )

    volume20 = value(
        latest,
        "VOL20"
    )

    factors = calculate_factors(
        df,
        len(df) - 1
    )

    default_weights = {

        "trend": 1.0,

        "momentum": 1.0,

        "macd": 1.0,

        "volume": 1.0,

        "breakout": 1.0,

        "risk": 1.0
    }

    score = weighted_score(
        factors,
        default_weights
    )

    st.success(
        f"📌 {name}（{stock_code}）"
        f" · 数据日期："
        f"{latest['日期'].strftime('%Y-%m-%d')}"
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "最新收盘",
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

    with col4:

        st.metric(
            "量化评分",
            f"{score:.1f}"
        )

    # =====================================================
    # 趋势
    # =====================================================

    st.subheader(
        "📈 趋势"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "MA5",
            f"{ma5:.2f}"
        )

    with col2:

        st.metric(
            "MA20",
            f"{ma20:.2f}"
        )

    with col3:

        st.metric(
            "MA60",
            f"{ma60:.2f}"
        )

    if (
        ma5 > ma20
        and ma20 > ma60
    ):

        st.success(
            "🟢 MA多头排列"
        )

    elif ma5 > ma20:

        st.info(
            "🟡 短期趋势偏强"
        )

    else:

        st.warning(
            "🔴 趋势偏弱"
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
            "🟢 DIF > DEA"
        )

    else:

        st.warning(
            "🔴 DIF < DEA"
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
            "成交量",
            f"{volume:,.0f}"
        )

    with col2:

        st.metric(
            "20日均量",
            f"{volume20:,.0f}"
        )

    if (
        pd.notna(volume20)
        and volume > volume20
    ):

        st.success(
            "🟢 放量"
        )

    else:

        st.info(
            "⚪ 未明显放量"
        )

    # =====================================================
    # 综合评分
    # =====================================================

    st.subheader(
        "🤖 综合量化评分"
    )

    st.progress(
        int(score)
    )

    if score >= 80:

        st.success(
            f"🟢 强势信号：{score:.1f}/100"
        )

    elif score >= 70:

        st.info(
            f"🟡 偏强信号：{score:.1f}/100"
        )

    elif score >= 60:

        st.warning(
            f"🟠 中性：{score:.1f}/100"
        )

    else:

        st.error(
            f"🔴 偏弱：{score:.1f}/100"
        )

    # =====================================================
    # K线相关数据
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


# =========================================================
# V5.3
# =========================================================

st.divider()

st.subheader(
    "🧠 V5.3 Walk-Forward 自动优化"
)

st.write(
    "程序会使用过去数据训练权重，"
    "再使用之后从未参与训练的数据进行验证。"
)


col1, col2, col3 = st.columns(3)


with col1:

    holding_days = st.selectbox(
        "持有周期",
        [
            5,
            10,
            20
        ],
        format_func=lambda x:
            f"{x}个交易日",
        key="v53_holding"
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
        "最低样本数",
        min_value=10,
        max_value=200,
        value=20,
        step=10
    )


st.subheader(
    "💰 回测成本"
)

col1, col2 = st.columns(2)


with col1:

    fee = st.number_input(
        "单边手续费",
        min_value=0.0,
        max_value=0.005,
        value=0.0003,
        step=0.0001,
        format="%.4f"
    )


with col2:

    slippage = st.number_input(
        "单边滑点",
        min_value=0.0,
        max_value=0.01,
        value=0.001,
        step=0.0005,
        format="%.4f"
    )


if st.button(
    "🚀 开始 V5.3 滚动回测",
    type="primary",
    use_container_width=True
):

    if len(STOCKS) == 0:

        st.error(
            "股票池为空，请检查 stock_list.csv"
        )

        st.stop()

    with st.spinner(
        "正在进行 Walk-Forward 回测……"
    ):

        validation_results, optimization_df = (
            run_walk_forward(
                holding_days=holding_days,
                train_ratio=train_ratio,
                validation_ratio=(
                    1 - train_ratio
                ) / 2,
                minimum_samples=minimum_samples,
                fee=fee,
                slippage=slippage
            )
        )

    if validation_results.empty:

        st.error(
            "没有得到有效的样本外回测结果。"
        )

        st.info(
            "可能是股票历史数据不足，"
            "或者最低样本数设置过高。"
        )

        st.stop()

    # =====================================================
    # 总体表现
    # =====================================================

    performance = calculate_performance(
        validation_results
    )

    st.success(
        "✅ Walk-Forward 样本外回测完成"
    )

    st.subheader(
        "📊 样本外真实表现"
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
            f"{performance['夏普比率']:.2f}"
        )

    with col4:

        st.metric(
            "最大亏损",
            f"{performance['最大单次亏损']:.2f}%"
        )

    # =====================================================
    # 判断
    # =====================================================

    st.subheader(
        "🧠 模型评价"
    )

    if (
        performance["平均收益"] > 0
        and performance["胜率"] >= 55
        and performance["夏普比率"] > 1
    ):

        st.success(
            "🟢 当前样本外结果较好。"
            "模型在未参与训练的数据上仍保持正收益和较好的风险收益比。"
        )

    elif (
        performance["平均收益"] > 0
        and performance["胜率"] >= 50
    ):

        st.info(
            "🟡 模型存在一定正向效果，"
            "但优势还不够明显，需要更多历史数据和不同市场阶段验证。"
        )

    else:

        st.warning(
            "🔴 当前样本外结果不足以证明模型具有稳定优势。"
            "不要仅根据训练集结果使用该策略。"
        )

    # =====================================================
    # 收益曲线
    # =====================================================

    st.subheader(
        "📈 样本外累计收益曲线"
    )

    equity = (
        1
        + validation_results[
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

    # =====================================================
    # 回撤
    # =====================================================

    st.subheader(
        "📉 回撤曲线"
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

    # =====================================================
    # 各股票表现
    # =====================================================

    st.subheader(
        "🏆 各股票样本外表现"
    )

    stock_stats = (
        validation_results
        .groupby("代码")
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

    stock_stats["股票名称"] = (
        stock_stats["代码"]
        .map(STOCK_NAMES)
        .fillna("未知股票")
    )

    stock_stats = stock_stats[
        [
            "股票名称",
            "代码",
            "样本数",
            "胜率",
            "平均收益",
            "最大收益",
            "最大亏损"
        ]
    ]

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
    # 权重统计
    # =====================================================

    if not optimization_df.empty:

        st.subheader(
            "⚙️ Walk-Forward 自动优化权重"
        )

        weight_columns = [
            "趋势权重",
            "动量权重",
            "MACD权重",
            "成交量权重",
            "突破权重"
        ]

        weight_summary = (
            optimization_df[
                weight_columns
            ]
            .mean()
            .to_frame(
                "平均权重"
            )
        )

        st.dataframe(
            weight_summary,
            use_container_width=True
        )

        st.subheader(
            "📋 每只股票训练出的权重"
        )

        st.dataframe(
            optimization_df,
            use_container_width=True,
            hide_index=True
        )

    # =====================================================
    # 历史交易记录
    # =====================================================

    st.subheader(
        "📋 样本外交易记录"
    )

    display_results = (
        validation_results
        .copy()
    )

    display_results["股票名称"] = (
        display_results["代码"]
        .map(STOCK_NAMES)
        .fillna("未知股票")
    )

    display_results = display_results[
        [
            "股票名称",
            "代码",
            "日期",
            "评分",
            "毛收益",
            "净收益"
        ]
    ]

    display_results = display_results.sort_values(
        "日期",
        ascending=False
    )

    st.dataframe(
        display_results.head(300),
        use_container_width=True,
        hide_index=True
    )

    # =====================================================
    # 下载
    # =====================================================

    csv = (
        display_results
        .to_csv(
            index=False,
            encoding="utf-8-sig"
        )
    )

    st.download_button(
        "⬇️ 下载样本外回测结果",
        data=csv,
        file_name=(
            f"V5.3_walk_forward_"
            f"{holding_days}days.csv"
        ),
        mime="text/csv",
        use_container_width=True
    )


# =========================================================
# 股票池
# =========================================================

st.divider()

st.subheader(
    "📋 当前股票池"
)

if STOCKS:

    stock_preview = pd.DataFrame(
        {
            "股票名称": [
                STOCK_NAMES.get(
                    code,
                    "未知股票"
                )
                for code in STOCKS
            ],

            "代码": STOCKS
        }
    )

    st.dataframe(
        stock_preview,
        use_container_width=True,
        hide_index=True
    )

else:

    st.warning(
        "没有读取到 stock_list.csv"
    )


# =========================================================
# 页脚
# =========================================================

st.divider()

st.caption(
    "⚠️ 本程序仅用于量化研究、学习和历史数据分析，"
    "不构成投资建议。历史回测结果不代表未来收益。"
)
