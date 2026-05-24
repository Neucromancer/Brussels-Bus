from __future__ import annotations

import pandas as pd

from logic.models import Stop, NextStopInfo
from const import BUS_SPEED, TRANSFER_PENALTY
from logic.helpers import haversine


# I. Lấy thời gian chờ trung bình của tuyến (route_id) từ database
def get_waiting_time(route_id):
    return TRANSFER_PENALTY


def normalize_route_paths_dataframe(route_path_dataframe: pd.DataFrame) -> pd.DataFrame:
    """
    Chuẩn hóa DataFrame route_paths để dùng được với cả:
    - route_paths đã build sẵn trong stib_database.db
    - dữ liệu raw lấy từ GTFS/merge thủ công
    """
    df = route_path_dataframe.copy()

    rename_map = {}
    if "route_short_name" in df.columns and "route_name" not in df.columns:
        rename_map["route_short_name"] = "route_name"
    if "direction_id" in df.columns and "direction" not in df.columns:
        rename_map["direction_id"] = "direction"
    if "stop_sequence" in df.columns and "stop_order" not in df.columns:
        rename_map["stop_sequence"] = "stop_order"
    if rename_map:
        df = df.rename(columns=rename_map)

    required_cols = ["route_name", "direction", "stop_order", "stop_id", "stop_name", "stop_lat", "stop_lon"]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise KeyError(f"Thiếu cột bắt buộc trong route_paths: {missing}")

    df["route_name"] = df["route_name"].astype(str)
    df["direction"] = pd.to_numeric(df["direction"], errors="coerce")
    df["stop_order"] = pd.to_numeric(df["stop_order"], errors="coerce")
    df["stop_id"] = df["stop_id"].astype(str)
    df["stop_name"] = df["stop_name"].astype(str)
    df["stop_lat"] = pd.to_numeric(df["stop_lat"], errors="coerce")
    df["stop_lon"] = pd.to_numeric(df["stop_lon"], errors="coerce")

    df = df.dropna(subset=["route_name", "direction", "stop_order", "stop_id", "stop_lat", "stop_lon"])
    df["direction"] = df["direction"].astype(int)
    df["stop_order"] = df["stop_order"].astype(int)

    # Giữ thứ tự ổn định để xây graph đúng tuyến -> hướng -> thứ tự bến.
    df = df.sort_values(["route_name", "direction", "stop_order", "stop_id"]).reset_index(drop=True)
    return df


# II. Nạp dữ liệu từ DataFrame Khởi tạo Stop
def load_data(route_path_dataframe):
    df = normalize_route_paths_dataframe(route_path_dataframe)
    all_stops = {}  # {id: Stop object}

    # 1. --- Khởi tạo tất cả Stop còn thiếu trường next_stops ---
    for _, row in df.iterrows():
        sid = str(row["stop_id"])
        if sid not in all_stops:
            all_stops[sid] = Stop(
                sid,
                row["stop_name"],
                float(row["stop_lat"]),
                float(row["stop_lon"]),
            )

    # 2. --- Tạo kết nối NextStopInfo ---
    for _, group in df.groupby(["route_name", "direction"], sort=False):
        group = group.sort_values("stop_order")
        rows = list(group.itertuples(index=False))
        for curr_row, next_row in zip(rows, rows[1:]):
            curr_stop = all_stops[str(curr_row.stop_id)]
            next_stop = all_stops[str(next_row.stop_id)]

            travel_time = (
                haversine(curr_stop.lat, curr_stop.lon, next_stop.lat, next_stop.lon) / BUS_SPEED
            ) * 60

            connection = NextStopInfo(next_stop, travel_time, str(curr_row.route_name))
            curr_stop.next_stops.append(connection)

    return sorted(all_stops.values(), key=lambda s: (str(s.name), str(s.id)))
