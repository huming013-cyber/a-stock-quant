import os
import time
import requests
import pandas as pd


# =========================================================
# 基本设置
# =========================================================

DATA_DIR = "data"

STOCK_LIST = "stock_list.csv"
ETF_LIST = "etf_list.csv"

os.makedirs(DATA_DIR, exist_ok=True)


# =========================================================
# Eastmoney 行情接口
# =========================================================

URL = (
    "https://push2his.eastmoney.com/api/qt/stock/kline/get"
)


HEADERS = {
    "User-Agent":
        "Mozilla/5.0 "
        "(iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) "
        "Version/17.0 Mobile/15E148 Safari/604.1"
}


# =========================================================
# 判断市场
# =========================================================

def get_secid(code):

    code = str(code).zfill(6)

    # 上海
    if code.startswith(
        (
            "5",
            "6",
            "68",
            "11"
        )
    ):
        return f"1.{code}"

    # 深圳
    return f"0.{code}"


# =========================================================
# 下载单只证券
# =========================================================

def download_history(code):

    code = str(code).zfill(6)

    secid = get_secid(code)

    params = {

        "secid":
            secid,

        "klt":
            "101",

        "fqt":
            "1",

        "beg":
            "20100101",

        "end":
            "20500101",

        "fields1":
            "f1,f2,f3,f4,f5,f6",

        "fields2":
            "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",

        "ut":
            "fa5fd1943c7b386f172d6893dbfba10b"
    }

    response = requests.get(
        URL,
        params=params,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    result = response.json()

    data = result.get("data")

    if not data:

        raise ValueError(
            f"{code} 没有获取到行情数据"
        )

    klines = data.get("klines")

    if not klines:

        raise ValueError(
            f"{code} K线数据为空"
        )

    records = []

    for row in klines:

        parts = row.split(",")

        if len(parts) < 7:

            continue

        records.append({

            "日期":
                parts[0],

            "开盘":
                parts[1],

            "收盘":
                parts[2],

            "最高":
                parts[3],

            "最低":
                parts[4],

            "成交量":
                parts[5],

            "成交额":
                parts[6]
        })

    df = pd.DataFrame(
        records
    )

    if df.empty:

        raise ValueError(
            f"{code} 数据为空"
        )

    # -----------------------------------------------------
    # 类型转换
    # -----------------------------------------------------

    df["日期"] = pd.to_datetime(
        df["日期"],
        errors="coerce"
    )

    numeric_columns = [
        "开盘",
        "收盘",
        "最高",
        "最低",
        "成交量",
        "成交额"
    ]

    for column in numeric_columns:

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
# 读取列表
# =========================================================

def load_codes(filename):

    if not os.path.exists(filename):

        print(
            f"⚠️ 找不到 {filename}"
        )

        return []

    df = pd.read_csv(
        filename,
        dtype={
            "code": str
        }
    )

    if "code" not in df.columns:

        print(
            f"⚠️ {filename} 没有 code 列"
        )

        return []

    codes = (
        df["code"]
        .astype(str)
        .str.extract(
            r"(\d{6})"
        )[0]
        .dropna()
        .unique()
        .tolist()
    )

    return codes


# =========================================================
# 更新股票
# =========================================================

def update_assets(
    codes,
    asset_type
):

    success = 0

    failed = 0

    for index, code in enumerate(
        codes,
        start=1
    ):

        print(
            f"\n[{index}/{len(codes)}] "
            f"正在更新 {asset_type} {code}"
        )

        try:

            df = download_history(
                code
            )

            filename = (
                f"{DATA_DIR}/"
                f"{asset_type}_{code}.csv"
            )

            df.to_csv(
                filename,
                index=False,
                encoding="utf-8-sig"
            )

            print(
                f"✅ {code} 更新成功 "
                f"({len(df)}条)"
            )

            success += 1

        except Exception as e:

            print(
                f"❌ {code} 更新失败：{e}"
            )

            failed += 1

        # 避免请求过快
        time.sleep(1)

    return success, failed


# =========================================================
# 主程序
# =========================================================

def main():

    print("=" * 60)

    print(
        "📈 A股量化 V2.3 自动行情更新"
    )

    print("=" * 60)

    # -----------------------------------------------------
    # 股票
    # -----------------------------------------------------

    stock_codes = load_codes(
        STOCK_LIST
    )

    print(
        f"\n📊 股票数量："
        f"{len(stock_codes)}"
    )

    stock_success, stock_failed = (
        update_assets(
            stock_codes,
            "stock"
        )
    )

    # -----------------------------------------------------
    # ETF
    # -----------------------------------------------------

    etf_codes = load_codes(
        ETF_LIST
    )

    print(
        f"\n📦 ETF数量："
        f"{len(etf_codes)}"
    )

    etf_success, etf_failed = (
        update_assets(
            etf_codes,
            "etf"
        )
    )

    # -----------------------------------------------------
    # 汇总
    # -----------------------------------------------------

    print("\n" + "=" * 60)

    print(
        "📊 更新完成"
    )

    print("=" * 60)

    print(
        f"股票：成功 {stock_success} "
        f"失败 {stock_failed}"
    )

    print(
        f"ETF：成功 {etf_success} "
        f"失败 {etf_failed}"
    )

    print("=" * 60)


if __name__ == "__main__":

    main()
