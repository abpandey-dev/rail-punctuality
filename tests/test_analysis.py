import pandas as pd

from railstats import analysis as A


def make():
    trains = pd.DataFrame([
        {"number": 1, "name": "FAST", "origin": "A", "destination": "C", "type": "Rajdhani", "distance_km": 1000},
        {"number": 2, "name": "SLOW", "origin": "A", "destination": "C", "type": "SF", "distance_km": 500},
    ])
    rows = []
    for day, (d1, d2) in enumerate([(5, 90), (10, 20), (None, 70)], start=1):
        date = pd.Timestamp(2026, 7, day)
        rows += [{"number": 1, "date": date, "station_code": "A", "order": 0, "delay_min": 0},
                 {"number": 1, "date": date, "station_code": "C", "order": 1, "delay_min": d1},
                 {"number": 2, "date": date, "station_code": "A", "order": 0, "delay_min": 10},
                 {"number": 2, "date": date, "station_code": "C", "order": 1, "delay_min": d2}]
    return pd.DataFrame(rows), trains


def test_categories():
    assert A.train_category("Rajdhani") == "Rajdhani"
    assert A.train_category("SF") == "Superfast"
    assert A.train_category("Vande Bharat") == "Vande Bharat"
    assert A.train_category("T18") == "Vande Bharat"  # the source's label
    assert A.train_category("Super Fast") == "Superfast"
    assert A.train_category("Mail") == "Mail/Express"
    assert A.train_category("Garib Rath") == "Other"


def test_runs_use_destination_delay_and_never_count_missing_as_zero():
    daily, trains = make()
    r = A.runs(daily, trains)
    fast = r[r["number"] == 1]
    assert fast["recorded"].tolist() == [True, True, False]
    s = A.by(r, "number").loc[1]
    assert s["avg_delay_min"] == 7.5 and s["on_time_pct"] == 100 and round(s["no_record_pct"], 1) == 33.3
    slow = A.by(r, "number").loc[2]
    assert slow["on_time_pct"] == 0 and round(slow["over_1h_pct"], 1) == 66.7


def test_delay_added_and_hotspots():
    daily, trains = make()
    r = A.runs(daily, trains)
    assert r.loc[r["number"] == 2, "delay_added"].tolist() == [80, 10, 60]
    stations = pd.DataFrame([{"station_code": "C", "station_name": "CEE"}, {"station_code": "A", "station_name": "AY"}])
    hot = A.delay_hotspots(daily, stations, min_obs=1)
    assert hot.index[0] == "C" and hot.iloc[0]["station"] == "CEE"


def test_final_leg_recovery():
    daily, _ = make()
    rec = A.final_leg_recovery(daily)
    # train 2 starts 10 min late and ends later on every recorded day, so nothing is recovered
    assert rec["runs"] == 5 and rec["recovered_share_pct"] == 0


def test_rank_corr_and_corridor():
    a, b = pd.Series([1, 2, 3, 4]), pd.Series([10, 100, 1000, 10000])
    assert A.rank_corr(a, b) == 1.0  # monotonic, so 1 even though not linear
    daily, trains = make()
    r = A.runs(daily, trains)
    eff = A.corridor_effect(r, {2})
    assert eff.loc["all other trains", "trains"] == 1
    assert round(eff.iloc[0]["share_of_over_1h_runs_pct"]) == 100  # only train 2 has 1h+ runs
