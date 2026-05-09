"""
Phase 5: Price tracking pipeline.

Records weekly price snapshots in SQLite, computes price changes over time,
and exposes helper queries used by the dashboard.

Usage:
    python tracker.py snapshot          # record a snapshot from valencia_scored.parquet
    python tracker.py drops --days 30   # show recent price drops
    python tracker.py stats             # show database stats
"""

import argparse
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
DATA_PARQUET = ROOT / "valencia_scored.parquet"
DB_PATH = ROOT / "history.sqlite"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_at TEXT NOT NULL,
    listing_id INTEGER NOT NULL,
    price_eur REAL,
    price_per_m2 INTEGER,
    surface_m2 REAL,
    bedrooms INTEGER,
    city TEXT,
    region TEXT,
    property_subtype TEXT,
    listing_age_days INTEGER,
    is_bargain INTEGER,
    bargain_pct REAL,
    PRIMARY KEY (snapshot_at, listing_id)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_listing ON snapshots(listing_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_date ON snapshots(snapshot_at);

CREATE TABLE IF NOT EXISTS listings_meta (
    listing_id INTEGER PRIMARY KEY,
    title TEXT,
    url TEXT,
    first_seen TEXT,
    last_seen TEXT,
    initial_price REAL,
    current_price REAL
);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA_SQL)
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def record_snapshot(snapshot_at: str | None = None) -> int:
    """Record a snapshot of the current valencia_scored.parquet to SQLite."""
    if not DATA_PARQUET.exists():
        log.error(f"{DATA_PARQUET} not found - run data_pipeline.py and price_model.py first")
        return 0

    df = pd.read_parquet(DATA_PARQUET)
    snapshot_at = snapshot_at or datetime.now().strftime("%Y-%m-%d")
    log.info(f"Recording snapshot {snapshot_at} ({len(df)} listings)")

    snap = df[[
        "id", "price_eur", "price_per_m2", "surface_m2", "bedrooms",
        "city", "region", "property_subtype", "listing_age_days",
        "is_bargain", "bargain_pct",
    ]].copy()
    snap.insert(0, "snapshot_at", snapshot_at)
    snap = snap.rename(columns={"id": "listing_id"})
    snap["is_bargain"] = snap["is_bargain"].astype(int)

    meta = df[["id", "title", "url", "price_eur"]].copy()
    meta = meta.rename(columns={"id": "listing_id"})

    with get_connection() as conn:
        conn.execute("DELETE FROM snapshots WHERE snapshot_at = ?", (snapshot_at,))
        snap.to_sql("snapshots", conn, if_exists="append", index=False)

        for _, r in meta.iterrows():
            conn.execute("""
                INSERT INTO listings_meta (listing_id, title, url, first_seen, last_seen, initial_price, current_price)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(listing_id) DO UPDATE SET
                    title = excluded.title,
                    url = excluded.url,
                    last_seen = excluded.last_seen,
                    current_price = excluded.current_price
            """, (
                int(r["listing_id"]), r["title"], r["url"],
                snapshot_at, snapshot_at, float(r["price_eur"]), float(r["price_eur"])
            ))

        conn.commit()
        n_rows = conn.execute("SELECT COUNT(*) FROM snapshots WHERE snapshot_at = ?", (snapshot_at,)).fetchone()[0]
        log.info(f"Snapshot saved: {n_rows} rows")
        return int(n_rows)


def get_price_drops(min_days: int = 7, min_drop_pct: float = 1.0) -> pd.DataFrame:
    """Return listings whose price dropped between snapshots.

    Compares the most recent snapshot to the most recent prior snapshot at least
    `min_days` apart.
    """
    with get_connection() as conn:
        snapshots = pd.read_sql(
            "SELECT DISTINCT snapshot_at FROM snapshots ORDER BY snapshot_at DESC",
            conn,
        )
        if len(snapshots) < 2:
            log.warning("Need ≥2 snapshots to compute price drops.")
            return pd.DataFrame()

        latest = snapshots.iloc[0]["snapshot_at"]
        latest_dt = datetime.strptime(latest, "%Y-%m-%d")

        prev = None
        for snap in snapshots["snapshot_at"].tolist()[1:]:
            snap_dt = datetime.strptime(snap, "%Y-%m-%d")
            if (latest_dt - snap_dt).days >= min_days:
                prev = snap
                break

        if prev is None:
            log.warning(f"No prior snapshot found with ≥{min_days} days gap.")
            return pd.DataFrame()

        log.info(f"Comparing {prev} → {latest}")

        query = """
        SELECT
            cur.listing_id,
            m.title,
            m.url,
            cur.city,
            cur.region,
            cur.property_subtype,
            prev.price_eur AS prev_price,
            cur.price_eur AS curr_price,
            (prev.price_eur - cur.price_eur) AS drop_eur,
            ROUND((prev.price_eur - cur.price_eur) / prev.price_eur * 100, 2) AS drop_pct,
            cur.surface_m2,
            cur.bargain_pct,
            cur.listing_age_days
        FROM snapshots cur
        JOIN snapshots prev ON cur.listing_id = prev.listing_id
        LEFT JOIN listings_meta m ON cur.listing_id = m.listing_id
        WHERE cur.snapshot_at = ?
          AND prev.snapshot_at = ?
          AND cur.price_eur < prev.price_eur
          AND ROUND((prev.price_eur - cur.price_eur) / prev.price_eur * 100, 2) >= ?
        ORDER BY drop_pct DESC
        """
        return pd.read_sql(query, conn, params=(latest, prev, min_drop_pct))


def get_listing_history(listing_id: int) -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql(
            "SELECT snapshot_at, price_eur, price_per_m2, bargain_pct "
            "FROM snapshots WHERE listing_id = ? ORDER BY snapshot_at",
            conn,
            params=(listing_id,),
        )


def get_market_trend() -> pd.DataFrame:
    """Aggregate market-level metrics over time."""
    with get_connection() as conn:
        return pd.read_sql(
            """
            SELECT
                snapshot_at,
                COUNT(*) AS n_listings,
                ROUND(AVG(price_eur)) AS mean_price,
                ROUND(AVG(price_per_m2)) AS mean_ppm2,
                SUM(is_bargain) AS n_bargains
            FROM snapshots
            GROUP BY snapshot_at
            ORDER BY snapshot_at
            """,
            conn,
        )


def get_stats() -> dict:
    with get_connection() as conn:
        n_snapshots = conn.execute("SELECT COUNT(DISTINCT snapshot_at) FROM snapshots").fetchone()[0]
        n_listings_tracked = conn.execute("SELECT COUNT(DISTINCT listing_id) FROM snapshots").fetchone()[0]
        n_total_rows = conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
        date_range = conn.execute(
            "SELECT MIN(snapshot_at), MAX(snapshot_at) FROM snapshots"
        ).fetchone()
        size_kb = DB_PATH.stat().st_size / 1024 if DB_PATH.exists() else 0
        return {
            "snapshots": n_snapshots,
            "unique_listings": n_listings_tracked,
            "total_rows": n_total_rows,
            "earliest": date_range[0],
            "latest": date_range[1],
            "db_size_kb": round(size_kb, 1),
        }


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    snap_parser = sub.add_parser("snapshot", help="Record a snapshot")
    snap_parser.add_argument("--date", help="Override snapshot date YYYY-MM-DD (default: today)")

    drop_parser = sub.add_parser("drops", help="Show recent price drops")
    drop_parser.add_argument("--days", type=int, default=7, help="Minimum days between compared snapshots")
    drop_parser.add_argument("--pct", type=float, default=1.0, help="Minimum drop %")

    sub.add_parser("stats", help="Show database stats")
    sub.add_parser("trend", help="Show market trend over time")

    args = parser.parse_args()

    if args.cmd == "snapshot":
        record_snapshot(args.date)
    elif args.cmd == "drops":
        df = get_price_drops(min_days=args.days, min_drop_pct=args.pct)
        if df.empty:
            print("No price drops detected.")
        else:
            print(df.head(30).to_string(index=False))
    elif args.cmd == "stats":
        for k, v in get_stats().items():
            print(f"{k}: {v}")
    elif args.cmd == "trend":
        print(get_market_trend().to_string(index=False))


if __name__ == "__main__":
    main()
