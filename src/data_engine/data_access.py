from __future__ import annotations

import os
import sqlite3
from typing import Dict, Tuple

import pandas as pd

from data_engine.data_process import load_data


def load_stops_table(db_path: str) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query(
            "SELECT stop_id, stop_name, stop_lat, stop_lon FROM stops",
            conn,
        )
    finally:
        conn.close()

    df["stop_id"] = df["stop_id"].astype(str)
    df["stop_lat"] = pd.to_numeric(df["stop_lat"], errors="coerce")
    df["stop_lon"] = pd.to_numeric(df["stop_lon"], errors="coerce")
    df = df.dropna(subset=["stop_lat", "stop_lon"])
    return df.drop_duplicates(subset=["stop_id"]).sort_values(["stop_name", "stop_id"])


def load_route_paths_table(db_path: str) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query("SELECT * FROM route_paths", conn)
    finally:
        conn.close()

    if df.empty:
        return df

    df["stop_id"] = df["stop_id"].astype(str)
    df["route_name"] = df["route_name"].astype(str)
    df["direction"] = pd.to_numeric(df["direction"], errors="coerce")
    df["stop_order"] = pd.to_numeric(df["stop_order"], errors="coerce")
    df["stop_lat"] = pd.to_numeric(df["stop_lat"], errors="coerce")
    df["stop_lon"] = pd.to_numeric(df["stop_lon"], errors="coerce")
    df = df.dropna(subset=["stop_order", "stop_lat", "stop_lon"])
    df["direction"] = df["direction"].astype(int)
    df["stop_order"] = df["stop_order"].astype(int)
    return df


def load_network_data(db_path: str):
    route_paths = load_route_paths_table(db_path)
    stops_df = load_stops_table(db_path)

    all_stops = load_data(route_paths) if not route_paths.empty else []
    coordinates = {str(stop.id): (float(stop.lat), float(stop.lon)) for stop in all_stops}
    stop_lookup = {
        row.stop_id: {
            "stop_name": row.stop_name,
            "stop_lat": float(row.stop_lat),
            "stop_lon": float(row.stop_lon),
        }
        for row in stops_df.itertuples(index=False)
    }

    return route_paths, stops_df, all_stops, coordinates, stop_lookup
