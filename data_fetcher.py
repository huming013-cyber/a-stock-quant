import os
import pandas as pd
import akshare as ak


STOCKS = [
    "600900",
]


def fetch_stock(code):
    print(f"正在获取 {code} ...")

    df = ak.stock_zh_a_hist(
        symbol=code,
        period="daily",
        start_date="20250101",
        end_date="20500101",
        adjust="qfq",
    )

    if df is None or df.empty:
        raise RuntimeError(f"{code} 没有获取到数据")

    os.makedirs("data", exist_ok=True)

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


if __name__ == "__main__":

    for code in STOCKS:
        fetch_stock(code)
