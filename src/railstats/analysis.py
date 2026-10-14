"""Punctuality metrics.

A *run* is one train on one date. Its delay is the delay at the last station in the source's history
(arrival at the destination); "on time" means within 15 minutes, the source's own "Right Time" band.
Runs with no destination record (cancelled, diverted or unknown) are counted separately, never as 0.
"""

from __future__ import annotations

import pandas as pd

ON_TIME_MIN = 15
LATE_HOUR_MIN = 60
TYPE_ORDER = ["Vande Bharat", "Shatabdi", "Rajdhani", "Duronto", "Superfast", "Mail/Express", "Other"]


def train_category(source_type: str) -> str:
    t = (source_type or "").lower()
    # The source labels Vande Bharat trains "T18" (the project's original name, Train 18).
    for key, label in [("vande", "Vande Bharat"), ("t18", "Vande Bharat"), ("shatabdi", "Shatabdi"), ("rajdhani", "Rajdhani"),
                       ("duronto", "Duronto"), ("super fast", "Superfast"), ("superfast", "Superfast"), ("sf", "Superfast"),
                       ("mail", "Mail/Express"), ("express", "Mail/Express"), ("exp", "Mail/Express")]:
        if key in t:
            return label
    return "Other"


def runs(daily: pd.DataFrame, trains: pd.DataFrame) -> pd.DataFrame:
    """One row per train run: origin delay, destination delay, delay added on the way."""
    d = daily.sort_values(["number", "date", "order"])
    last_order = d.groupby("number")["order"].transform("max")
    origin = d[d["order"] == 0].set_index(["number", "date"])["delay_min"].rename("origin_delay")
    dest = d[d["order"] == last_order].set_index(["number", "date"])["delay_min"].rename("dest_delay")
    r = pd.concat([origin, dest], axis=1).reset_index()
    r["recorded"] = r["dest_delay"].notna()
    r["on_time"] = r["dest_delay"] <= ON_TIME_MIN
    r["late_hour"] = r["dest_delay"] > LATE_HOUR_MIN
    r["delay_added"] = r["dest_delay"] - r["origin_delay"]
    meta = trains[["number", "name", "origin", "destination", "type", "distance_km"]].copy()
    meta["category"] = meta["type"].map(train_category)
    r = r.merge(meta, on="number", how="left")
    r["month"] = r["date"].dt.to_period("M")
    r["weekday"] = r["date"].dt.day_name()
    return r


def _summary(g: pd.DataFrame) -> pd.Series:
    rec = g[g["recorded"]]
    return pd.Series({
        "runs": len(g),
        "recorded_runs": len(rec),
        "avg_delay_min": rec["dest_delay"].mean(),
        "median_delay_min": rec["dest_delay"].median(),
        "p90_delay_min": rec["dest_delay"].quantile(0.9),
        "on_time_pct": 100 * rec["on_time"].mean(),
        "over_1h_pct": 100 * rec["late_hour"].mean(),
        "no_record_pct": 100 * (1 - len(rec) / len(g)) if len(g) else float("nan"),
    })


def headline(r: pd.DataFrame) -> pd.Series:
    s = _summary(r)
    s["trains"] = r["number"].nunique()
    s["first_date"], s["last_date"] = r["date"].min().date(), r["date"].max().date()
    return s


def by(r: pd.DataFrame, col: str) -> pd.DataFrame:
    return r.groupby(col, observed=True).apply(_summary, include_groups=False)


def by_category(r: pd.DataFrame) -> pd.DataFrame:
    out = by(r, "category")
    return out.reindex([c for c in TYPE_ORDER if c in out.index])


def train_ranking(r: pd.DataFrame, min_runs: int = 20) -> pd.DataFrame:
    t = r.groupby("number").apply(_summary, include_groups=False)
    meta = r.drop_duplicates("number").set_index("number")[["name", "origin", "destination", "category",
                                                           "distance_km"]]
    t = meta.join(t)
    return t[t["recorded_runs"] >= min_runs].sort_values(["on_time_pct", "avg_delay_min"],
                                                          ascending=[False, True])


def delay_along_route(daily: pd.DataFrame, bins: int = 5) -> pd.DataFrame:
    """Average delay by how far along its route the train is (station position as a share of the trip)."""
    d = daily.dropna(subset=["delay_min"]).copy()
    span = d.groupby("number")["order"].transform("max").replace(0, 1)
    d["progress"] = d["order"] / span
    d["stage"] = pd.cut(d["progress"], bins=[-0.01, 0.2, 0.4, 0.6, 0.8, 1.0][: bins + 1],
                        labels=["start", "20-40%", "40-60%", "60-80%", "end"][:bins])
    # Average within each run first, so trains with many recorded stops don't outweigh the rest.
    per_run = d.groupby(["number", "date", "stage"], observed=True)["delay_min"].mean().reset_index()
    return per_run.groupby("stage", observed=True)["delay_min"].agg(["mean", "median", "count"])


def delay_hotspots(daily: pd.DataFrame, stations: pd.DataFrame, min_obs: int = 200) -> pd.DataFrame:
    """Where trains lose time: average delay gained on arrival at a station versus the previous recorded stop."""
    d = daily.sort_values(["number", "date", "order"]).copy()
    d["gained"] = d.groupby(["number", "date"])["delay_min"].diff()
    names = stations.drop_duplicates("station_code").set_index("station_code")["station_name"]
    g = d.dropna(subset=["gained"]).groupby("station_code")["gained"].agg(["mean", "count"])
    g = g[g["count"] >= min_obs].sort_values("mean", ascending=False)
    g.insert(0, "station", g.index.map(names))
    return g


def weekday_order(df: pd.DataFrame) -> pd.DataFrame:
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return df.reindex([x for x in days if x in df.index])


def final_leg_recovery(daily: pd.DataFrame) -> pd.Series:
    """Delay at the second-last recorded stop vs at the destination. Timetables often pad the final leg."""
    d = daily.dropna(subset=["delay_min"])
    last_order = d.groupby("number")["order"].transform("max")
    last = d[d["order"] == last_order].set_index(["number", "date"])["delay_min"]
    prev = d[d["order"] == last_order - 1].set_index(["number", "date"])["delay_min"]
    j = pd.concat([prev.rename("prev"), last.rename("last")], axis=1).dropna()
    rec = j["prev"] - j["last"]
    return pd.Series({"runs": len(j), "delay_before_final_leg": j["prev"].mean(), "delay_at_destination": j["last"].mean(),
                      "recovered_share_pct": 100 * (rec > 0).mean(), "avg_recovered_min": rec.mean()})


# Junctions east and south of Howrah where the worst-hit trains in this sample all lose time.
CORRIDOR_STATIONS = ("KGP", "TATA", "CKP", "ROU")


def corridor_trains(daily: pd.DataFrame, stations=CORRIDOR_STATIONS) -> set[int]:
    return set(daily.loc[daily["station_code"].isin(stations), "number"])


def corridor_effect(r: pd.DataFrame, trains_in: set[int]) -> pd.DataFrame:
    rec = r[r["recorded"]]
    inside = rec["number"].isin(trains_in)
    late = r[r["late_hour"].fillna(False)]
    out = pd.DataFrame({
        "trains": [len(trains_in), rec.loc[~inside, "number"].nunique()],
        "avg_delay_min": [rec.loc[inside, "dest_delay"].mean(), rec.loc[~inside, "dest_delay"].mean()],
        "on_time_pct": [100 * rec.loc[inside, "on_time"].mean(), 100 * rec.loc[~inside, "on_time"].mean()],
        "share_of_over_1h_runs_pct": [100 * late["number"].isin(trains_in).mean(),
                                      100 * (~late["number"].isin(trains_in)).mean()],
    }, index=["via Kharagpur-Tatanagar-Rourkela", "all other trains"])
    return out


def rank_corr(a: pd.Series, b: pd.Series) -> float:
    """Spearman correlation without scipy: Pearson on ranks."""
    return a.rank().corr(b.rank())
