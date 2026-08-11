import os
import time
import requests
import pandas as pd


# =========================================================
# A股量化 V2.3.1 自动行情更新
# 股票 + ETF
# =========================================================

DATA_DIR = "data"

STOCK_LIST = "stock_list.csv"
ETF_LIST = "etf_list.csv"

os.makedirs(DATA_DIR, exist_ok=True)


# =========================================================
# 东方财富历史行情接口
# =========================================================

URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) "
        "Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    "Referer": "https://quote.eastmoney.com/"
}


# =========================================================
# 判断交易所
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
# 下载历史行情
# =========================================================

def download_history(code, retries=3):

    code = str(code).zfill(6)

    secid = get_secid(code)

    params = {
        "secid": secid,

        # 日线
        "klt": "101",

        # 前复权
        "fqt": "1",

        # 从2010年开始
        "beg": "20100101",

        # 到未来
        "end": "20500101",

        "fields1": "f1,f2,f3,f4,f5,f6",

        "fields2": (
            "f51,f52,f53,f54,f55,"
            "f56,f57,f58,f59,f60,f61"
        ),

        "ut": (
            "fa5fd1943c7b386f172d6893dbfba10b"
        )
    }

    last_error = None

    for attempt in range(1, retries + 1):

        try:

            print(
                f"  第 {attempt}/{retries} 次请求..."
            )

            session = requests.Session()

            response = session.get(
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
                    f"{code} 没有返回 data"
                )

            klines = data.get("klines")

            if not klines:

                raise ValueError(
                    f"{code} 没有返回K线数据"
                )

            records = []

            for row in klines:

                parts = row.split(",")

                if len(parts) < 7:
                    continue

                records.append({
                    "日期": parts[0],
                    "开盘": parts[1],
                    "收盘": parts[2],
                    "最高": parts[3],
                    "最低": parts[4],
                    "成交量": parts[5],
                    "成交额": parts[6]
                })

            df = pd.DataFrame(records)

            if df.empty:

                raise ValueError(
                    f"{code} 数据为空"
                )

            # -------------------------------------------------
            # 数据类型
            # -------------------------------------------------

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

            # -------------------------------------------------
            # 最低数据量检查
            # -------------------------------------------------

            if len(df) < 30:

                raise ValueError(
                    f"{code} 只有 {len(df)} 条数据，"
                    f"少于30条，暂不保存"
                )

            return df

        except Exception as e:

            last_error = e

            print(
                f"  ⚠️ 第 {attempt} 次失败：{e}"
            )

            if attempt < retries:

                print(
                    "  等待5秒后重试..."
                )

                time.sleep(5)

    raise RuntimeError(
        f"{code} 连续 {retries} 次获取失败："
        f"{last_error}"
    )


# =========================================================
# 读取股票 / ETF列表
# =========================================================

def load_codes(filename):

    if not os.path.exists(filename):

        raise FileNotFoundError(
            f"找不到 {filename}"
        )

    df = pd.read_csv(
        filename,
        dtype={
            "code": str
        }
    )

    if "code" not in df.columns:

        raise ValueError(
            f"{filename} 缺少 code 列"
        )

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
# 更新股票 / ETF
# =========================================================

def update_assets(codes, asset_type):

    success_codes = []

    failed_codes = []

    print(
        f"\n{'=' * 60}"
    )

    print(
        f"开始更新 {asset_type}"
    )

    print(
        f"共 {len(codes)} 个"
    )

    print(
        f"{'=' * 60}"
    )

    for index, code in enumerate(
        codes,
        start=1
    ):

        print(
            f"\n[{index}/{len(codes)}] "
            f"{asset_type} {code}"
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
                f"✅ {code} 更新成功"
            )

            print(
                f"   数据：{len(df)} 条"
            )

            print(
                f"   日期："
                f"{df['日期'].iloc[0].date()} "
                f"→ "
                f"{df['日期'].iloc[-1].date()}"
            )

            success_codes.append(
                code
            )

        except Exception as e:

            print(
                f"❌ {code} 更新失败"
            )

            print(
                f"   原因：{e}"
            )

            failed_codes.append(
                code
            )

        # 请求间隔
        time.sleep(2)

    return (
        success_codes,
        failed_codes
    )


# =========================================================
# 主程序
# =========================================================

def main():

    print("\n")
    print("=" * 60)
    print("📈 A股量化 V2.3.1 自动行情更新")
    print("=" * 60)

    # =====================================================
    # 股票
    # =====================================================

    stock_codes = load_codes(
        STOCK_LIST
    )

    print(
        f"\n📊 股票数量："
        f"{len(stock_codes)}"
    )

    (
        stock_success,
        stock_failed
    ) = update_assets(
        stock_codes,
        "stock"
    )

    # =====================================================
    # ETF
    # =====================================================

    etf_codes = load_codes(
        ETF_LIST
    )

    print(
        f"\n📦 ETF数量："
        f"{len(etf_codes)}"
    )

    (
        etf_success,
        etf_failed
    ) = update_assets(
        etf_codes,
        "etf"
    )

    # =====================================================
    # 最终报告
    # =====================================================

    print("\n")
    print("=" * 60)
    print("📊 行情更新报告")
    print("=" * 60)

    print(
        f"\n股票："
        f"成功 {len(stock_success)}"
        f" / 失败 {len(stock_failed)}"
    )

    print(
        f"ETF："
        f"成功 {len(etf_success)}"
        f" / 失败 {len(etf_failed)}"
    )

    if stock_failed:

        print(
            "\n❌ 股票失败："
        )

        for code in stock_failed:

            print(
                f"   {code}"
            )

    if etf_failed:

        print(
            "\n❌ ETF失败："
        )

        for code in etf_failed:

            print(
                f"   {code}"
            )

    print(
        "\n" + "=" * 60
    )

    # =====================================================
    # 只要有任何失败，就让 GitHub Actions 失败
    # =====================================================

    total_failed = (
        len(stock_failed)
        +
        len(etf_failed)
    )

    if total_failed > 0:

        raise RuntimeError(
            f"共有 {total_failed} 个证券更新失败"
        )

    print(
        "🎉 所有股票和ETF更新成功！"
    )

    print(
        "=" * 60
    )


if __name__ == "__main__":

    main()
