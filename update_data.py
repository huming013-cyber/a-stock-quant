import os
import sys
import time
import traceback

import pandas as pd
import akshare as ak


# =========================================================
# 基础设置
# =========================================================

DATA_DIR = "data"

STOCK_LIST = "stock_list.csv"

ETF_LIST = "etf_list.csv"

os.makedirs(DATA_DIR, exist_ok=True)


# =========================================================
# 统一输出
# =========================================================

def log(message):

    print(message, flush=True)


# =========================================================
# 读取列表
# =========================================================

def load_list(filename):

    log("")
    log("=" * 60)
    log(f"读取列表：{filename}")
    log("=" * 60)

    if not os.path.exists(filename):

        log(f"❌ 文件不存在：{filename}")

        return pd.DataFrame(
            columns=["code", "name"]
        )

    try:

        df = pd.read_csv(
            filename,
            dtype={"code": str}
        )

    except Exception as e:

        log(f"❌ 读取失败：{filename}")
        log(str(e))

        return pd.DataFrame(
            columns=["code", "name"]
        )

    if "code" not in df.columns:

        log(
            f"❌ {filename} 缺少 code 列"
        )

        return pd.DataFrame(
            columns=["code", "name"]
        )

    if "name" not in df.columns:

        df["name"] = ""

    df["code"] = (
        df["code"]
        .astype(str)
        .str.strip()
        .str.replace(
            ".0",
            "",
            regex=False
        )
        .str.zfill(6)
    )

    df = df[
        df["code"].str.len() == 6
    ]

    df = df.drop_duplicates(
        subset=["code"]
    )

    df = df.reset_index(
        drop=True
    )

    log(
        f"✅ 共发现 {len(df)} 个品种"
    )

    return df


# =========================================================
# 数据清洗
# =========================================================

def clean_data(df):

    if df is None:

        raise ValueError(
            "下载结果为空"
        )

    if df.empty:

        raise ValueError(
            "下载结果为空"
        )

    # -----------------------------------------------------
    # 自动识别列名
    # -----------------------------------------------------

    column_mapping = {}

    possible_columns = {

        "日期": [
            "日期",
            "date",
            "Date"
        ],

        "开盘": [
            "开盘",
            "开盘价",
            "open",
            "Open"
        ],

        "最高": [
            "最高",
            "最高价",
            "high",
            "High"
        ],

        "最低": [
            "最低",
            "最低价",
            "low",
            "Low"
        ],

        "收盘": [
            "收盘",
            "收盘价",
            "close",
            "Close"
        ],

        "成交量": [
            "成交量",
            "volume",
            "Volume"
        ]
    }

    for standard_name, names in possible_columns.items():

        for name in names:

            if name in df.columns:

                column_mapping[name] = standard_name

                break

    df = df.rename(
        columns=column_mapping
    )

    required_columns = [
        "日期",
        "开盘",
        "最高",
        "最低",
        "收盘",
        "成交量"
    ]

    missing_columns = [
        col
        for col in required_columns
        if col not in df.columns
    ]

    if missing_columns:

        raise ValueError(
            "缺少必要字段："
            + ", ".join(missing_columns)
        )

    df = df[
        required_columns
    ].copy()

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

    number_columns = [
        "开盘",
        "最高",
        "最低",
        "收盘",
        "成交量"
    ]

    for col in number_columns:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    # -----------------------------------------------------
    # 删除无效数据
    # -----------------------------------------------------

    df = df.dropna(
        subset=[
            "日期",
            "开盘",
            "收盘"
        ]
    )

    # -----------------------------------------------------
    # 删除价格 <= 0
    # -----------------------------------------------------

    df = df[
        (df["开盘"] > 0)
        &
        (df["收盘"] > 0)
    ]

    # -----------------------------------------------------
    # 排序
    # -----------------------------------------------------

    df = df.sort_values(
        "日期"
    )

    # -----------------------------------------------------
    # 删除重复日期
    # -----------------------------------------------------

    df = df.drop_duplicates(
        subset=["日期"],
        keep="last"
    )

    df = df.reset_index(
        drop=True
    )

    if df.empty:

        raise ValueError(
            "清洗后没有有效数据"
        )

    return df


# =========================================================
# 下载股票
# =========================================================

def download_stock(code):

    log(
        f"📥 正在下载股票：{code}"
    )

    try:

        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date="20000101",
            end_date=pd.Timestamp.now().strftime(
                "%Y%m%d"
            ),
            adjust="qfq"
        )

        return df

    except Exception as e:

        log(
            f"❌ 股票 {code} 下载失败"
        )

        log(
            str(e)
        )

        return None


# =========================================================
# 下载ETF
# =========================================================

def download_etf(code):

    log(
        f"📥 正在下载ETF：{code}"
    )

    try:

        df = ak.fund_etf_hist_em(
            symbol=code,
            period="daily",
            start_date="20000101",
            end_date=pd.Timestamp.now().strftime(
                "%Y%m%d"
            ),
            adjust=""
        )

        return df

    except Exception as e:

        log(
            f"❌ ETF {code} 下载失败"
        )

        log(
            str(e)
        )

        return None


# =========================================================
# 保存数据
# =========================================================

def save_data(
    df,
    asset_type,
    code
):

    filename = os.path.join(
        DATA_DIR,
        f"{asset_type}_{code}.csv"
    )

    df.to_csv(
        filename,
        index=False,
        encoding="utf-8-sig"
    )

    return filename


# =========================================================
# 更新单个品种
# =========================================================

def update_one(
    code,
    name,
    asset_type
):

    log("")
    log("-" * 60)
    log(
        f"开始处理：{code} - {name}"
    )
    log(
        f"类型：{asset_type}"
    )
    log("-" * 60)

    try:

        # -------------------------------------------------
        # 下载
        # -------------------------------------------------

        if asset_type == "stock":

            raw_df = download_stock(
                code
            )

        else:

            raw_df = download_etf(
                code
            )

        # -------------------------------------------------
        # 下载失败
        # -------------------------------------------------

        if raw_df is None:

            raise ValueError(
                "API没有返回有效数据"
            )

        # -------------------------------------------------
        # 清洗
        # -------------------------------------------------

        df = clean_data(
            raw_df
        )

        # -------------------------------------------------
        # 数据量检查
        # -------------------------------------------------

        if len(df) < 30:

            raise ValueError(
                f"有效数据只有 {len(df)} 条，数量太少"
            )

        # -------------------------------------------------
        # 保存
        # -------------------------------------------------

        filename = save_data(
            df,
            asset_type,
            code
        )

        # -------------------------------------------------
        # 检查保存结果
        # -------------------------------------------------

        if not os.path.exists(
            filename
        ):

            raise ValueError(
                "CSV文件保存失败"
            )

        # -------------------------------------------------
        # 输出结果
        # -------------------------------------------------

        first_date = (
            df["日期"].min()
            .strftime("%Y-%m-%d")
        )

        last_date = (
            df["日期"].max()
            .strftime("%Y-%m-%d")
        )

        log("")
        log(
            f"✅ {code} 更新成功"
        )

        log(
            f"数据量：{len(df)}"
        )

        log(
            f"开始日期：{first_date}"
        )

        log(
            f"最新日期：{last_date}"
        )

        log(
            f"文件：{filename}"
        )

        return True

    except Exception as e:

        log("")
        log(
            f"❌ {code} 更新失败"
        )

        log(
            f"原因：{str(e)}"
        )

        return False


# =========================================================
# 检查已有数据
# =========================================================

def check_existing_data(
    code,
    asset_type
):

    filename = os.path.join(
        DATA_DIR,
        f"{asset_type}_{code}.csv"
    )

    if not os.path.exists(
        filename
    ):

        return False

    try:

        df = pd.read_csv(
            filename
        )

        if df.empty:

            return False

        required_columns = [
            "日期",
            "开盘",
            "收盘"
        ]

        for col in required_columns:

            if col not in df.columns:

                return False

        return True

    except Exception:

        return False


# =========================================================
# 主程序
# =========================================================

def main():

    start_time = time.time()

    log("")
    log("=" * 60)
    log("🚀 A股量化助手 V3 数据更新程序")
    log("=" * 60)
    log("")

    # =====================================================
    # 读取股票
    # =====================================================

    stocks = load_list(
        STOCK_LIST
    )

    # =====================================================
    # 读取ETF
    # =====================================================

    etfs = load_list(
        ETF_LIST
    )

    total_count = (
        len(stocks)
        +
        len(etfs)
    )

    if total_count == 0:

        log("")
        log(
            "❌ 没有找到任何股票或ETF"
        )

        sys.exit(1)

    log("")
    log("=" * 60)
    log(
        f"准备更新 {total_count} 个品种"
    )
    log(
        f"股票：{len(stocks)}"
    )
    log(
        f"ETF：{len(etfs)}"
    )
    log("=" * 60)

    success_list = []

    failed_list = []

    # =====================================================
    # 股票
    # =====================================================

    for _, row in stocks.iterrows():

        code = row["code"]

        name = row["name"]

        success = update_one(
            code,
            name,
            "stock"
        )

        if success:

            success_list.append(
                f"股票 {code} {name}"
            )

        else:

            failed_list.append(
                f"股票 {code} {name}"
            )

        # 防止请求过快
        time.sleep(1)

    # =====================================================
    # ETF
    # =====================================================

    for _, row in etfs.iterrows():

        code = row["code"]

        name = row["name"]

        success = update_one(
            code,
            name,
            "etf"
        )

        if success:

            success_list.append(
                f"ETF {code} {name}"
            )

        else:

            failed_list.append(
                f"ETF {code} {name}"
            )

        # 防止请求过快
        time.sleep(1)

    # =====================================================
    # 最终报告
    # =====================================================

    elapsed = (
        time.time()
        -
        start_time
    )

    log("")
    log("")
    log("=" * 60)
    log("📊 数据更新结果")
    log("=" * 60)

    log("")
    log(
        f"总数量：{total_count}"
    )

    log(
        f"成功：{len(success_list)}"
    )

    log(
        f"失败：{len(failed_list)}"
    )

    log(
        f"耗时：{elapsed:.1f} 秒"
    )

    # =====================================================
    # 成功列表
    # =====================================================

    if success_list:

        log("")
        log("✅ 成功列表")

        for item in success_list:

            log(
                f"   {item}"
            )

    # =====================================================
    # 失败列表
    # =====================================================

    if failed_list:

        log("")
        log("❌ 失败列表")

        for item in failed_list:

            log(
                f"   {item}"
            )

    # =====================================================
    # 最终状态
    # =====================================================

    log("")
    log("=" * 60)

    if failed_list:

        log(
            "⚠️ 数据更新完成，但存在失败品种。"
        )

        log(
            "请根据上面的失败原因检查。"
        )

        # 注意：
        # 不直接 sys.exit(1)
        #
        # 防止一个ETF失败导致整个Actions
        # 完全停止。

    else:

        log(
            "🎉 所有股票和ETF更新成功！"
        )

    log("=" * 60)


# =========================================================
# 程序入口
# =========================================================

if __name__ == "__main__":

    try:

        main()

    except Exception as e:

        log("")
        log("=" * 60)
        log("❌ 程序发生严重错误")
        log("=" * 60)

        log(
            str(e)
        )

        log("")
        log(
            "详细错误："
        )

        traceback.print_exc()

        # 严重错误才让Actions失败
        sys.exit(1)
