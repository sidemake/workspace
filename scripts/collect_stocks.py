#!/usr/bin/env python3
"""관심 종목 현재가 수집기.

config/stocks.json 의 종목을 차례로 조회해 data/stocks.json 에 기록한다.
1순위는 네이버 증권, 실패하면 야후 파이낸스로 넘어간다. 둘 다 공식 제공 API가 아니므로
응답 형식이 바뀌면 이 파일의 fetch_naver / fetch_yahoo 를 고쳐야 한다.

사용법: collect_stocks.py <config/stocks.json> <data 폴더>
"""
import datetime
import json
import pathlib
import sys
import urllib.request

KST = datetime.timezone(datetime.timedelta(hours=9))
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) workspace-dashboard"}


def get_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as res:
        return json.loads(res.read().decode("utf-8"))


def to_number(text):
    """'58,300' 이나 '-1.60' 같은 문자열을 숫자로 바꾼다."""
    if isinstance(text, (int, float)):
        return text
    return float(str(text).replace(",", "").replace("+", "").strip())


def fetch_naver(stock):
    d = get_json(f"https://m.stock.naver.com/api/stock/{stock['code']}/basic")
    return {
        "api_name": d.get("stockName"),
        "price": int(to_number(d["closePrice"])),
        "change": int(to_number(d["compareToPreviousClosePrice"])),
        "change_pct": round(to_number(d["fluctuationsRatio"]), 2),
        "traded_at": d.get("localTradedAt"),
        "status": d.get("marketStatus"),
        "source": "naver",
    }


def fetch_yahoo(stock):
    suffix = ".KQ" if stock.get("market") == "KOSDAQ" else ".KS"
    d = get_json(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{stock['code']}{suffix}?range=1d&interval=1d"
    )
    meta = d["chart"]["result"][0]["meta"]
    price = meta["regularMarketPrice"]
    prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    change = price - prev if prev else 0
    traded = meta.get("regularMarketTime")
    return {
        "api_name": meta.get("shortName") or meta.get("longName"),
        "price": int(round(price)),
        "change": int(round(change)),
        "change_pct": round(change / prev * 100, 2) if prev else 0.0,
        "traded_at": datetime.datetime.fromtimestamp(traded, KST).isoformat(timespec="seconds") if traded else None,
        "status": None,
        "source": "yahoo",
    }


def main():
    if len(sys.argv) != 3:
        sys.exit("사용법: collect_stocks.py <종목 설정 파일> <data 폴더>")
    stocks = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    out_path = pathlib.Path(sys.argv[2]) / "stocks.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        previous = json.loads(out_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = {}
    previous_items = {item["code"]: item for item in previous.get("items", [])}

    items, ok_count = [], 0
    for stock in stocks:
        quote, errors = None, []
        for fetch in (fetch_naver, fetch_yahoo):
            try:
                quote = fetch(stock)
                break
            except Exception as exc:  # 한 종목·한 출처의 실패가 전체를 멈추지 않게 한다
                errors.append(f"{fetch.__name__}: {type(exc).__name__} {exc}")
        base = {"code": stock["code"], "name": stock["name"], "market": stock.get("market")}
        if quote:
            ok_count += 1
            api_name = quote.pop("api_name")
            items.append({**base, **quote})
            print(f"{stock['name']}({stock['code']}): {quote['price']:,}원 {quote['change']:+,} "
                  f"({quote['change_pct']:+.2f}%) [{quote['source']}, 조회된 종목명: {api_name}]")
        else:
            print(f"{stock['name']}({stock['code']}): 실패 — {' / '.join(errors)}")
            old = previous_items.get(stock["code"])
            if old:  # 직전 값을 남기되 오래된 값임을 표시한다
                items.append({**old, **base, "stale": True})

    if ok_count == 0:
        print("실패: 어떤 종목도 조회하지 못했습니다. 기존 파일은 그대로 둡니다.")
        sys.exit(1)

    if items == previous.get("items"):
        print("변동 없음: 파일을 다시 쓰지 않습니다.")
        return
    result = {"updated": datetime.datetime.now(KST).isoformat(timespec="minutes"), "items": items}
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"기록: {ok_count}/{len(stocks)} 종목")


if __name__ == "__main__":
    main()
