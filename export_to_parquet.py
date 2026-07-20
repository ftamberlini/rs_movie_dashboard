"""
Export Oracle tables to Parquet files in ./data/.

Usage:
    uv run python export_to_parquet.py [--out ./data]

Requires: pyarrow (add to pyproject.toml if missing)
    uv add pyarrow
"""
import os
import sys
import time
import argparse
from pathlib import Path

import oracledb
import pyarrow as pa
import pyarrow.parquet as pq
from dotenv import load_dotenv

load_dotenv()

# ── Oracle connection ─────────────────────────────────────────────────────────

WALLET_DIR = os.path.abspath(os.getenv("ORACLE_WALLET_DIR", "./oracle"))


def _conn():
    return oracledb.connect(
        user=os.getenv("ORACLE_USER"),
        password=os.getenv("ORACLE_PASSWORD"),
        dsn=os.getenv("ORACLE_DSN"),
        config_dir=WALLET_DIR,
        wallet_location=WALLET_DIR,
        wallet_password=os.getenv("ORACLE_WALLET_PASSWORD"),
    )


# ── Tables to export ──────────────────────────────────────────────────────────
# Each entry: (table_name, estimated_rows_for_display)
# Tables are exported as-is — no transformations, raw Oracle data.

TABLES = [
    ("country",          300),
    ("ml_imdb",          10_000),
    ("director",         50_000),
    ("writer",           50_000),
    ("movie_imdb",       90_000),
    ("movie_country",    200_000),
    ("movie_ml_genre",   100_000),
    ("movie_imdb_genre", 100_000),
    ("movie_director",   100_000),
    ("movie_writer",     100_000),
    ("movie_rating",     500_000),
    ("subtitle_geo",     200_000),
    ("subtitle_theme",   700_000),
]

CHUNK_SIZE = 50_000  # rows per batch when writing Parquet


# ── Helpers ───────────────────────────────────────────────────────────────────

def oracle_type_to_arrow(ora_type, precision, scale):
    """Map oracledb type to PyArrow type."""
    name = getattr(ora_type, "__name__", str(ora_type))
    if ora_type is oracledb.DB_TYPE_NUMBER:
        if scale == 0 and precision and precision <= 18:
            return pa.int64()
        return pa.float64()
    if ora_type in (oracledb.DB_TYPE_VARCHAR, oracledb.DB_TYPE_CHAR,
                    oracledb.DB_TYPE_NVARCHAR, oracledb.DB_TYPE_NCHAR,
                    oracledb.DB_TYPE_CLOB, oracledb.DB_TYPE_LONG):
        return pa.string()
    if ora_type is oracledb.DB_TYPE_DATE:
        return pa.date32()
    if ora_type in (oracledb.DB_TYPE_TIMESTAMP,
                    oracledb.DB_TYPE_TIMESTAMP_TZ,
                    oracledb.DB_TYPE_TIMESTAMP_LTZ):
        return pa.timestamp("us")
    if ora_type is oracledb.DB_TYPE_BINARY_FLOAT:
        return pa.float32()
    if ora_type is oracledb.DB_TYPE_BINARY_DOUBLE:
        return pa.float64()
    if ora_type in (oracledb.DB_TYPE_BLOB, oracledb.DB_TYPE_RAW,
                    oracledb.DB_TYPE_LONG_RAW):
        return pa.binary()
    return pa.string()  # fallback: stringify


def build_schema(cursor) -> pa.Schema:
    fields = []
    for col in cursor.description:
        name, ora_type, _, _, precision, scale, _ = col
        fields.append(pa.field(name, oracle_type_to_arrow(ora_type, precision, scale)))
    return pa.schema(fields)


def rows_to_columns(rows, n_cols):
    """Transpose list-of-tuples → list-of-lists (one per column)."""
    cols = [[] for _ in range(n_cols)]
    for row in rows:
        for i, v in enumerate(row):
            cols[i].append(v)
    return cols


def export_table(conn, table: str, out_path: Path) -> int:
    t0 = time.time()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {table}")

    schema = build_schema(cur)
    n_cols = len(schema)
    writer = None
    total = 0

    while True:
        rows = cur.fetchmany(CHUNK_SIZE)
        if not rows:
            break

        cols = rows_to_columns(rows, n_cols)
        arrays = []
        for i, field in enumerate(schema):
            try:
                arrays.append(pa.array(cols[i], type=field.type))
            except (pa.ArrowInvalid, pa.ArrowTypeError):
                # Fallback: stringify the column
                arrays.append(pa.array([str(v) if v is not None else None for v in cols[i]],
                                       type=pa.string()))

        batch = pa.record_batch(arrays, schema=schema)

        if writer is None:
            writer = pq.ParquetWriter(out_path, schema,
                                      compression="snappy",
                                      write_statistics=True)
        writer.write_batch(batch)
        total += len(rows)
        print(f"  {total:>8,} rows…", end="\r", flush=True)

    if writer:
        writer.close()
    cur.close()

    elapsed = time.time() - t0
    size_mb = out_path.stat().st_size / 1_048_576 if out_path.exists() else 0
    print(f"  {total:>8,} rows  →  {size_mb:.1f} MB  ({elapsed:.1f}s)")
    return total


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Export Oracle tables to Parquet")
    parser.add_argument("--out", default="./data", help="Output directory (default: ./data)")
    parser.add_argument("--tables", nargs="*", help="Export only these tables (default: all)")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    tables = TABLES
    if args.tables:
        names = {t.lower() for t in args.tables}
        tables = [(t, n) for t, n in TABLES if t.lower() in names]
        if not tables:
            print(f"No matching tables found. Available: {[t for t,_ in TABLES]}")
            sys.exit(1)

    print(f"Connecting to Oracle ({os.getenv('ORACLE_DSN')})…")
    conn = _conn()
    print("Connected.\n")

    grand_total = 0
    t_start = time.time()

    for table, _ in tables:
        out_path = out_dir / f"{table}.parquet"
        print(f"▶  {table}")
        try:
            n = export_table(conn, table, out_path)
            grand_total += n
        except Exception as e:
            print(f"  ERROR: {e}")

    conn.close()

    elapsed = time.time() - t_start
    total_mb = sum((out_dir / f"{t}.parquet").stat().st_size
                   for t, _ in tables
                   if (out_dir / f"{t}.parquet").exists()) / 1_048_576

    print(f"\n✓  {grand_total:,} rows total  |  {total_mb:.1f} MB  |  {elapsed:.0f}s")
    print(f"   Files in: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
