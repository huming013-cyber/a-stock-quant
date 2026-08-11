import os
import streamlit as st
import pandas as pd
import numpy as np


# =========================================================
# 页面
# =========================================================

st.set_page_config(
    page_title="A股量化助手 V2.1",
    page_icon="📈",
    layout="wide"
)

st.title("📈 A股量化助手 V2.1")

st.caption(
    "股票 + ETF · 严格历史回测 · 成本 · 滑点 · 风险指标"
)


# =========================================================
# 股票 / ETF 列表
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

def calculate_indicators(df):

    data = df.copy()

    # -----------------------------------------------------
    # 涨跌幅
    # -----------------------------------------------------

    data["涨跌幅"] = (
        data["收盘"]
        .pct_change()
        * 100
    )

    # -----------------------------------------------------
    # MA
    # -----------------------------------------------------

    data["MA5"] = (
        data["收盘"]
        .rolling(5)
        .mean()
    )

    data["MA10"] = (
        data["收盘"]
        .rolling(10)
        .mean()
    )

    data["MA20"] = (
        data["收盘"]
        .rolling(20)
        .mean()
    )

    # -----------------------------------------------------
    # MACD
    # -----------------------------------------------------

    ema12 = (
        data["收盘"]
        .ewm(
            span=12,
            adjust=False
        )
        .mean()
    )

    ema26 = (
        data["收盘"]
        .ewm(
            span=26,
            adjust=False
        )
        .mean()
    )

    data["DIF"] = (
        ema12 - ema26
    )

    data["DEA"] = (
        data["DIF"]
        .ewm(
            span=9,
            adjust=False
        )
        .mean()
    )

    data["MACD"] = (
        data["DIF"]
        - data["DEA"]
    ) * 2

    # -----------------------------------------------------
    # 成交量
    # -----------------------------------------------------

    data["VOL20"] = (
        data["成交量"]
        .rolling(20)
        .mean()
    )

    # -----------------------------------------------------
    # 评分
    # -----------------------------------------------------

    ma_condition = (
        data["MA5"]
        >
        data["MA20"]
    )

    macd_condition = (
        data["DIF"]
        >
        data["DEA"]
    )

    volume_condition = (
        data["成交量"]
        >
        data["VOL20"]
    )

    data["评分"] = (
        ma_condition.astype(int)
        +
        macd_condition.astype(int)
        +
        volume_condition.astype(int)
    )

    # -----------------------------------------------------
    # 信号
    # -----------------------------------------------------

    data["买入信号"] = (
        data["评分"] == 3
    )

    data["卖出信号"] = (
        data["评分"] == 0
    )

    return data


# =========================================================
# 严格回测
# =========================================================

def strict_backtest(
    df,
    years,
    asset_type,
    initial_capital,
    commission_rate,
    stamp_tax_rate,
    slippage_rate,
    position_ratio
):

    data = df.copy()

    # -----------------------------------------------------
    # 选择回测时间
    # -----------------------------------------------------

    end_date = data["日期"].max()

    if years == 0:

        start_date = data["日期"].min()

    else:

        start_date = (
            end_date
            - pd.DateOffset(
                years=years
            )
        )

    data = data[
        data["日期"] >= start_date
    ].copy()

    data = data.reset_index(
        drop=True
    )

    if len(data) < 60:

        raise ValueError(
            "指定回测周期的数据不足，"
            "请选择更短周期或重新下载历史数据。"
        )

    # -----------------------------------------------------
    # 资金
    # -----------------------------------------------------

    cash = float(
        initial_capital
    )

    shares = 0

    entry_price = None

    entry_date = None

    trades = []

    equity_records = []

    # -----------------------------------------------------
    # A股交易单位
    # -----------------------------------------------------

    lot_size = 100

    # -----------------------------------------------------
    # 开始回测
    # -----------------------------------------------------

    for i in range(
        30,
        len(data) - 1
    ):

        today = data.iloc[i]

        next_day = data.iloc[i + 1]

        signal = int(
            today["评分"]
        )

        next_open = float(
            next_day["开盘"]
        )

        if not np.isfinite(
            next_open
        ):

            continue

        if next_open <= 0:

            continue

        # =================================================
        # 买入
        # =================================================

        if (
            shares == 0
            and signal == 3
        ):

            # -------------------------------------------------
            # 计划投入资金
            # -------------------------------------------------

            invest_cash = (
                cash
                * position_ratio
            )

            # -------------------------------------------------
            # 滑点
            # -------------------------------------------------

            buy_price = (
                next_open
                * (1 + slippage_rate)
            )

            # -------------------------------------------------
            # 手数
            # -------------------------------------------------

            max_shares = int(
                invest_cash
                / buy_price
                / lot_size
            ) * lot_size

            if max_shares <= 0:

                continue

            # -------------------------------------------------
            # 佣金
            # -------------------------------------------------

            amount = (
                max_shares
                * buy_price
            )

            commission = max(
                amount
                * commission_rate,
                5
            )

            total_cost = (
                amount
                + commission
            )

            if total_cost > cash:

                continue

            # -------------------------------------------------
            # 执行
            # -------------------------------------------------

            cash -= total_cost

            shares = max_shares

            entry_price = buy_price

            entry_date = (
                next_day["日期"]
            )

        # =================================================
        # 卖出
        # =================================================

        elif (
            shares > 0
            and signal == 0
        ):

            # -------------------------------------------------
            # 滑点
            # -------------------------------------------------

            sell_price = (
                next_open
                * (1 - slippage_rate)
            )

            amount = (
                shares
                * sell_price
            )

            # -------------------------------------------------
            # 卖出佣金
            # -------------------------------------------------

            commission = max(
                amount
                * commission_rate,
                5
            )

            # -------------------------------------------------
            # 股票印花税
            # ETF不收这里设置的股票印花税
            # -------------------------------------------------

            if asset_type == "stock":

                stamp_tax = (
                    amount
                    * stamp_tax_rate
                )

            else:

                stamp_tax = 0

            net_amount = (
                amount
                - commission
                - stamp_tax
            )

            # -------------------------------------------------
            # 交易收益
            # -------------------------------------------------

            trade_return = (
                net_amount
                /
                (
                    shares
                    * entry_price
                )
                - 1
            ) * 100

            cash += net_amount

            trades.append({

                "买入日期":
                    entry_date,

                "买入价格":
                    entry_price,

                "卖出日期":
                    next_day["日期"],

                "卖出价格":
                    sell_price,

                "收益率":
                    trade_return,

                "持有天数":
                    (
                        next_day["日期"]
                        - entry_date
                    ).days
            })

            shares = 0

            entry_price = None

            entry_date = None

        # =================================================
        # 每日权益
        # =================================================

        close_price = float(
            today["收盘"]
        )

        equity = (
            cash
            +
            shares * close_price
        )

        equity_records.append({

            "日期":
                today["日期"],

            "资产":
                equity
        })

    # =====================================================
    # 最终资产
    # =====================================================

    last_close = float(
        data.iloc[-1]["收盘"]
    )

    final_equity = (
        cash
        +
        shares * last_close
    )

    # =====================================================
    # 策略收益
    # =====================================================

    strategy_return = (
        final_equity
        /
        initial_capital
        - 1
    ) * 100

    # =====================================================
    # 买入持有
    # =====================================================

    first_open = float(
        data.iloc[0]["开盘"]
    )

    buy_hold_return = (
        last_close
        /
        first_open
        - 1
    ) * 100

    # =====================================================
    # 年化收益
    # =====================================================

    actual_days = (
        data["日期"].iloc[-1]
        -
        data["日期"].iloc[0]
    ).days

    actual_years = max(
        actual_days / 365.25,
        0.01
    )

    annual_return = (
        (
            final_equity
            /
            initial_capital
        )
        ** (1 / actual_years)
        - 1
    ) * 100

    # =====================================================
    # 资金曲线
    # =====================================================

    equity_df = pd.DataFrame(
        equity_records
    )

    if equity_df.empty:

        raise ValueError(
            "没有产生资金曲线"
        )

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

    # =====================================================
    # 日收益
    # =====================================================

    equity_df["日收益"] = (
        equity_df["资产"]
        .pct_change()
        .fillna(0)
    )

    daily_std = (
        equity_df["日收益"]
        .std()
    )

    if daily_std > 0:

        sharpe = (
            equity_df["日收益"].mean()
            /
            daily_std
            * np.sqrt(252)
        )

    else:

        sharpe = 0

    # =====================================================
    # Calmar
    # =====================================================

    if max_drawdown < 0:

        calmar = (
            annual_return
            /
            abs(max_drawdown)
        )

    else:

        calmar = 0

    # =====================================================
    # 交易统计
    # =====================================================

    trades_df = pd.DataFrame(
        trades
    )

    total_trades = len(
        trades_df
    )

    if total_trades > 0:

        winning = (
            trades_df["收益率"] > 0
        )

        win_rate = (
            winning.mean()
            * 100
        )

        winning_returns = (
            trades_df.loc[
                winning,
                "收益率"
            ]
        )

        losing_returns = (
            trades_df.loc[
                ~winning,
                "收益率"
            ]
        )

        if len(winning_returns) > 0:

            avg_win = (
                winning_returns.mean()
            )

        else:

            avg_win = 0

        if len(losing_returns) > 0:

            avg_loss = abs(
                losing_returns.mean()
            )

        else:

            avg_loss = 0

        if avg_loss > 0:

            profit_loss_ratio = (
                avg_win
                /
                avg_loss
            )

        else:

            profit_loss_ratio = 0

    else:

        win_rate = 0

        avg_win = 0

        avg_loss = 0

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

        "annual_return":
            annual_return,

        "buy_hold_return":
            buy_hold_return,

        "max_drawdown":
            max_drawdown,

        "sharpe":
            sharpe,

        "calmar":
            calmar,

        "total_trades":
            total_trades,

        "win_rate":
            win_rate,

        "avg_win":
            avg_win,

        "avg_loss":
            avg_loss,

        "profit_loss_ratio":
            profit_loss_ratio,

        "actual_years":
            actual_years
    }

    return (
        results,
        trades_df,
        equity_df,
        data
    )


# =========================================================
# 选择资产
# =========================================================

asset_type_name = st.radio(
    "选择分析类型",
    [
        "股票",
        "ETF"
    ],
    horizontal=True
)


if asset_type_name == "股票":

    asset_key = "stock"

    asset_list = stocks

else:

    asset_key = "etf"

    asset_list = etfs


# =========================================================
# 选择品种
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
# 功能
# =========================================================

function = st.radio(
    "选择功能",
    [
        "技术分析",
        "严格历史回测"
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

            df = calculate_indicators(
                df
            )

        except Exception as e:

            st.error(
                "读取数据失败"
            )

            st.code(
                str(e)
            )

            st.stop()

        latest = df.iloc[-1]

        st.success(
            f"{asset_name} · "
            f"{latest['日期'].strftime('%Y-%m-%d')}"
        )

        col1, col2, col3 = st.columns(3)

        with col1:

            st.metric(
                "最新价格",
                f"{latest['收盘']:.3f}",
                f"{latest['涨跌幅']:.2f}%"
            )

        with col2:

            st.metric(
                "MA5",
                f"{latest['MA5']:.3f}"
            )

        with col3:

            st.metric(
                "MA20",
                f"{latest['MA20']:.3f}"
            )

        # -------------------------------------------------
        # 评分
        # -------------------------------------------------

        score = int(
            latest["评分"]
        )

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
        # 技术指标
        # -------------------------------------------------

        st.subheader(
            "📊 技术指标"
        )

        col1, col2, col3 = st.columns(3)

        with col1:

            st.metric(
                "DIF",
                f"{latest['DIF']:.4f}"
            )

        with col2:

            st.metric(
                "DEA",
                f"{latest['DEA']:.4f}"
            )

        with col3:

            st.metric(
                "成交量",
                f"{latest['成交量']:,.0f}"
            )

        # -------------------------------------------------
        # 价格
        # -------------------------------------------------

        st.subheader(
            "📈 价格与均线"
        )

        chart = df.tail(200)[
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

        macd_chart = df.tail(200)[
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
# 严格历史回测
# =========================================================

else:

    st.subheader(
        "🧪 V2.1 严格历史回测"
    )

    st.info(
        "当天收盘产生信号 → "
        "下一交易日开盘成交。"
        "回测不使用未来数据。"
    )

    # -----------------------------------------------------
    # 回测周期
    # -----------------------------------------------------

    years_option = st.selectbox(
        "📅 回测周期",
        [
            1,
            2,
            3,
            5,
            8,
            10,
            0
        ],
        format_func=lambda x:
            "全部历史"
            if x == 0
            else f"{x} 年"
    )

    # -----------------------------------------------------
    # 初始资金
    # -----------------------------------------------------

    initial_capital = st.number_input(
        "💰 初始资金",
        min_value=10000,
        max_value=10000000,
        value=100000,
        step=10000
    )

    # -----------------------------------------------------
    # 仓位
    # -----------------------------------------------------

    position_percent = st.slider(
        "📌 单次最大仓位",
        min_value=10,
        max_value=100,
        value=95,
        step=5
    )

    position_ratio = (
        position_percent / 100
    )

    # -----------------------------------------------------
    # 滑点
    # -----------------------------------------------------

    slippage_percent = st.number_input(
        "📉 滑点 %",
        min_value=0.0,
        max_value=2.0,
        value=0.10,
        step=0.01
    )

    slippage_rate = (
        slippage_percent / 100
    )

    # -----------------------------------------------------
    # 佣金
    # -----------------------------------------------------

    commission_percent = st.number_input(
        "💵 佣金 %",
        min_value=0.0,
        max_value=0.5,
        value=0.03,
        step=0.01
    )

    commission_rate = (
        commission_percent / 100
    )

    # -----------------------------------------------------
    # 印花税
    # -----------------------------------------------------

    if asset_key == "stock":

        stamp_tax_percent = st.number_input(
            "🏦 股票卖出印花税 %",
            min_value=0.0,
            max_value=1.0,
            value=0.05,
            step=0.01
        )

    else:

        stamp_tax_percent = 0.0

        st.info(
            "ETF不计股票印花税。"
        )

    stamp_tax_rate = (
        stamp_tax_percent / 100
    )

    # -----------------------------------------------------
    # 开始回测
    # -----------------------------------------------------

    if st.button(
        "🧪 开始严格回测",
        type="primary"
    ):

        try:

            df = load_data(
                code,
                asset_key
            )

            df = calculate_indicators(
                df
            )

            (
                results,
                trades_df,
                equity_df,
                backtest_data
            ) = strict_backtest(

                df=df,

                years=years_option,

                asset_type=asset_key,

                initial_capital=initial_capital,

                commission_rate=commission_rate,

                stamp_tax_rate=stamp_tax_rate,

                slippage_rate=slippage_rate,

                position_ratio=position_ratio
            )

        except Exception as e:

            st.error(
                "回测失败"
            )

            st.code(
                str(e)
            )

            st.stop()

        # =================================================
        # 回测信息
        # =================================================

        st.success(
            f"{asset_name} · "
            f"实际回测 "
            f"{results['actual_years']:.2f} 年"
        )

        # =================================================
        # 核心收益
        # =================================================

        st.subheader(
            "📊 收益结果"
        )

        col1, col2, col3 = st.columns(3)

        with col1:

            st.metric(
                "策略累计收益",
                f"{results['strategy_return']:.2f}%"
            )

        with col2:

            st.metric(
                "策略年化收益",
                f"{results['annual_return']:.2f}%"
            )

        with col3:

            st.metric(
                "买入持有",
                f"{results['buy_hold_return']:.2f}%"
            )

        # =================================================
        # 风险
        # =================================================

        st.subheader(
            "🛡️ 风险指标"
        )

        col1, col2, col3 = st.columns(3)

        with col1:

            st.metric(
                "最大回撤",
                f"{results['max_drawdown']:.2f}%"
            )

        with col2:

            st.metric(
                "Sharpe",
                f"{results['sharpe']:.2f}"
            )

        with col3:

            st.metric(
                "Calmar",
                f"{results['calmar']:.2f}"
            )

        # =================================================
        # 交易统计
        # =================================================

        st.subheader(
            "🔢 交易统计"
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
        # 策略评价
        # =================================================

        st.subheader(
            "🧠 策略评价"
        )

        if (
            results["strategy_return"]
            >
            results["buy_hold_return"]
        ):

            st.success(
                "🟢 策略累计收益跑赢了"
                "同期买入持有。"
            )

        else:

            st.warning(
                "🟡 策略累计收益没有跑赢"
                "同期买入持有。"
            )

        if results["sharpe"] >= 1:

            st.success(
                "🟢 Sharpe ≥ 1，"
                "风险收益表现相对较好。"
            )

        elif results["sharpe"] >= 0.5:

            st.info(
                "🟡 Sharpe 在0.5～1之间。"
            )

        else:

            st.warning(
                "🔴 Sharpe 较低，"
                "需要谨慎评估策略稳定性。"
            )

        # =================================================
        # 资金曲线
        # =================================================

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
        # 回撤
        # =================================================

        st.subheader(
            "📉 回撤曲线"
        )

        drawdown_chart = (
            equity_df[
                [
                    "日期",
                    "回撤"
                ]
            ]
            .set_index("日期")
        )

        st.line_chart(
            drawdown_chart
        )

        # =================================================
        # 交易记录
        # =================================================

        st.subheader(
            "📋 历史交易记录"
        )

        if trades_df.empty:

            st.warning(
                "这个周期没有完成交易。"
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

            display_df[
                "买入价格"
            ] = display_df[
                "买入价格"
            ].round(3)

            display_df[
                "卖出价格"
            ] = display_df[
                "卖出价格"
            ].round(3)

            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True
            )


# =========================================================
# 说明
# =========================================================

st.divider()

st.caption(
    "V2.1 严格回测："
    "下一交易日开盘执行、"
    "交易单位100股、"
    "佣金、股票卖出印花税、"
    "滑点、剩余现金、"
    "最大回撤、Sharpe、Calmar。"
)

st.caption(
    "⚠️ 历史回测不代表未来收益。"
    "本程序仅用于量化研究和学习，"
    "不构成投资建议。"
)
