import os
import itertools
import streamlit as st
import pandas as pd
import numpy as np


# =========================================================
# 页面设置
# =========================================================

st.set_page_config(
    page_title="A股量化助手 V2.2",
    page_icon="📈",
    layout="wide"
)

st.title("📈 A股量化助手 V2.2")

st.caption(
    "训练集 / 测试集 · 自动参数优化 · 防止未来数据泄漏"
)
# =========================================================
# 数据刷新按钮
# =========================================================

refresh_col1, refresh_col2 = st.columns(
    [1, 5]
)

with refresh_col1:

    if st.button(
        "🔄 刷新数据",
        use_container_width=True
    ):

        st.cache_data.clear()

        st.rerun()

# =========================================================
# 读取股票 / ETF列表
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


stocks = load_list("stock_list.csv")

etfs = load_list("etf_list.csv")


# =========================================================
# 读取行情
# =========================================================

@st.cache_data
def load_data(code, asset_type):

    filename = (
        f"data/{asset_type}_{code}.csv"
    )

    if not os.path.exists(filename):

        raise FileNotFoundError(
            f"没有找到行情文件：{filename}"
        )

    df = pd.read_csv(filename)

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

    for col in number_columns:

        if col in df.columns:

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
        subset=["日期"]
    )

    df = df.reset_index(
        drop=True
    )

    return df


# =========================================================
# 技术指标
# =========================================================

def calculate_indicators(
    df,
    ma_short,
    ma_long,
    volume_window
):

    data = df.copy()

    # -----------------------------------------------------
    # MA
    # -----------------------------------------------------

    data["MA_SHORT"] = (
        data["收盘"]
        .rolling(ma_short)
        .mean()
    )

    data["MA_LONG"] = (
        data["收盘"]
        .rolling(ma_long)
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

    data["VOL_AVG"] = (
        data["成交量"]
        .rolling(volume_window)
        .mean()
    )

    # -----------------------------------------------------
    # 条件
    # -----------------------------------------------------

    condition_ma = (
        data["MA_SHORT"]
        >
        data["MA_LONG"]
    )

    condition_macd = (
        data["DIF"]
        >
        data["DEA"]
    )

    condition_volume = (
        data["成交量"]
        >
        data["VOL_AVG"]
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

    data["买入信号"] = (
        data["评分"] == 3
    )

    data["卖出信号"] = (
        data["评分"] == 0
    )

    return data


# =========================================================
# 回测函数
# =========================================================

def run_backtest(
    df,
    asset_type,
    initial_capital,
    commission_rate,
    stamp_tax_rate,
    slippage_rate,
    position_ratio
):

    data = df.copy()

    if len(data) < 60:

        return None

    cash = float(
        initial_capital
    )

    shares = 0

    entry_price = None

    entry_date = None

    trades = []

    equity_records = []

    # A股 / ETF统一按100份进行交易
    lot_size = 100

    # -----------------------------------------------------
    # 注意：
    #
    # i日收盘产生信号
    # i+1日开盘执行
    #
    # 因此绝不使用i+1日的任何数据来产生信号
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

        if (
            not np.isfinite(next_open)
            or next_open <= 0
        ):

            continue

        # =================================================
        # 买入
        # =================================================

        if (
            shares == 0
            and signal == 3
        ):

            available_cash = (
                cash
                * position_ratio
            )

            buy_price = (
                next_open
                * (1 + slippage_rate)
            )

            max_shares = int(
                available_cash
                /
                buy_price
                /
                lot_size
            ) * lot_size

            if max_shares <= 0:

                continue

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

            sell_price = (
                next_open
                * (1 - slippage_rate)
            )

            amount = (
                shares
                * sell_price
            )

            commission = max(
                amount
                * commission_rate,
                5
            )

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

            gross_cost = (
                shares
                * entry_price
            )

            trade_return = (
                net_amount
                /
                gross_cost
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
                        -
                        entry_date
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
    # 累计收益
    # =====================================================

    total_return = (
        final_equity
        /
        initial_capital
        - 1
    ) * 100

    # =====================================================
    # 年化收益
    # =====================================================

    days = (
        data["日期"].iloc[-1]
        -
        data["日期"].iloc[0]
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
        ** (1 / years)
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
    # 资金曲线
    # =====================================================

    equity_df = pd.DataFrame(
        equity_records
    )

    if equity_df.empty:

        return None

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
    # Sharpe
    # =====================================================

    equity_df["日收益"] = (
        equity_df["资产"]
        .pct_change()
        .fillna(0)
    )

    daily_std = (
        equity_df["日收益"].std()
    )

    if daily_std > 0:

        sharpe = (
            equity_df["日收益"].mean()
            /
            daily_std
            *
            np.sqrt(252)
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

        wins = (
            trades_df["收益率"] > 0
        )

        win_rate = (
            wins.mean()
            * 100
        )

        avg_win = (
            trades_df.loc[
                wins,
                "收益率"
            ].mean()
            if wins.any()
            else 0
        )

        avg_loss = (
            abs(
                trades_df.loc[
                    ~wins,
                    "收益率"
                ].mean()
            )
            if (~wins).any()
            else 0
        )

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
    # 综合评分
    # =====================================================

    # 优化目标：
    #
    # 收益越高越好
    # Sharpe越高越好
    # 最大回撤越小越好
    #
    # 避免单纯追求历史收益
    # =====================================================

    score = (
        annual_return
        +
        sharpe * 10
        +
        calmar * 5
        +
        min(
            total_trades,
            30
        ) * 0.2
    )

    return {

        "final_equity":
            final_equity,

        "total_return":
            total_return,

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

        "profit_loss_ratio":
            profit_loss_ratio,

        "score":
            score,

        "trades":
            trades_df,

        "equity":
            equity_df
    }


# =========================================================
# 参数优化
# =========================================================

def optimize_parameters(
    df,
    asset_type,
    initial_capital,
    commission_rate,
    stamp_tax_rate,
    slippage_rate,
    position_ratio
):

    # =====================================================
    # 参数搜索范围
    #
    # 控制数量，避免手机运行太慢
    # =====================================================

    ma_short_list = [
        5,
        10,
        15
    ]

    ma_long_list = [
        20,
        30,
        40,
        60
    ]

    volume_window_list = [
        10,
        20,
        30
    ]

    parameter_results = []

    # =====================================================
    # 网格搜索
    # =====================================================

    combinations = list(
        itertools.product(
            ma_short_list,
            ma_long_list,
            volume_window_list
        )
    )

    for (
        ma_short,
        ma_long,
        volume_window
    ) in combinations:

        if ma_short >= ma_long:

            continue

        test_df = calculate_indicators(
            df,
            ma_short,
            ma_long,
            volume_window
        )

        result = run_backtest(
            test_df,
            asset_type,
            initial_capital,
            commission_rate,
            stamp_tax_rate,
            slippage_rate,
            position_ratio
        )

        if result is None:

            continue

        parameter_results.append({

            "MA短周期":
                ma_short,

            "MA长周期":
                ma_long,

            "成交量周期":
                volume_window,

            "年化收益":
                result["annual_return"],

            "最大回撤":
                result["max_drawdown"],

            "Sharpe":
                result["sharpe"],

            "Calmar":
                result["calmar"],

            "交易次数":
                result["total_trades"],

            "胜率":
                result["win_rate"],

            "优化得分":
                result["score"]
        })

    results_df = pd.DataFrame(
        parameter_results
    )

    if results_df.empty:

        return None

    results_df = (
        results_df
        .sort_values(
            "优化得分",
            ascending=False
        )
        .reset_index(
            drop=True
        )
    )

    best = (
        results_df.iloc[0]
    )

    best_parameters = {

        "ma_short":
            int(best["MA短周期"]),

        "ma_long":
            int(best["MA长周期"]),

        "volume_window":
            int(best["成交量周期"])
    }

    return (
        best_parameters,
        results_df
    )


# =========================================================
# 选择股票 / ETF
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
        "V2.2 自动优化回测"
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

            raw_df = load_data(
                code,
                asset_key
            )

            df = calculate_indicators(
                raw_df,
                5,
                20,
                20
            )

        except Exception as e:

            st.error(
                "数据读取失败"
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
                f"{latest['收盘']:.3f}"
            )

        with col2:

            st.metric(
                "MA5",
                f"{latest['MA_SHORT']:.3f}"
            )

        with col3:

            st.metric(
                "MA20",
                f"{latest['MA_LONG']:.3f}"
            )

        score = int(
            latest["评分"]
        )

        st.subheader(
            "🤖 当前评分"
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

        st.subheader(
            "📈 价格与均线"
        )

        chart = df.tail(200)[
            [
                "日期",
                "收盘",
                "MA_SHORT",
                "MA_LONG"
            ]
        ].set_index(
            "日期"
        )

        st.line_chart(
            chart
        )


# =========================================================
# V2.2 自动优化回测
# =========================================================

else:

    st.subheader(
        "🧪 V2.2 自动优化回测"
    )

    st.info(
        "程序先在训练集寻找参数，"
        "然后锁定参数，在完全没有参与优化的测试集上验证。"
    )

    # -----------------------------------------------------
    # 回测周期
    # -----------------------------------------------------

    years = st.selectbox(
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
    # 训练集比例
    # -----------------------------------------------------

    train_percent = st.select_slider(
        "🧪 训练集比例",
        options=[
            50,
            60,
            70,
            80
        ],
        value=70
    )

    st.caption(
        f"训练集 {train_percent}% · "
        f"测试集 {100-train_percent}%"
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
        "📌 单次最大仓位 %",
        10,
        100,
        95,
        5
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
            "ETF不计算股票印花税。"
        )

    stamp_tax_rate = (
        stamp_tax_percent / 100
    )

    # -----------------------------------------------------
    # 开始
    # -----------------------------------------------------

    if st.button(
        "🤖 开始自动优化 + 样本外测试",
        type="primary"
    ):

        try:

            raw_df = load_data(
                code,
                asset_key
            )

        except Exception as e:

            st.error(
                "读取数据失败"
            )

            st.code(
                str(e)
            )

            st.stop()

        # =================================================
        # 选择历史区间
        # =================================================

        end_date = (
            raw_df["日期"].max()
        )

        if years == 0:

            start_date = (
                raw_df["日期"].min()
            )

        else:

            start_date = (
                end_date
                -
                pd.DateOffset(
                    years=years
                )
            )

        period_df = raw_df[
            raw_df["日期"] >= start_date
        ].copy()

        period_df = (
            period_df
            .reset_index(
                drop=True
            )
        )

        if len(period_df) < 100:

            st.error(
                "历史数据不足100个交易日，"
                "无法进行可靠的训练/测试。"
            )

            st.stop()

        # =================================================
        # 时间切分
        #
        # 非随机切分
        #
        # 前70%训练
        # 后30%测试
        #
        # 防止未来数据泄漏
        # =================================================

        split_index = int(
            len(period_df)
            * train_percent
            / 100
        )

        train_df = (
            period_df.iloc[
                :split_index
            ]
            .copy()
        )

        test_df = (
            period_df.iloc[
                split_index:
            ]
            .copy()
        )

        # =================================================
        # 训练集参数优化
        # =================================================

        st.subheader(
            "🔍 第一步：训练集自动优化"
        )

        progress = st.progress(
            0
        )

        combinations_count = (
            3 * 4 * 3
        )

        progress.progress(
            5
        )

        optimization = (
            optimize_parameters(

                train_df,

                asset_key,

                initial_capital,

                commission_rate,

                stamp_tax_rate,

                slippage_rate,

                position_ratio
            )
        )

        progress.progress(
            100
        )

        if optimization is None:

            st.error(
                "没有找到有效参数组合。"
            )

            st.stop()

        (
            best_parameters,
            optimization_df
        ) = optimization

        # =================================================
        # 最佳参数
        # =================================================

        st.success(
            "训练集参数优化完成。"
        )

        st.write(
            "### 🏆 最佳参数"
        )

        col1, col2, col3 = st.columns(3)

        with col1:

            st.metric(
                "MA短周期",
                best_parameters[
                    "ma_short"
                ]
            )

        with col2:

            st.metric(
                "MA长周期",
                best_parameters[
                    "ma_long"
                ]
            )

        with col3:

            st.metric(
                "成交量周期",
                best_parameters[
                    "volume_window"
                ]
            )

        # =================================================
        # 训练集结果
        # =================================================

        train_indicators = (
            calculate_indicators(
                train_df,
                best_parameters[
                    "ma_short"
                ],
                best_parameters[
                    "ma_long"
                ],
                best_parameters[
                    "volume_window"
                ]
            )
        )

        train_result = run_backtest(
            train_indicators,
            asset_key,
            initial_capital,
            commission_rate,
            stamp_tax_rate,
            slippage_rate,
            position_ratio
        )

        # =================================================
        # 测试集
        #
        # 非常重要：
        #
        # 这里使用已经锁定的参数。
        #
        # 不再优化。
        # =================================================

        st.subheader(
            "🧪 第二步：完全独立测试集"
        )

        test_indicators = (
            calculate_indicators(
                test_df,
                best_parameters[
                    "ma_short"
                ],
                best_parameters[
                    "ma_long"
                ],
                best_parameters[
                    "volume_window"
                ]
            )
        )

        test_result = run_backtest(
            test_indicators,
            asset_key,
            initial_capital,
            commission_rate,
            stamp_tax_rate,
            slippage_rate,
            position_ratio
        )

        if (
            train_result is None
            or test_result is None
        ):

            st.error(
                "训练集或测试集无法完成回测。"
            )

            st.stop()

        st.success(
            "测试集完成。测试集没有参与参数优化。"
        )

        # =================================================
        # 训练 / 测试对比
        # =================================================

        st.subheader(
            "📊 训练集 vs 测试集"
        )

        comparison = pd.DataFrame({

            "指标": [
                "累计收益",
                "年化收益",
                "最大回撤",
                "Sharpe",
                "Calmar",
                "交易次数",
                "胜率",
                "盈亏比"
            ],

            "训练集": [

                f"{train_result['total_return']:.2f}%",

                f"{train_result['annual_return']:.2f}%",

                f"{train_result['max_drawdown']:.2f}%",

                f"{train_result['sharpe']:.2f}",

                f"{train_result['calmar']:.2f}",

                train_result["total_trades"],

                f"{train_result['win_rate']:.2f}%",

                f"{train_result['profit_loss_ratio']:.2f}"
            ],

            "测试集": [

                f"{test_result['total_return']:.2f}%",

                f"{test_result['annual_return']:.2f}%",

                f"{test_result['max_drawdown']:.2f}%",

                f"{test_result['sharpe']:.2f}",

                f"{test_result['calmar']:.2f}",

                test_result["total_trades"],

                f"{test_result['win_rate']:.2f}%",

                f"{test_result['profit_loss_ratio']:.2f}"
            ]
        })

        st.dataframe(
            comparison,
            use_container_width=True,
            hide_index=True
        )

        # =================================================
        # 测试集核心结果
        # =================================================

        st.subheader(
            "🎯 最重要：测试集真实表现"
        )

        col1, col2, col3 = st.columns(3)

        with col1:

            st.metric(
                "测试集累计收益",
                f"{test_result['total_return']:.2f}%"
            )

        with col2:

            st.metric(
                "测试集年化收益",
                f"{test_result['annual_return']:.2f}%"
            )

        with col3:

            st.metric(
                "测试集最大回撤",
                f"{test_result['max_drawdown']:.2f}%"
            )

        col1, col2, col3 = st.columns(3)

        with col1:

            st.metric(
                "测试集Sharpe",
                f"{test_result['sharpe']:.2f}"
            )

        with col2:

            st.metric(
                "测试集胜率",
                f"{test_result['win_rate']:.2f}%"
            )

        with col3:

            st.metric(
                "测试集盈亏比",
                f"{test_result['profit_loss_ratio']:.2f}"
            )

        # =================================================
        # 买入持有
        # =================================================

        st.subheader(
            "📌 测试集 vs 买入持有"
        )

        col1, col2 = st.columns(2)

        with col1:

            st.metric(
                "策略",
                f"{test_result['total_return']:.2f}%"
            )

        with col2:

            st.metric(
                "买入持有",
                f"{test_result['buy_hold_return']:.2f}%"
            )

        if (
            test_result["total_return"]
            >
            test_result["buy_hold_return"]
        ):

            st.success(
                "🟢 测试集策略跑赢同期买入持有。"
            )

        else:

            st.warning(
                "🟡 测试集策略没有跑赢同期买入持有。"
            )

        # =================================================
        # 过拟合检查
        # =================================================

        st.subheader(
            "🔬 简单过拟合检查"
        )

        train_return = (
            train_result["annual_return"]
        )

        test_return = (
            test_result["annual_return"]
        )

        if train_return != 0:

            degradation = (
                1
                -
                test_return
                /
                train_return
            ) * 100

        else:

            degradation = 0

        st.metric(
            "测试集年化收益相对训练集变化",
            f"{-degradation:.2f}%"
        )

        if (
            test_return > 0
            and
            test_result["sharpe"] > 0.5
        ):

            st.success(
                "🟢 测试集仍保持正收益，"
                "初步说明参数具有一定样本外稳定性。"
            )

        elif test_return > 0:

            st.info(
                "🟡 测试集仍盈利，"
                "但风险调整收益一般。"
            )

        else:

            st.error(
                "🔴 测试集亏损。"
                "模型可能存在过拟合或策略本身没有优势。"
            )

        # =================================================
        # 测试集资金曲线
        # =================================================

        st.subheader(
            "📈 测试集资金曲线"
        )

        test_equity_chart = (
            test_result["equity"][
                [
                    "日期",
                    "资产"
                ]
            ]
            .set_index("日期")
        )

        st.line_chart(
            test_equity_chart
        )

        # =================================================
        # 测试集回撤
        # =================================================

        st.subheader(
            "📉 测试集回撤"
        )

        drawdown_chart = (
            test_result["equity"][
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
        # 最佳参数排行榜
        # =================================================

        st.subheader(
            "🏆 训练集参数排行榜"
        )

        ranking = (
            optimization_df
            .head(10)
            .copy()
        )

        for col in [
            "年化收益",
            "最大回撤",
            "Sharpe",
            "Calmar",
            "胜率",
            "优化得分"
        ]:

            ranking[col] = (
                ranking[col]
                .round(2)
            )

        st.dataframe(
            ranking,
            use_container_width=True,
            hide_index=True
        )

        # =================================================
        # 测试交易
        # =================================================

        st.subheader(
            "📋 测试集交易记录"
        )

        if test_result[
            "trades"
        ].empty:

            st.warning(
                "测试集没有完成交易。"
            )

        else:

            trades_display = (
                test_result[
                    "trades"
                ].copy()
            )

            trades_display[
                "收益率"
            ] = trades_display[
                "收益率"
            ].round(2)

            trades_display[
                "买入价格"
            ] = trades_display[
                "买入价格"
            ].round(3)

            trades_display[
                "卖出价格"
            ] = trades_display[
                "卖出价格"
            ].round(3)

            st.dataframe(
                trades_display,
                use_container_width=True,
                hide_index=True
            )


# =========================================================
# 底部说明
# =========================================================

st.divider()

st.caption(
    "V2.2采用时间顺序训练/测试切分。"
    "参数只允许使用训练集历史数据确定。"
)

st.caption(
    "测试集完全不参与参数搜索，"
    "用于检查模型样本外表现。"
)

st.caption(
    "⚠️ 历史回测不代表未来收益。"
    "本程序仅用于量化研究和学习，"
    "不构成投资建议。"
)
