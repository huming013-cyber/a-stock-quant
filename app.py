import os
import itertools

import streamlit as st
import pandas as pd
import numpy as np


# =========================================================
# 页面
# =========================================================

st.set_page_config(
    page_title="A股量化助手 V3.0",
    page_icon="📈",
    layout="wide"
)

st.title("📈 A股量化助手 V3.0")

st.caption(
    "股票 + ETF · 自动优化 · 样本外测试 · Walk-Forward"
)


# =========================================================
# 刷新
# =========================================================

if st.button(
    "🔄 刷新数据",
    use_container_width=True
):

    st.cache_data.clear()

    st.rerun()


# =========================================================
# 列表
# =========================================================

@st.cache_data
def load_list(filename):

    if not os.path.exists(filename):

        return pd.DataFrame(
            columns=["code", "name"]
        )

    df = pd.read_csv(
        filename,
        dtype={"code": str}
    )

    df["code"] = (
        df["code"]
        .astype(str)
        .str.zfill(6)
    )

    return df


stocks = load_list(
    "stock_list.csv"
)

etfs = load_list(
    "etf_list.csv"
)


# =========================================================
# 数据
# =========================================================

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
            f"找不到数据文件：{filename}"
        )

    df = pd.read_csv(
        filename
    )

    required = [
        "日期",
        "开盘",
        "最高",
        "最低",
        "收盘",
        "成交量"
    ]

    for col in required:

        if col not in df.columns:

            raise ValueError(
                f"{filename} 缺少 {col}"
            )

    df["日期"] = pd.to_datetime(
        df["日期"],
        errors="coerce"
    )

    for col in [
        "开盘",
        "最高",
        "最低",
        "收盘",
        "成交量"
    ]:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    df = df.dropna(
        subset=[
            "日期",
            "开盘",
            "收盘"
        ]
    )

    df = df.sort_values(
        "日期"
    )

    df = df.drop_duplicates(
        "日期"
    )

    return df.reset_index(
        drop=True
    )


# =========================================================
# 指标
# =========================================================

def indicators(
    df,
    ma_fast,
    ma_slow,
    momentum_window,
    volatility_window
):

    data = df.copy()

    # 趋势
    data["MA_FAST"] = (
        data["收盘"]
        .rolling(ma_fast)
        .mean()
    )

    data["MA_SLOW"] = (
        data["收盘"]
        .rolling(ma_slow)
        .mean()
    )

    # 动量
    data["MOM"] = (
        data["收盘"]
        /
        data["收盘"]
        .shift(momentum_window)
        - 1
    )

    # 波动率
    data["RET"] = (
        data["收盘"]
        .pct_change()
    )

    data["VOLATILITY"] = (
        data["RET"]
        .rolling(volatility_window)
        .std()
        *
        np.sqrt(252)
    )

    # 趋势评分
    trend_score = (
        data["MA_FAST"]
        >
        data["MA_SLOW"]
    ).astype(int)

    # 动量评分
    momentum_score = (
        data["MOM"] > 0
    ).astype(int)

    # 波动评分
    volatility_median = (
        data["VOLATILITY"]
        .rolling(60)
        .median()
    )

    volatility_score = (
        data["VOLATILITY"]
        <
        volatility_median * 1.5
    ).astype(int)

    # 综合评分
    data["评分"] = (
        trend_score
        +
        momentum_score
        +
        volatility_score
    )

    return data


# =========================================================
# 回测
# =========================================================

def backtest(
    df,
    initial_capital=100000,
    commission=0.0003,
    slippage=0.001,
    position_ratio=0.95,
    stamp_tax=0
):

    if len(df) < 100:

        return None

    cash = float(
        initial_capital
    )

    shares = 0

    entry_price = None

    entry_date = None

    trades = []

    equity_records = []

    lot = 100

    for i in range(
        60,
        len(df) - 1
    ):

        today = df.iloc[i]

        tomorrow = df.iloc[i + 1]

        score = today["评分"]

        next_open = float(
            tomorrow["开盘"]
        )

        if not np.isfinite(
            next_open
        ):

            continue

        # -------------------------------------------------
        # 买入
        # -------------------------------------------------

        if (
            shares == 0
            and score >= 3
        ):

            buy_price = (
                next_open
                *
                (1 + slippage)
            )

            available = (
                cash
                *
                position_ratio
            )

            shares_to_buy = int(
                available
                /
                buy_price
                /
                lot
            ) * lot

            if shares_to_buy > 0:

                amount = (
                    shares_to_buy
                    *
                    buy_price
                )

                fee = max(
                    amount * commission,
                    5
                )

                total = (
                    amount
                    +
                    fee
                )

                if total <= cash:

                    cash -= total

                    shares = (
                        shares_to_buy
                    )

                    entry_price = (
                        buy_price
                    )

                    entry_date = (
                        tomorrow["日期"]
                    )

        # -------------------------------------------------
        # 卖出
        # -------------------------------------------------

        elif (
            shares > 0
            and score <= 0
        ):

            sell_price = (
                next_open
                *
                (1 - slippage)
            )

            amount = (
                shares
                *
                sell_price
            )

            fee = max(
                amount * commission,
                5
            )

            tax = (
                amount
                *
                stamp_tax
            )

            net = (
                amount
                -
                fee
                -
                tax
            )

            cost = (
                shares
                *
                entry_price
            )

            trade_return = (
                net
                /
                cost
                - 1
            ) * 100

            cash += net

            trades.append({

                "买入日期":
                    entry_date,

                "买入价格":
                    entry_price,

                "卖出日期":
                    tomorrow["日期"],

                "卖出价格":
                    sell_price,

                "收益率":
                    trade_return,

                "持有天数":
                    (
                        tomorrow["日期"]
                        -
                        entry_date
                    ).days
            })

            shares = 0

            entry_price = None

            entry_date = None

        # -------------------------------------------------
        # 资金曲线
        # -------------------------------------------------

        equity = (
            cash
            +
            shares
            *
            float(today["收盘"])
        )

        equity_records.append({

            "日期":
                today["日期"],

            "资产":
                equity
        })

    # -----------------------------------------------------
    # 最终资产
    # -----------------------------------------------------

    last_close = float(
        df.iloc[-1]["收盘"]
    )

    final_equity = (
        cash
        +
        shares
        *
        last_close
    )

    total_return = (
        final_equity
        /
        initial_capital
        - 1
    ) * 100

    days = (
        df["日期"].iloc[-1]
        -
        df["日期"].iloc[0]
    ).days

    years = max(
        days / 365.25,
        0.01
    )

    annual_return = (
        (
            final_equity
            /
            initial_capital
        )
        **
        (1 / years)
        - 1
    ) * 100

    equity = pd.DataFrame(
        equity_records
    )

    if equity.empty:

        return None

    equity["最高资产"] = (
        equity["资产"]
        .cummax()
    )

    equity["回撤"] = (
        equity["资产"]
        /
        equity["最高资产"]
        - 1
    )

    max_drawdown = (
        equity["回撤"].min()
        * 100
    )

    daily_return = (
        equity["资产"]
        .pct_change()
        .dropna()
    )

    if (
        len(daily_return) > 10
        and
        daily_return.std() > 0
    ):

        sharpe = (
            daily_return.mean()
            /
            daily_return.std()
            *
            np.sqrt(252)
        )

    else:

        sharpe = 0

    if max_drawdown < 0:

        calmar = (
            annual_return
            /
            abs(max_drawdown)
        )

    else:

        calmar = 0

    trades_df = pd.DataFrame(
        trades
    )

    trade_count = len(
        trades_df
    )

    if trade_count:

        win_rate = (
            (
                trades_df["收益率"]
                > 0
            ).mean()
            * 100
        )

    else:

        win_rate = 0

    return {

        "total_return":
            total_return,

        "annual_return":
            annual_return,

        "max_drawdown":
            max_drawdown,

        "sharpe":
            sharpe,

        "calmar":
            calmar,

        "trade_count":
            trade_count,

        "win_rate":
            win_rate,

        "equity":
            equity,

        "trades":
            trades_df
    }


# =========================================================
# 参数优化
# =========================================================

def optimize(
    df,
    initial_capital,
    commission,
    slippage,
    position_ratio,
    stamp_tax
):

    results = []

    combinations = itertools.product(

        [5, 10, 20],

        [30, 60, 120],

        [20, 60, 120],

        [20, 60]
    )

    for (
        fast,
        slow,
        momentum,
        volatility
    ) in combinations:

        if fast >= slow:

            continue

        test = indicators(
            df,
            fast,
            slow,
            momentum,
            volatility
        )

        result = backtest(

            test,

            initial_capital,

            commission,

            slippage,

            position_ratio,

            stamp_tax
        )

        if result is None:

            continue

        # -------------------------------------------------
        # 综合评分
        # -------------------------------------------------

        score = (

            result["annual_return"]

            +

            result["sharpe"] * 8

            +

            result["calmar"] * 4

            +

            min(
                result["trade_count"],
                20
            ) * 0.2

        )

        results.append({

            "MA快":
                fast,

            "MA慢":
                slow,

            "动量":
                momentum,

            "波动率":
                volatility,

            "年化收益":
                result["annual_return"],

            "最大回撤":
                result["max_drawdown"],

            "Sharpe":
                result["sharpe"],

            "Calmar":
                result["calmar"],

            "交易次数":
                result["trade_count"],

            "胜率":
                result["win_rate"],

            "评分":
                score
        })

    result_df = pd.DataFrame(
        results
    )

    if result_df.empty:

        return None

    result_df = (
        result_df
        .sort_values(
            "评分",
            ascending=False
        )
        .reset_index(drop=True)
    )

    best = result_df.iloc[0]

    params = {

        "fast":
            int(best["MA快"]),

        "slow":
            int(best["MA慢"]),

        "momentum":
            int(best["动量"]),

        "volatility":
            int(best["波动率"])
    }

    return params, result_df


# =========================================================
# Walk Forward
# =========================================================

def walk_forward(
    df,
    initial_capital,
    commission,
    slippage,
    position_ratio,
    stamp_tax
):

    if len(df) < 500:

        return None

    results = []

    window = 400

    test_size = 100

    start = 0

    while (
        start
        +
        window
        +
        test_size
        <=
        len(df)
    ):

        train = df.iloc[
            start:
            start + window
        ].copy()

        test = df.iloc[
            start + window:
            start + window + test_size
        ].copy()

        optimized = optimize(

            train,

            initial_capital,

            commission,

            slippage,

            position_ratio,

            stamp_tax
        )

        if optimized is None:

            start += test_size

            continue

        params, _ = optimized

        # -------------------------------------------------
        # 指标预热
        # -------------------------------------------------

        max_window = max(
            params["slow"],
            params["momentum"],
            params["volatility"],
            120
        )

        begin = max(
            0,
            start + window - max_window
        )

        combined = df.iloc[
            begin:
            start + window + test_size
        ].copy()

        combined = indicators(

            combined,

            params["fast"],

            params["slow"],

            params["momentum"],

            params["volatility"]
        )

        test_part = combined[
            combined["日期"]
            >=
            test["日期"].min()
        ].copy()

        result = backtest(

            test_part,

            initial_capital,

            commission,

            slippage,

            position_ratio,

            stamp_tax
        )

        if result is not None:

            results.append({

                "测试开始":
                    test["日期"].min(),

                "测试结束":
                    test["日期"].max(),

                "年化收益":
                    result["annual_return"],

                "最大回撤":
                    result["max_drawdown"],

                "Sharpe":
                    result["sharpe"],

                "交易次数":
                    result["trade_count"]
            })

        start += test_size

    if not results:

        return None

    wf = pd.DataFrame(
        results
    )

    return wf


# =========================================================
# 选择资产
# =========================================================

asset_type = st.radio(
    "选择类型",
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


if asset_list.empty:

    st.error(
        "没有找到品种列表。"
    )

    st.stop()


# =========================================================
# 选择品种
# =========================================================

options = (
    asset_list["code"]
    +
    " - "
    +
    asset_list["name"]
).tolist()

selected = st.selectbox(
    "选择分析品种",
    options
)

code = selected.split(
    " - "
)[0]


# =========================================================
# 参数
# =========================================================

st.sidebar.header(
    "⚙️ 回测设置"
)

years = st.sidebar.selectbox(
    "历史范围",
    [3, 5, 8, 10, 0],
    format_func=lambda x:
        "全部历史"
        if x == 0
        else f"{x}年"
)

initial_capital = st.sidebar.number_input(
    "初始资金",
    min_value=10000,
    max_value=10000000,
    value=100000,
    step=10000
)

position_ratio = (
    st.sidebar.slider(
        "最大仓位 %",
        10,
        100,
        95,
        5
    )
    / 100
)

commission = (
    st.sidebar.number_input(
        "佣金 %",
        0.0,
        0.5,
        0.03,
        0.01
    )
    / 100
)

slippage = (
    st.sidebar.number_input(
        "滑点 %",
        0.0,
        2.0,
        0.10,
        0.01
    )
    / 100
)

if asset_key == "stock":

    stamp_tax = (
        st.sidebar.number_input(
            "印花税 %",
            0.0,
            1.0,
            0.05,
            0.01
        )
        / 100
    )

else:

    stamp_tax = 0


# =========================================================
# 开始分析
# =========================================================

if st.button(
    "🚀 开始量化分析",
    type="primary",
    use_container_width=True
):

    try:

        raw = load_data(
            code,
            asset_key
        )

    except Exception as e:

        st.error(
            "数据读取失败"
        )

        st.code(
            str(e)
        )

        st.stop()

    # -----------------------------------------------------
    # 历史区间
    # -----------------------------------------------------

    end_date = raw["日期"].max()

    if years == 0:

        start_date = raw["日期"].min()

    else:

        start_date = (
            end_date
            -
            pd.DateOffset(
                years=years
            )
        )

    df = raw[
        raw["日期"] >= start_date
    ].copy()

    if len(df) < 300:

        st.error(
            "有效历史数据不足300个交易日。"
        )

        st.stop()

    # -----------------------------------------------------
    # 训练测试
    # -----------------------------------------------------

    split = int(
        len(df) * 0.7
    )

    train = df.iloc[
        :split
    ].copy()

    test = df.iloc[
        split:
    ].copy()

    st.subheader(
        "① 训练集自动优化"
    )

    result = optimize(

        train,

        initial_capital,

        commission,

        slippage,

        position_ratio,

        stamp_tax
    )

    if result is None:

        st.error(
            "没有找到有效参数。"
        )

        st.stop()

    params, ranking = result

    cols = st.columns(4)

    with cols[0]:

        st.metric(
            "MA快",
            params["fast"]
        )

    with cols[1]:

        st.metric(
            "MA慢",
            params["slow"]
        )

    with cols[2]:

        st.metric(
            "动量",
            params["momentum"]
        )

    with cols[3]:

        st.metric(
            "波动率",
            params["volatility"]
        )

    # -----------------------------------------------------
    # 训练结果
    # -----------------------------------------------------

    train_ind = indicators(

        train,

        params["fast"],

        params["slow"],

        params["momentum"],

        params["volatility"]
    )

    train_result = backtest(

        train_ind,

        initial_capital,

        commission,

        slippage,

        position_ratio,

        stamp_tax
    )

    # -----------------------------------------------------
    # 测试集指标预热
    # -----------------------------------------------------

    warmup = max(
        params["slow"],
        params["momentum"],
        params["volatility"],
        120
    )

    test_start = max(
        0,
        split - warmup
    )

    combined = df.iloc[
        test_start:
    ].copy()

    combined = indicators(

        combined,

        params["fast"],

        params["slow"],

        params["momentum"],

        params["volatility"]
    )

    test = combined[
        combined["日期"]
        >=
        df.iloc[split]["日期"]
    ].copy()

    # -----------------------------------------------------
    # 测试
    # -----------------------------------------------------

    st.subheader(
        "② 完全样本外测试"
    )

    test_result = backtest(

        test,

        initial_capital,

        commission,

        slippage,

        position_ratio,

        stamp_tax
    )

    if test_result is None:

        st.error(
            "测试集回测失败。"
        )

        st.stop()

    comparison = pd.DataFrame({

        "指标": [
            "累计收益",
            "年化收益",
            "最大回撤",
            "Sharpe",
            "Calmar",
            "交易次数",
            "胜率"
        ],

        "训练集": [

            f"{train_result['total_return']:.2f}%",

            f"{train_result['annual_return']:.2f}%",

            f"{train_result['max_drawdown']:.2f}%",

            f"{train_result['sharpe']:.2f}",

            f"{train_result['calmar']:.2f}",

            train_result["trade_count"],

            f"{train_result['win_rate']:.2f}%"
        ],

        "测试集": [

            f"{test_result['total_return']:.2f}%",

            f"{test_result['annual_return']:.2f}%",

            f"{test_result['max_drawdown']:.2f}%",

            f"{test_result['sharpe']:.2f}",

            f"{test_result['calmar']:.2f}",

            test_result["trade_count"],

            f"{test_result['win_rate']:.2f}%"
        ]
    })

    st.dataframe(
        comparison,
        use_container_width=True,
        hide_index=True
    )

    # -----------------------------------------------------
    # 核心结果
    # -----------------------------------------------------

    st.subheader(
        "③ 测试集真实表现"
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.metric(
            "年化收益",
            f"{test_result['annual_return']:.2f}%"
        )

    with c2:

        st.metric(
            "最大回撤",
            f"{test_result['max_drawdown']:.2f}%"
        )

    with c3:

        st.metric(
            "Sharpe",
            f"{test_result['sharpe']:.2f}"
        )

    with c4:

        st.metric(
            "胜率",
            f"{test_result['win_rate']:.2f}%"
        )

    # -----------------------------------------------------
    # Walk Forward
    # -----------------------------------------------------

    st.subheader(
        "④ Walk-Forward 滚动验证"
    )

    wf = walk_forward(

        df,

        initial_capital,

        commission,

        slippage,

        position_ratio,

        stamp_tax
    )

    if wf is None:

        st.warning(
            "历史数据不足，无法进行Walk-Forward。"
        )

    else:

        avg_return = (
            wf["年化收益"].mean()
        )

        positive_rate = (
            (
                wf["年化收益"] > 0
            ).mean()
            * 100
        )

        avg_drawdown = (
            wf["最大回撤"].mean()
        )

        wc1, wc2, wc3 = st.columns(3)

        with wc1:

            st.metric(
                "平均年化",
                f"{avg_return:.2f}%"
            )

        with wc2:

            st.metric(
                "盈利窗口比例",
                f"{positive_rate:.1f}%"
            )

        with wc3:

            st.metric(
                "平均最大回撤",
                f"{avg_drawdown:.2f}%"
            )

        st.dataframe(
            wf,
            use_container_width=True,
            hide_index=True
        )

    # -----------------------------------------------------
    # 资金曲线
    # -----------------------------------------------------

    st.subheader(
        "⑤ 测试集资金曲线"
    )

    chart = (
        test_result["equity"][
            [
                "日期",
                "资产"
            ]
        ]
        .set_index("日期")
    )

    st.line_chart(
        chart
    )

    # -----------------------------------------------------
    # 参数排行榜
    # -----------------------------------------------------

    st.subheader(
        "⑥ 训练集参数排行榜"
    )

    display = ranking.head(10).copy()

    for col in [
        "年化收益",
        "最大回撤",
        "Sharpe",
        "Calmar",
        "胜率",
        "评分"
    ]:

        display[col] = (
            display[col]
            .round(2)
        )

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True
    )

    # -----------------------------------------------------
    # 交易记录
    # -----------------------------------------------------

    st.subheader(
        "⑦ 测试集交易记录"
    )

    if test_result[
        "trades"
    ].empty:

        st.info(
            "测试集没有完成交易。"
        )

    else:

        trades = (
            test_result[
                "trades"
            ].copy()
        )

        for col in [
            "买入价格",
            "卖出价格",
            "收益率"
        ]:

            trades[col] = (
                trades[col]
                .round(3)
            )

        st.dataframe(
            trades,
            use_container_width=True,
            hide_index=True
        )


# =========================================================
# 说明
# =========================================================

st.divider()

st.caption(
    "V3.0数据层：东方财富主接口 + 腾讯备用接口。"
)

st.caption(
    "V3.0模型：训练集优化 + 样本外测试 + Walk-Forward。"
)

st.caption(
    "历史回测不代表未来收益，仅用于量化研究。"
)
