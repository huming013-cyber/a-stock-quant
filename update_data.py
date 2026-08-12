import os
import sys
import time
import requests
import pandas as pd


# =========================================================
# 基础设置
# =========================================================

DATA_DIR = "data"

STOCK_LIST = "stock_list.csv"
ETF_LIST = "etf_list.csv"

os.makedirs(DATA_DIR, exist_ok=True)

TODAY = pd.Timestamp.now().strftime("%Y%m%d")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120 Safari/537.36"
    )
}


# =========================================================
# 输出
# =========================================================

def log(text):
    print(text, flush=True)


# =========================================================
# 判断市场
# =========================================================

def get_market(code):

    code = str(code).zfill(6)

    # 上海
    if (
        code.startswith("6")
        or code.startswith("68")
        or code.startswith("5")
    ):
        return 1

    # 深圳
    if (
        code.startswith("0")
        or code.startswith("3")
        or code.startswith("159")
    ):
        return 0

    # 默认深圳
    return 0


def get_tencent_prefix(code):

    market = get_market(code)

    if market == 1:
        return "sh"

    return "sz"


# =========================================================
# 读取列表
# =========================================================

def load_list(filename):

    if not os.path.exists(filename):

        log(f"❌ 找不到 {filename}")

        return pd.DataFrame(
            columns=["code", "name"]
        )

    df = pd.read_csv(
        filename,
        dtype={"code": str}
    )

    if "code" not in df.columns:

        raise ValueError(
            f"{filename} 缺少 code 列"
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

    return df.reset_index(drop=True)


# =========================================================
# 东方财富接口
# =========================================================

def fetch_eastmoney(code):

    market = get_market(code)

    secid = f"{market}.{code}"

    url = (
        "https://push2his.eastmoney.com/"
        "api/qt/stock/kline/get"
    )

    params = {

        "secid": secid,

        "fields1":
            "f1,f2,f3,f4,f5,f6",

        "fields2":
            "f51,f52,f53,f54,f55,"
            "f56,f57,f58,f59,f60,f61",

        "klt": "101",

        # 前复权
        "fqt": "1",

        "beg": "0",

        "end": "20500000",

        "lmt": "5000"
    }

    response = requests.get(
        url,
        params=params,
        headers=HEADERS,
        timeout=20
    )

    response.raise_for_status()

    result = response.json()

    if not result.get("data"):

        raise ValueError(
            "东方财富没有返回data"
        )

    klines = result["data"].get(
        "klines"
    )

    if not klines:

        raise ValueError(
            "东方财富没有返回K线"
        )

    rows = []

    for item in klines:

        parts = item.split(",")

        if len(parts) < 7:
            continue

        rows.append({

            "日期": parts[0],

            "开盘": parts[1],

            "收盘": parts[2],

            "最高": parts[3],

            "最低": parts[4],

            "成交量": parts[5],

            "成交额": parts[6]
        })

    if not rows:

        raise ValueError(
            "东方财富K线解析失败"
        )

    return pd.DataFrame(rows)


# =========================================================
# 腾讯备用接口
# =========================================================

def fetch_tencent(code):

    prefix = get_tencent_prefix(code)

    symbol = prefix + code

    url = (
        "https://web.ifzq.gtimg.cn/"
        "appstock/app/fqkline/get"
    )

    params = {

        "_var": "kline_dayqfq",

        "param":
            f"{symbol},day,,,5000,qfqa"
    }

    response = requests.get(
        url,
        params=params,
        headers=HEADERS,
        timeout=20
    )

    response.raise_for_status()

    data = response.json()

    stock_data = (
        data
        .get("data", {})
        .get(symbol, {})
    )

    rows = (
        stock_data.get("qfqday")
        or stock_data.get("day")
        or []
    )

    if not rows:

        raise ValueError(
            "腾讯没有返回K线"
        )

    result = []

    for item in rows:

        if len(item) < 6:
            continue

        result.append({

            "日期": item[0],

            "开盘": item[1],

            "收盘": item[2],

            "最高": item[3],

            "最低": item[4],

            "成交量": item[5]
        })

    if not result:

        raise ValueError(
            "腾讯K线解析失败"
        )

    return pd.DataFrame(result)


# =========================================================
# 数据标准化
# =========================================================

def clean_data(df):

    required = [
        "日期",
        "开盘",
        "收盘",
        "最高",
        "最低",
        "成交量"
    ]

    for col in required:

        if col not in df.columns:

            raise ValueError(
                f"缺少字段：{col}"
            )

    df = df[
        required
    ].copy()

    df["日期"] = pd.to_datetime(
        df["日期"],
        errors="coerce"
    )

    for col in [
        "开盘",
        "收盘",
        "最高",
        "最低",
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

    df = df[
        (df["开盘"] > 0)
        &
        (df["收盘"] > 0)
    ]

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

        raise ValueError(
            f"有效数据只有 {len(df)} 条"
        )

    return df


# =========================================================
# 下载单个品种
# =========================================================

def fetch_data(code):

    east_error = None

    # -----------------------------------------------------
    # 第一数据源：东方财富
    # -----------------------------------------------------

    try:

        log(
            f"   → 东方财富：{code}"
        )

        df = fetch_eastmoney(
            code
        )

        df = clean_data(
            df
        )

        log(
            f"   ✅ 东方财富成功：{len(df)}条"
        )

        return df, "东方财富"

    except Exception as e:

        east_error = str(e)

        log(
            f"   ⚠️ 东方财富失败：{e}"
        )

    # -----------------------------------------------------
    # 第二数据源：腾讯
    # -----------------------------------------------------

    try:

        log(
            f"   → 腾讯备用接口：{code}"
        )

        df = fetch_tencent(
            code
        )

        df = clean_data(
            df
        )

        log(
            f"   ✅ 腾讯备用成功：{len(df)}条"
        )

        return df, "腾讯"

    except Exception as e:

        log(
            f"   ❌ 腾讯也失败：{e}"
        )

        raise RuntimeError(
            f"两个数据源都失败。"
            f"东方财富：{east_error}；"
            f"腾讯：{e}"
        )


# =========================================================
# 保存
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
# 更新一个品种
# =========================================================

def update_one(
    code,
    name,
    asset_type
):

    log("")
    log("=" * 60)

    log(
        f"📌 {asset_type.upper()} "
        f"{code} - {name}"
    )

    try:

        df, source = fetch_data(
            code
        )

        filename = save_data(
            df,
            asset_type,
            code
        )

        first_date = (
            df["日期"]
            .min()
            .strftime("%Y-%m-%d")
        )

        last_date = (
            df["日期"]
            .max()
            .strftime("%Y-%m-%d")
        )

        log(
            f"   数据源：{source}"
        )

        log(
            f"   数据量：{len(df)}"
        )

        log(
            f"   日期：{first_date}"
            f" → {last_date}"
        )

        log(
            f"   文件：{filename}"
        )

        log(
            "   ✅ 更新成功"
        )

        return True

    except Exception as e:

        log(
            f"   ❌ 更新失败：{e}"
        )

        return False


# =========================================================
# 主程序
# =========================================================

def main():

    log("")
    log("=" * 60)
    log("🚀 A股量化助手 V3.0 数据中心")
    log("=" * 60)

    stocks = load_list(
        STOCK_LIST
    )

    etfs = load_list(
        ETF_LIST
    )

    total = (
        len(stocks)
        +
        len(etfs)
    )

    if total == 0:

        log(
            "❌ 股票和ETF列表都是空的"
        )

        sys.exit(1)

    success = []

    failed = []

    # =====================================================
    # 股票
    # =====================================================

    for _, row in stocks.iterrows():

        ok = update_one(
            row["code"],
            row["name"],
            "stock"
        )

        if ok:

            success.append(
                f"股票 {row['code']} "
                f"{row['name']}"
            )

        else:

            failed.append(
                f"股票 {row['code']} "
                f"{row['name']}"
            )

        time.sleep(0.5)

    # =====================================================
    # ETF
    # =====================================================

    for _, row in etfs.iterrows():

        ok = update_one(
            row["code"],
            row["name"],
            "etf"
        )

        if ok:

            success.append(
                f"ETF {row['code']} "
                f"{row['name']}"
            )

        else:

            failed.append(
                f"ETF {row['code']} "
                f"{row['name']}"
            )

        time.sleep(0.5)

    # =====================================================
    # 总结
    # =====================================================

    log("")
    log("")
    log("=" * 60)
    log("📊 更新结果")
    log("=" * 60)

    log(
        f"总数：{total}"
    )

    log(
        f"成功：{len(success)}"
    )

    log(
        f"失败：{len(failed)}"
    )

    if success:

        log("")
        log("✅ 成功：")

        for item in success:

            log(
                f"   {item}"
            )

    if failed:

        log("")
        log("❌ 失败：")

        for item in failed:

            log(
                f"   {item}"
            )

        log("")
        log(
            "⚠️ 有品种更新失败。"
        )

        # 让 Actions 明确失败
        # 但已经告诉用户具体是哪一只

        sys.exit(1)

    log("")
    log(
        "🎉 所有股票和ETF更新成功！"
    )

    log("=" * 60)


if __name__ == "__main__":

    main()
