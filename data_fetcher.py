import os
import time
import requests
import pandas as pd


STOCK_LIST_FILE = "stock_list.csv"
ETF_LIST_FILE = "etf_list.csv"


def load_codes(filename):

    if not os.path.exists(filename):
        raise FileNotFoundError(
            f"找不到 {filename}"
        )

    df = pd.read_csv(
        filename,
        dtype={"code": str}
    )

    return df["code"].str.zfill(6).tolist()


def get_yahoo_symbol(code, asset_type):

    # A股股票
    if asset_type == "stock":

        if code.startswith(("6", "68")):
            return f"{code}.SS"

        if code.startswith(("0", "3")):
            return f"{code}.SZ"

    # ETF
    elif asset_type == "etf":

        if code.startswith("5"):
            return f"{code}.SS"

        if code.startswith("1"):
            return f"{code}.SZ"

    raise ValueError(
        f"无法判断市场：{asset_type} {code}"
    )


def fetch_stock(code, asset_type):

    symbol = get_yahoo_symbol(
        code,
        asset_type
    )

    url = (
        f"https://query1.finance.yahoo.com/"
        f"v8/finance/chart/{symbol}"
    )

    params = {
        "range": "2y",
        "interval": "1d",
        "events": "history",
        "includeAdjustedClose": "true",
    }

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    print(
        f"正在获取 {asset_type} "
        f"{code} ({symbol}) ..."
    )

    response = requests.get(
        url,
        params=params,
        headers=headers,
        timeout=30,
    )

    print(
        "HTTP状态码:",
        response.status_code
    )

    response.raise_for_status()

    data = response.json()

    result = data.get(
        "chart",
        {}
    ).get(
        "result"
    )

    if not result:
        raise RuntimeError(
            f"{symbol} 没有返回行情数据"
        )

    result = result[0]

    timestamps = result.get(
        "timestamp"
    )

    quote = (
        result
        .get("indicators", {})
        .get("quote", [{}])[0]
    )

    if not timestamps:
        raise RuntimeError(
            "没有返回历史日期"
        )

    df = pd.DataFrame({
        "日期": pd.to_datetime(
            timestamps,
            unit="s"
        ).date,

        "开盘": quote.get("open"),

        "最高": quote.get("high"),

        "最低": quote.get("low"),

        "收盘": quote.get("close"),

        "成交量": quote.get("volume"),
    })

    df["日期"] = pd.to_datetime(
        df["日期"]
    )

    number_columns = [
        "开盘",
        "最高",
        "最低",
        "收盘",
        "成交量",
    ]

    for column in number_columns:

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

    if len(df) < 30:

        raise RuntimeError(
            f"数据太少：{len(df)} 条"
        )

    os.makedirs(
        "data",
        exist_ok=True
    )

    filename = (
        f"data/{asset_type}_{code}.csv"
    )

    df.to_csv(
        filename,
        index=False,
        encoding="utf-8-sig"
    )

    print(
        f"✅ {asset_type} {code} "
        f"成功：{len(df)}条"
    )

    print(
        "最新日期：",
        df.iloc[-1]["日期"]
    )

    print(
        "最新收盘：",
        df.iloc[-1]["收盘"]
    )


def run():

    stocks = load_codes(
        STOCK_LIST_FILE
    )

    etfs = load_codes(
        ETF_LIST_FILE
    )

    print(
        f"股票数量：{len(stocks)}"
    )

    print(
        f"ETF数量：{len(etfs)}"
    )

    success = 0
    failed = 0

    # =========================
    # 股票
    # =========================

    for code in stocks:

        try:

            fetch_stock(
                code,
                "stock"
            )

            success += 1

        except Exception as e:

            failed += 1

            print(
                f"❌ 股票 {code} 失败：{e}"
            )

        time.sleep(2)

    # =========================
    # ETF
    # =========================

    for code in etfs:

        try:

            fetch_stock(
                code,
                "etf"
            )

            success += 1

        except Exception as e:

            failed += 1

            print(
                f"❌ ETF {code} 失败：{e}"
            )

        time.sleep(2)

    print("")
    print("========================")
    print("数据更新完成")
    print(
        f"成功：{success}"
    )
    print(
        f"失败：{failed}"
    )
    print("========================")


if __name__ == "__main__":

    run()
