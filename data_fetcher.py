import os
import requests
import pandas as pd


STOCKS = [
    "600900",
]


def get_yahoo_symbol(code):

    if code.startswith(("6", "68")):
        return f"{code}.SS"

    if code.startswith(("0", "3")):
        return f"{code}.SZ"

    raise ValueError(f"不支持的股票代码：{code}")


def fetch_stock(code):

    symbol = get_yahoo_symbol(code)

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

    print(f"正在获取 {code} ({symbol}) ...")

    response = requests.get(
        url,
        params=params,
        headers=headers,
        timeout=30,
    )

    print("HTTP状态码:", response.status_code)

    response.raise_for_status()

    data = response.json()

    if not data.get("chart"):
        raise RuntimeError(
            "Yahoo Finance 返回数据异常"
        )

    result = data["chart"]["result"]

    if not result:
        raise RuntimeError(
            f"没有找到 {symbol} 的行情数据"
        )

    result = result[0]

    timestamps = result.get("timestamp")
    quote = result["indicators"]["quote"][0]

    if not timestamps:
        raise RuntimeError(
            "没有返回历史交易日期"
        )

    df = pd.DataFrame({
        "日期": pd.to_datetime(
            timestamps,
            unit="s"
        ).date,

        "开盘": quote["open"],

        "最高": quote["high"],

        "最低": quote["low"],

        "收盘": quote["close"],

        "成交量": quote["volume"],
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
            f"获取到的数据太少：{len(df)} 条"
        )

    os.makedirs(
        "data",
        exist_ok=True
    )

    filename = f"data/{code}.csv"

    df.to_csv(
        filename,
        index=False,
        encoding="utf-8-sig"
    )

    print(
        f"✅ {code} 获取成功："
        f"{len(df)} 条"
    )

    print(
        "最新日期：",
        df.iloc[-1]["日期"]
    )

    print(
        "最新收盘价：",
        df.iloc[-1]["收盘"]
    )


if __name__ == "__main__":

    for code in STOCKS:

        fetch_stock(code)
