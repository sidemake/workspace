#!/usr/bin/env python3
"""Claude 구독 사용률 수집기.

`claude -p ... --output-format stream-json --verbose` 의 출력 파일을 읽어
5시간·7일 사용률을 data/usage.json 에 한 줄 추가하고,
주 단위 집계(data/weekly.json)를 다시 만든다.

사용법: collect_usage.py <stream-json 출력 파일> <data 폴더>

공개 저장소의 실행 로그에 남아도 되는 내용(사용률 숫자, 오류 요약)만 출력한다.
"""
import datetime
import json
import pathlib
import sys

KST = datetime.timezone(datetime.timedelta(hours=9))
MAX_RECORDS = 5000  # 하루 4회 기준 3년 이상


def to_pct(value):
    """stream-json 은 0~1 비율로 준다. 혹시 0~100 으로 오면 그대로 둔다."""
    pct = value if value > 1.5 else value * 100
    return round(pct, 1)


def to_iso(epoch):
    """리셋 시각(초 또는 밀리초)을 한국 시간 문자열로 바꾼다."""
    if not isinstance(epoch, (int, float)) or epoch <= 0:
        return None
    if epoch > 1e12:  # 밀리초
        epoch = epoch / 1000
    return datetime.datetime.fromtimestamp(epoch, KST).isoformat(timespec="minutes")


def read_windows(path):
    """출력에서 창(five_hour, seven_day 등)별 사용률을 모은다."""
    windows, result_text = {}, None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            if event.get("type") == "rate_limit_event":
                info = event.get("rate_limit_info") or {}
                for name, win in (info.get("unifiedWindows") or {}).items():
                    if isinstance(win, dict) and isinstance(win.get("utilization"), (int, float)):
                        windows[name] = {
                            "pct": to_pct(win["utilization"]),
                            "resets_at": to_iso(win.get("resetsAt")),
                        }
                # 구버전 형식: 창 하나의 사용률만 최상위에 실려 오는 경우
                name, util = info.get("rateLimitType"), info.get("utilization")
                if name and name not in windows and isinstance(util, (int, float)):
                    windows[name] = {"pct": to_pct(util), "resets_at": to_iso(info.get("resetsAt"))}
            elif event.get("type") == "result":
                result_text = str(event.get("result"))[:200]
    return windows, result_text


def rebuild_weekly(records):
    """같은 주간 창(리셋 시각이 같은 기록)끼리 묶어 그 주의 최고 사용률을 남긴다."""
    weeks = []
    for rec in records:
        key = rec.get("seven_day_resets_at")
        pct = rec.get("seven_day_pct")
        if key is None or pct is None:
            continue
        reset = datetime.datetime.fromisoformat(key)
        # 리셋 시각이 몇 분 어긋나게 보고돼도 같은 주로 본다(1시간 이내).
        week = next(
            (w for w in weeks if abs((w["_reset"] - reset).total_seconds()) <= 3600), None
        )
        if week is None:
            week = {"week_resets_at": key, "used_pct": 0, "samples": 0, "last_recorded": None, "_reset": reset}
            weeks.append(week)
        week["used_pct"] = max(week["used_pct"], pct)
        week["samples"] += 1
        week["last_recorded"] = rec["t"]
    weeks.sort(key=lambda w: w["_reset"])
    return [{k: v for k, v in w.items() if k != "_reset"} for w in weeks]


def main():
    if len(sys.argv) != 3:
        sys.exit("사용법: collect_usage.py <출력 파일> <data 폴더>")
    src, data_dir = sys.argv[1], pathlib.Path(sys.argv[2])
    data_dir.mkdir(parents=True, exist_ok=True)
    usage_path, weekly_path = data_dir / "usage.json", data_dir / "weekly.json"

    windows, result_text = read_windows(src)
    if "five_hour" not in windows and "seven_day" not in windows:
        print("실패: 출력에 사용률 항목이 없습니다.")
        print(f"실행 결과 요약: {result_text}")
        sys.exit(1)

    record = {"t": datetime.datetime.now(KST).isoformat(timespec="minutes")}
    for name in ("five_hour", "seven_day"):
        win = windows.pop(name, None)
        record[f"{name}_pct"] = win["pct"] if win else None
        record[f"{name}_resets_at"] = win["resets_at"] if win else None
    if windows:  # 그 밖의 창이 실려 오면 버리지 않고 함께 남긴다
        record["other"] = windows

    try:
        records = json.loads(usage_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        records = []
    records = (records + [record])[-MAX_RECORDS:]

    usage_path.write_text(json.dumps(records, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    weekly_path.write_text(
        json.dumps(rebuild_weekly(records), ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"기록: 5시간 {record['five_hour_pct']}% / 주간 {record['seven_day_pct']}% (총 {len(records)}건)")


if __name__ == "__main__":
    main()
