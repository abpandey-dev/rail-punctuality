"""Turn cached running-history pages into three tidy tables.

  trains        one row per train: name, route, type, zone, running days, distance
  daily         one row per train x date x station: delay in minutes (negative = early, NaN = no record)
  station_stats one row per train x station: run counts per delay band and average delay, as the source reports them

Delay bands are the source's own: Right Time 0-15 min, Slight 15-60 min, Significant > 60 min.
"""

from __future__ import annotations

import html as htmllib
import re
from datetime import date
from pathlib import Path

import pandas as pd


def _text(html: str) -> str:
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
    return " ".join(htmllib.unescape(re.sub(r"<[^>]+>", " ", t)).split())


def parse_page(html: str) -> tuple[dict, list[dict], list[dict]]:
    text = _text(html)
    # "<NAME> (<NO>) <ORIGIN> to <DESTINATION> <NAME> (<NO>) Running Days: ..." in the train info box; the
    # back-references stop it matching the page's other "<NAME> (<NO>)" headings.
    head = re.search(r"([A-Z0-9][A-Z0-9 .&'/-]{1,60}?) \((\d{5})\) ([A-Z][A-Z0-9 .'&()-]{1,50}?) to "
                     r"([A-Z][A-Z0-9 .'&()-]{1,50}?) \1 \(\2\) Running Days: (.+?) (?:Pantry|Available Classes|Type:)", text)
    if not head:
        raise ValueError("train header not found")
    name, number, origin, destination, days = head.groups()
    ttype = re.search(r"Type: (.+?) Zone:", text)
    zone = re.search(r"Zone: (\S+)", text)
    dist = re.search(r"Distance: ([\d,]+) Kms", text)
    train = {
        "number": int(number), "name": name.strip(), "origin": origin.strip(), "destination": destination.strip(),
        "type": ttype.group(1).strip() if ttype else "Unknown", "zone": zone.group(1) if zone else None,
        "running_days": days.strip(), "distance_km": int(dist.group(1).replace(",", "")) if dist else None,
    }

    names = dict((code, nm.strip()) for nm, code in re.findall(r"([A-Z][A-Z0-9 .&'()/-]+?) \(([A-Z0-9]{2,5})\) Avg\. Delay", text))
    prim = re.search(r"primaryData = \[(.*?)\];", html, re.S)
    stats = []
    for order, m in enumerate(re.finditer(r"\['([A-Z0-9]+)',\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(-?[\d.]+)\]",
                                          prim.group(1) if prim else "")):
        code, rt, sl, sig, can, avg = m.groups()
        stats.append({"number": int(number), "station_code": code, "station_name": names.get(code, code),
                      "order": order, "right_time": int(rt), "slight": int(sl), "significant": int(sig),
                      "cancelled_unknown": int(can), "avg_delay_min": float(avg)})

    tip = re.search(r"tooltipData = \[\['Date',(.*?)\]\s*,(.*?)\];", html, re.S)
    daily = []
    if tip:
        codes = re.findall(r"'label':'([A-Z0-9]+)'", tip.group(1))
        for y, m, d, vals in re.findall(r"\[new Date\((\d+),(\d+),(\d+)\),([^\]]*)\]", tip.group(2)):
            day = date(int(y), int(m) + 1, int(d))  # JavaScript months are 0-based
            for order, (code, v) in enumerate(zip(codes, vals.split(","))):
                v = v.strip()
                daily.append({"number": int(number), "date": day, "station_code": code, "order": order,
                              "delay_min": None if v in ("null", "") else float(v)})
    return train, stats, daily


def build(raw_dir: str | Path = "data/raw", period: str = "6m") -> dict[str, pd.DataFrame]:
    trains, stats, daily, errors = [], [], [], []
    for f in sorted(Path(raw_dir).glob(f"*_{period}.html")):
        try:
            t, s, d = parse_page(f.read_text(encoding="utf-8"))
        except ValueError as e:
            errors.append((f.name, str(e)))
            continue
        trains.append(t)
        stats += s
        daily += d
    tables = {"trains": pd.DataFrame(trains), "station_stats": pd.DataFrame(stats), "daily": pd.DataFrame(daily)}
    if not tables["daily"].empty:
        tables["daily"]["date"] = pd.to_datetime(tables["daily"]["date"])
    tables["errors"] = pd.DataFrame(errors, columns=["file", "error"])
    return tables


def save(tables: dict[str, pd.DataFrame], out: str | Path = "data") -> None:
    for name, df in tables.items():
        df.to_csv(Path(out) / f"{name}.csv", index=False)
