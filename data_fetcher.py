import os
import requests
import pandas as pd


STOCKS = [
    "600900",
]


def get_market_prefix(code):
    if code.startswith(("6", "68")):
        return "sh"
    elif code.startswith(("0", "3")):
        return "sz"
    else:
        raise ValueError(f"暂不支持股票代码：{code}")


def fetch_stock(code):

    market = get_market_prefix(code)

    symbol = f"{market}{code}"

    url = (
        "https://web.ifzq.gtimg.cn/"
        "app/kline/kline"
    )

    params = {
        "param": f"{symbol},day,1,0,500,640,qfq"
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        ),
        "Referer": "https://gu.qq.com/",
    }

    print(f"正在获取 {code} ...")

    response = requests.get(
        url,
        params=params,
        headers=headers,
        timeout=20,
    )

    response.raise_for_status()

    data = response.json()

    stock_data = data.get("data", {})

    if symbol not in stock_data:
        raise RuntimeError(
            f"接口没有返回 {symbol} 的数据"
        )

    stock_info = stock_data[symbol]

    # 腾讯接口通常把日K放在 day
    klines = stock_info.get("day")

    if not klines:
        raise RuntimeError(
            f"{code} 没有返回日K数据"
        )

    rows = []

    for item in klines:

        if len(item) < 6:
            continue

        rows.append([
            item[0],
            item[1],
            item[2],
            item[3],
            item[4],
            item[5],
        ])

    if not rows:
        raise RuntimeError(
            f"{code} K线数据为空"
        )

    df = pd.DataFrame(
        rows,
        columns=[
            "日期",
            "开盘",
            "收盘",
            "最高",
            "最低",
            "成交量",
        ],
    )

    df["日期"] = pd.to_datetime(
        df["日期"]
    )

    number_columns = [
        "开盘",
        "收盘",
        "最高",
        "最低",
        "成交量",
    ]

    for column in number_columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df = df.sort_values("日期")

    df = df.reset_index(drop=True)

    os.makedirs(
        "data",
        exist_ok=True,
    )

    filename = f"data/{code}.csv"

    df.to_csv(
        filename,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        f"{code} 获取成功："
        f"{len(df)} 条数据"
    )

    print(
        f"最新日期："
        f"{df.iloc[-1]['日期']}"
    )


if __name__ == "__main__":

    for code in STOCKS:

        try:

            fetch_stock(code)

        except Exception as e:

            print(
                f"{code} 获取失败：{e}"
            )

            raise
