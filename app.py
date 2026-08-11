import os
import streamlit as st
import pandas as pd
import numpy as np


# =========================================================
# 页面设置
# =========================================================

st.set_page_config(
    page_title="A股量化助手 V2.0",
    page_icon="📈",
    layout="wide"
)

st.title("📈 A股量化助手 V2.0")

st.caption(
    "股票 + ETF · 技术分析 · 综合评分 · 历史回测"
)


# =========================================================
# 读取股票 / ETF 列表
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
# 读取行情
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
            f"没有找到行情文件：{filename}"
        )

    df = pd.read_csv(
        filename
    )

    if df.empty:

        raise ValueError(
            "行情数据为空"
        )

    df["日期"] = pd.to_datetime(
        df["日期"],
        errors="coerce"
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
        subset=[
            "日期",
            "开盘",
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

    df["VOL20"] = (
        df["成交量"]
        .rolling(20)
        .mean()
    )

    return df


# =========================================================
# 生成交易信号
# =========================================================

def generate_signals(
    df,
    ma_short=5,
    ma_long=20
):

    data = df.copy()

    # -----------------------------------------------------
    # 条件1：短期均线高于长期均线
    # -----------------------------------------------------

    condition_ma = (
        data[f"MA{ma_short}"]
        >
        data[f"MA{ma_long}"]
    )

    # -----------------------------------------------------
    # 条件2：MACD DIF > DEA
    # -----------------------------------------------------

    condition_macd = (
        data["DIF"]
        >
        data["DEA"]
    )

    # -----------------------------------------------------
    # 条件3：成交量高于20日平均
    # -----------------------------------------------------

    condition_volume = (
        data["成交量"]
        >
        data["VOL20"]
    )

    # -----------------------------------------------------
    # 综合评分
    # -----------------------------------------------------

    data["评分"] = (
        condition_ma.astype(int)
        +
        condition_macd.astype(int)
        +
        condition_volume.astype(int)
    )

    # -----------------------------------------------------
    # 交易信号
    #
    # 3分：买入
    # 0分：卖出
    # 1/2分：保持原仓位
    # -----------------------------------------------------

    data["买入信号"] = (
        data["评分"] == 3
    )

    data["卖出信号"] = (
        data["评分"] == 0
    )

    return data


# =========================================================
# 回测
# =========================================================

def backtest(
    df,
    initial_capital=100000
):

    data = df.copy()

    cash = float(
        initial_capital
    )

    shares = 0.0

    entry_price = None

    trades = []

    equity_curve = []

    # -----------------------------------------------------
    # 从第30天开始
    # 保证指标基本完整
    # -----------------------------------------------------

    start_index = 30

    for i in range(
        start_index,
        len(data) - 1
    ):

        today = data.iloc[i]

        next_day = data.iloc[i + 1]

        today_signal = today["评分"]

        # =================================================
        # 当天收盘产生信号
        # 下一交易日开盘执行
        # =================================================

        next_open = float(
            next_day["开盘"]
        )

        # =================================================
        # 买入
        # =================================================

        if (
            shares == 0
            and today_signal == 3
            and next_open > 0
        ):

            shares = (
                cash
                / next_open
            )

            cash = 0.0

            entry_price = next_open

            trades.append({
                "买入日期":
                    next_day["日期"],
                "买入价格":
                    next_open,
                "卖出日期":
                    None,
                "卖出价格":
                    None,
                "收益率":
                    None
            })

        # =================================================
        # 卖出
        # =================================================

        elif (
            shares > 0
            and today_signal == 0
            and next_open > 0
        ):

            sell_value = (
                shares
                * next_open
            )

            trade_return = (
                next_open
                / entry_price
                - 1
            ) * 100

            cash = sell_value

            shares = 0.0

            # 更新最后一笔交易
            if trades:

                trades[-1][
                    "卖出日期"
                ] = next_day["日期"]

                trades[-1][
                    "卖出价格"
                ] = next_open

                trades[-1][
                    "收益率"
                ] = trade_return

            entry_price = None

        # =================================================
        # 每日权益
        # =================================================

        close_price = float(
            today["收盘"]
        )

        total_equity = (
            cash
            +
            shares * close_price
        )

        equity_curve.append({
            "日期":
                today["日期"],
            "资产":
                total_equity
        })

    # =====================================================
    # 如果最后还持仓
    # 用最后一天收盘价计算最终资产
    # =====================================================

    last_price = float(
        data.iloc[-1]["收盘"]
    )

    final_equity = (
        cash
        +
        shares * last_price
    )

    # =====================================================
    # 策略累计收益
    # =====================================================

    strategy_return = (
        final_equity
        / initial_capital
        - 1
    ) * 100

    # =====================================================
    # 买入持有
    # =====================================================

    first_price = float(
        data.iloc[start_index]["开盘"]
    )

    buy_hold_return = (
        last_price
        / first_price
        - 1
    ) * 100

    # =====================================================
    # 最大回撤
    # =====================================================

    equity_df = pd.DataFrame(
        equity_curve
    )

    if not equity_df.empty:

        equity_df["最高资产"] = (
            equity_df["资产"]
            .cummax()
        )

        equity_df["回撤"] = (
            equity_df["资产"]
            /
            equity_df["最高资产"]
            - 1
        )

        max_drawdown = (
            equity_df["回撤"].min()
            * 100
        )

    else:

        max_drawdown = 0

    # =====================================================
    # 已完成交易
    # =====================================================

    completed_trades = [
        trade
        for trade in trades
        if trade["收益率"] is not None
    ]

    total_trades = len(
        completed_trades
    )

    winning_trades = [
        trade
        for trade in completed_trades
        if trade["收益率"] > 0
    ]

    losing_trades = [
        trade
        for trade in completed_trades
        if trade["收益率"] <= 0
    ]

    # =====================================================
    # 胜率
    # =====================================================

    if total_trades > 0:

        win_rate = (
            len(winning_trades)
            /
            total_trades
            * 100
        )

    else:

        win_rate = 0

    # =====================================================
    # 盈亏比
    # =====================================================

    avg_win = 0

    avg_loss = 0

    if winning_trades:

        avg_win = np.mean([
            trade["收益率"]
            for trade in winning_trades
        ])

    if losing_trades:

        avg_loss = abs(
            np.mean([
                trade["收益率"]
                for trade in losing_trades
            ])
        )

    if avg_loss > 0:

        profit_loss_ratio = (
            avg_win
            /
            avg_loss
        )

    else:

        profit_loss_ratio = 0

    # =====================================================
    # 结果
    # =====================================================

    results = {

        "initial_capital":
            initial_capital,

        "final_equity":
            final_equity,

        "strategy_return":
            strategy_return,

        "buy_hold_return":
            buy_hold_return,

        "max_drawdown":
            max_drawdown,

        "total_trades":
            total_trades,

        "winning_trades":
            len(winning_trades),

        "losing_trades":
            len(losing_trades),

        "win_rate":
            win_rate,

        "avg_win":
            avg_win,

        "avg_loss":
            avg_loss,

        "profit_loss_ratio":
            profit_loss_ratio
    }

    trades_df = pd.DataFrame(
        completed_trades
    )

    return (
        results,
        trades_df,
        equity_df
    )


# =========================================================
# 资产选择
# =========================================================

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


# =========================================================
# 品种选择
# =========================================================

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

    asset_name = selected

else:

    code = st.text_input(
        "输入代码"
    )

    asset_name = code


# =========================================================
# 功能选择
# =========================================================

function = st.radio(
    "选择功能",
    [
        "技术分析",
        "历史回测"
    ],
    horizontal=True
)


# =========================================================
# 技术分析
# =========================================================

if function == "技术分析":

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

        df = generate_signals(
            df
        )

        latest = df.iloc[-1]

        price = latest["收盘"]

        change = latest["涨跌幅"]

        ma5 = latest["MA5"]

        ma20 = latest["MA20"]

        dif = latest["DIF"]

        dea = latest["DEA"]

        volume = latest["成交量"]

        volume20 = latest["VOL20"]

        score = latest["评分"]

        # -------------------------------------------------
        # 基础行情
        # -------------------------------------------------

        st.success(
            f"{asset_name} · "
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

        # -------------------------------------------------
        # 评分
        # -------------------------------------------------

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

        # -------------------------------------------------
        # 指标
        # -------------------------------------------------

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

        # -------------------------------------------------
        # 价格
        # -------------------------------------------------

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

        # -------------------------------------------------
        # MACD
        # -------------------------------------------------

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
# 历史回测
# =========================================================

else:

    st.subheader(
        "🧪 历史回测"
    )

    st.info(
        "回测规则：当天收盘产生信号，"
        "下一交易日开盘执行。"
    )

    initial_capital = st.number_input(
        "初始资金",
        min_value=10000,
        max_value=10000000,
        value=100000,
        step=10000
    )

    if st.button(
        "🧪 开始回测",
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

        df = generate_signals(
            df
        )

        (
            results,
            trades_df,
            equity_df
        ) = backtest(
            df,
            initial_capital
        )

        # =================================================
        # 回测结果
        # =================================================

        st.success(
            f"{asset_name} 回测完成"
        )

        st.subheader(
            "📊 核心结果"
        )

        col1, col2, col3 = st.columns(3)

        with col1:

            st.metric(
                "策略累计收益",
                f"{results['strategy_return']:.2f}%"
            )

        with col2:

            st.metric(
                "买入持有收益",
                f"{results['buy_hold_return']:.2f}%"
            )

        with col3:

            st.metric(
                "最大回撤",
                f"{results['max_drawdown']:.2f}%"
            )

        col1, col2, col3 = st.columns(3)

        with col1:

            st.metric(
                "交易次数",
                results["total_trades"]
            )

        with col2:

            st.metric(
                "胜率",
                f"{results['win_rate']:.2f}%"
            )

        with col3:

            st.metric(
                "盈亏比",
                f"{results['profit_loss_ratio']:.2f}"
            )

        # =================================================
        # 结果评价
        # =================================================

        st.subheader(
            "🧠 策略评价"
        )

        strategy_return = (
            results["strategy_return"]
        )

        buy_hold_return = (
            results["buy_hold_return"]
        )

        if strategy_return > buy_hold_return:

            st.success(
                "🟢 当前测试中，"
                "策略收益高于简单买入持有。"
            )

        else:

            st.warning(
                "🟡 当前测试中，"
                "策略没有跑赢买入持有。"
            )

        if results["win_rate"] >= 60:

            st.info(
                "胜率达到60%以上，"
                "但仍需要结合收益和最大回撤判断。"
            )

        # =================================================
        # 资金曲线
        # =================================================

        if not equity_df.empty:

            st.subheader(
                "📈 策略资金曲线"
            )

            equity_chart = (
                equity_df[
                    [
                        "日期",
                        "资产"
                    ]
                ]
                .set_index("日期")
            )

            st.line_chart(
                equity_chart
            )

        # =================================================
        # 交易记录
        # =================================================

        st.subheader(
            "📋 历史交易记录"
        )

        if trades_df.empty:

            st.warning(
                "历史数据中没有完成交易。"
            )

        else:

            display_df = (
                trades_df.copy()
            )

            display_df[
                "收益率"
            ] = display_df[
                "收益率"
            ].round(2)

            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True
            )


# =========================================================
# 页面底部
# =========================================================

st.divider()

st.caption(
    "⚠️ 本程序仅用于量化研究、学习和历史数据分析，"
    "不构成投资建议。历史回测结果不代表未来表现。"
)
