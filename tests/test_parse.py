"""Parser tests on a small hand-made page with the same structure as the source (no copied content)."""

import math

from railstats.parse import parse_page

PAGE = """
<div>EXAMPLE EXPRESS (12345) ALPHA JN to BETA CENTRAL EXAMPLE EXPRESS (12345) Running Days: Mon Wed Fri
Pantry Available Type: Superfast Zone: NR</div><div>Distance: 1,234 Kms.</div>
<a class="runStatStn"><div>ALPHA JN (ALJN) <div><b>Avg. Delay:</b> 3 Min's</div></div></a>
<a class="runStatStn"><div>BETA CENTRAL (BTC) <div><b>Avg. Delay:</b> 42.5 Min's</div></div></a>
<script>
et.rsStat.primaryData = [ ['Stations','Right Time', 'Slight Delay', 'Significant Delay', 'Cancelled/Unknown', {'type': 'string'}],['ALJN', 3, 0, 0, 0, 3],['BTC', 1, 1, 1, 0, 42.5]];
et.rsStat.tooltipData = [['Date',{'type':'number','label':'ALJN'},{'type':'number','label':'BTC'}]
,[new Date(2026,0,31),2,95]
,[new Date(2026,1,02),-1,20]
,[new Date(2026,1,04),null,null]
];
</script>
"""


def test_train_metadata():
    train, _, _ = parse_page(PAGE)
    assert train == {"number": 12345, "name": "EXAMPLE EXPRESS", "origin": "ALPHA JN", "destination": "BETA CENTRAL",
                     "type": "Superfast", "zone": "NR", "running_days": "Mon Wed Fri", "distance_km": 1234}


def test_station_stats_keep_order_and_names():
    _, stats, _ = parse_page(PAGE)
    assert [s["station_code"] for s in stats] == ["ALJN", "BTC"]
    assert stats[1]["station_name"] == "BETA CENTRAL" and stats[1]["avg_delay_min"] == 42.5
    assert (stats[1]["right_time"], stats[1]["slight"], stats[1]["significant"]) == (1, 1, 1)


def test_daily_delays_fix_js_months_and_keep_missing_as_none():
    _, _, daily = parse_page(PAGE)
    assert len(daily) == 6
    first = daily[0]
    assert str(first["date"]) == "2026-01-31" and first["station_code"] == "ALJN" and first["delay_min"] == 2
    assert str(daily[2]["date"]) == "2026-02-02" and daily[2]["delay_min"] == -1  # early departure
    assert daily[4]["delay_min"] is None and daily[5]["delay_min"] is None  # cancelled / unknown run


def test_missing_header_raises():
    try:
        parse_page("<html>nothing here</html>")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
