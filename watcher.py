#!/usr/bin/env python3
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import requests

API = "https://mcp.aka.page/api/cgv/timetable"
DATES = ["20260814", "20260815", "20260816", "20260817", "20260822", "20260823"]
THEATER_KEYWORD = "용산아이파크몰"
MOVIE_KEYWORDS = ["오디세이", "ODYSSEY"]
FORMAT_KEYWORDS = ["IMAX"]
STATE_FILE = Path("state.json")
RESULT_FILE = Path("result.json")
TIMEOUT = 25

def norm(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()

def as_int(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, str):
        m = re.search(r"-?\d+", v.replace(",", ""))
        if m:
            try:
                return int(m.group())
            except ValueError:
                pass
    return None

def walk_dicts(obj):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from walk_dicts(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from walk_dicts(item)

def first(d, *keys):
    low = {str(k).lower(): v for k, v in d.items()}
    for key in keys:
        if key.lower() in low:
            return low[key.lower()]
    return None

def candidate_showtimes(payload, date):
    seen = set()
    items = []
    for d in walk_dicts(payload):
        blob = " ".join(norm(v) for v in d.values() if isinstance(v, (str, int, float)))
        blob_u = blob.upper()

        if not any(k.upper() in blob_u for k in MOVIE_KEYWORDS):
            continue
        if not any(k.upper() in blob_u for k in FORMAT_KEYWORDS):
            continue
        if "용산" not in blob:
            continue

        movie = first(d, "movieName", "movieNm", "movieTitle", "title", "movie_name")
        theater = first(d, "theaterName", "theaterNm", "siteName", "cinemaName", "theater_name")
        screen = first(d, "screenName", "screenNm", "screenType", "hallName", "screen_name", "playType")
        start = first(d, "startTime", "playStartTime", "startTm", "start_time", "playTime")
        end = first(d, "endTime", "playEndTime", "endTm", "end_time")
        remaining = first(
            d, "remainingSeats", "remainSeats", "remainSeat", "availableSeats",
            "seatRemain", "remainCount", "remainCnt", "restSeatCnt", "leftSeatCount"
        )
        total = first(d, "totalSeats", "totalSeat", "seatCount", "totalCnt", "totalSeatCount")

        remaining_i = as_int(remaining)
        total_i = as_int(total)

        # Some CGV responses put seat text in a generic label/value.
        if remaining_i is None:
            m = re.search(r"(?:잔여|남은|remaining|remain)[^\d]{0,10}(\d+)", blob, re.I)
            if m:
                remaining_i = int(m.group(1))

        # Need at least a recognizable time to avoid matching parent metadata objects.
        start_s = norm(start)
        if not re.search(r"\d{1,2}:\d{2}|\d{4}", start_s):
            m = re.search(r"\b([01]?\d|2[0-3]):[0-5]\d\b", blob)
            if m:
                start_s = m.group(0)

        if not start_s:
            continue

        key = (date, start_s, norm(screen), norm(movie), remaining_i)
        if key in seen:
            continue
        seen.add(key)

        items.append({
            "date": date,
            "movie": norm(movie) or "오디세이",
            "theater": norm(theater) or THEATER_KEYWORD,
            "screen": norm(screen) or "IMAX",
            "start": start_s,
            "end": norm(end),
            "remaining": remaining_i,
            "total": total_i,
            "raw_hint": blob[:240],
        })
    return items

def fetch(date):
    params = {"playDate": date, "keyword": THEATER_KEYWORD}
    last_error = None
    for attempt in range(3):
        try:
            r = requests.get(API, params=params, timeout=TIMEOUT, headers={
                "User-Agent": "Mozilla/5.0 cgv-odyssey-seat-watcher/1.0",
                "Accept": "application/json",
            })
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_error = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{date} 조회 실패: {last_error}")

def load_state():
    if not STATE_FILE.exists():
        return {"shows": {}}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"shows": {}}

def show_key(s):
    return f'{s["date"]}|{s["start"]}|{s["screen"]}|{s["movie"]}'

def main():
    raw = {}
    for date in DATES:
        try:
            raw[date] = fetch(date)
        except Exception as e:
            raw[date] = {"ERROR": str(e)}

    Path("raw_response.json").write_text(
        json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    state = load_state()
    old = state.get("shows", {})
    current = {}
    alerts = []
    all_shows = []
    errors = []

    for date in DATES:
        try:
            payload = fetch(date)
            shows = candidate_showtimes(payload, date)
            all_shows.extend(shows)
            for s in shows:
                key = show_key(s)
                current[key] = s
                rem = s.get("remaining")
                old_rem = (old.get(key) or {}).get("remaining")

                # Alert when we can positively identify available seats and:
                # 1) first observation is available, or 2) sold out/zero becomes positive,
                # 3) positive seat count increases.
                if isinstance(rem, int) and rem > 0:
                    if old_rem is None or old_rem <= 0 or (isinstance(old_rem, int) and rem > old_rem):
                        alerts.append({
                            **s,
                            "previous_remaining": old_rem,
                            "reason": "예매 가능한 좌석 감지",
                        })
        except Exception as e:
            errors.append(str(e))

    # Keep prior entries if a transient API response omitted a show.
    merged = dict(old)
    merged.update(current)
    state = {"shows": merged}
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    result = {
        "alerts": alerts,
        "shows": all_shows,
        "errors": errors,
        "dates": DATES,
        "theater": THEATER_KEYWORD,
        "movie": "오디세이",
        "format": "IMAX",
    }
    RESULT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))

    # GitHub Actions output
    if os.getenv("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"alert_count={len(alerts)}\n")
            f.write(f"error_count={len(errors)}\n")

    return 0 if not errors else 0  # Don't kill the workflow for transient API failures.

if __name__ == "__main__":
    raise SystemExit(main())
