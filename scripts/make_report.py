"""Parse the cached pages, compute the findings, and write charts to docs/images/.

    PYTHONPATH=src python scripts/make_report.py

Writes data/*.csv (local only) and docs/images/*.png (aggregates, safe to publish), and prints the findings.
"""

import json
from pathlib import Path

from railstats import analysis as A
from railstats import charts as C
from railstats.parse import build, save

IMG = Path("docs/images")
IMG.mkdir(parents=True, exist_ok=True)

t = build()
save(t)
r = A.runs(t["daily"], t["trains"])
head = A.headline(r)
cat = A.by_category(r)
rank = A.train_ranking(r)
month = A.by(r, "month")
week = A.weekday_order(A.by(r, "weekday"))
stage = A.delay_along_route(t["daily"])
hot = A.delay_hotspots(t["daily"], t["station_stats"])
corr = rank["distance_km"].corr(rank["avg_delay_min"])


def label(row):
    return f"{row['name'].title()} ({row.name})"


best = rank.head(10)  # highest on-time share
worst = rank.sort_values("avg_delay_min", ascending=False).head(10)  # largest average delay
C.save(C.by_category(cat), IMG / "by_category.png")
C.save(C.hbars([label(x) for _, x in best.iterrows()], best["on_time_pct"].tolist(),
               "Most punctual trains", "on time at destination (%)", "{:.0f}%"), IMG / "most_punctual.png")
C.save(C.hbars([label(x) for _, x in worst.iterrows()], worst["avg_delay_min"].tolist(),
               "Least punctual trains", "average delay at destination (min)", "{:.0f} min"), IMG / "least_punctual.png")
days_per_month = r.groupby("month")["date"].nunique()
C.save(C.monthly(month, days_per_month), IMG / "by_month.png")
C.save(C.along_route(stage), IMG / "along_route.png")
C.save(C.distribution(r), IMG / "delay_distribution.png")
top_hot = hot.head(10)
C.save(C.hbars([f"{s.title()} ({c})" for c, s in top_hot["station"].items()], top_hot["mean"].tolist(),
               "Where trains lose the most time", "average delay gained since the previous stop (min)", "{:.1f}"),
       IMG / "hotspots.png")
via = A.corridor_trains(t["daily"])
corridor = A.corridor_effect(r, via)
spearman = A.rank_corr(rank["distance_km"], rank["avg_delay_min"])
C.save(C.distance_vs_delay(rank, via, f"Longer routes run later (rank correlation {spearman:.2f})",
                           "via Kharagpur-Tatanagar-Rourkela"), IMG / "distance_vs_delay.png")

findings = {
    "headline": {k: (round(v, 1) if isinstance(v, float) else str(v)) for k, v in head.items()},
    "by_category": cat.round(2).to_dict("index"),
    "most_punctual": best[["name", "on_time_pct", "avg_delay_min"]].round(1).reset_index().to_dict("records"),
    "least_punctual": worst[["name", "on_time_pct", "avg_delay_min"]].round(1).reset_index().to_dict("records"),
    "by_month": {str(k): {**v, "days": int(days_per_month[k])}
                 for k, v in month[["avg_delay_min", "on_time_pct"]].round(1).to_dict("index").items()},
    "by_weekday": week[["avg_delay_min", "on_time_pct"]].round(1).to_dict("index"),
    "along_route": stage["mean"].round(1).to_dict(),
    "hotspots": top_hot.round(1).reset_index().to_dict("records"),
    "distance_delay_corr": {"pearson": round(corr, 2), "spearman": round(spearman, 2)},
    "corridor": corridor.round(1).to_dict("index"),
    "corridor_trains": sorted(via),
    "final_leg_recovery": A.final_leg_recovery(t["daily"]).round(1).to_dict(),
    "parse_errors": t["errors"].to_dict("records"),
}
Path("data/findings.json").write_text(json.dumps(findings, indent=1, default=str), encoding="utf-8")
print(json.dumps(findings, indent=1, default=str))
