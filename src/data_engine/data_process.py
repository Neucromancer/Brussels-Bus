from __future__ import annotations

import os
import sqlite3
import pandas as pd
import streamlit as st

from pathlib import Path
from typing import Dict, Tuple, List
from logic.models import Stop, NextStopInfo
from const import METRO_LINES, METRO_SPEED, BUS_SPEED, TRANSFER_PENALTY_METRO, TRANSFER_PENALTY_BUS
from logic.helpers import haversine


# I. Lấy thời gian chờ và tốc độ trung bình của tuyến (route_id) từ database
def get_route_speed(route_name: str) -> float:
    """Trả về vận tốc thương mại (km/h) bằng cách tra cứu thủ công"""
    route_name = str(route_name).upper().strip() 
    
    if route_name in METRO_LINES:
        return METRO_SPEED
    else:
        return BUS_SPEED  # Các tuyến còn lại mặc định là Bus
    
def get_waiting_time(route_name: str) -> float:
    """Trả về thời gian chờ (phút) bằng cách tra cứu thủ công"""
    route_name = str(route_name).upper().strip()
    
    if route_name in METRO_LINES:
        return TRANSFER_PENALTY_METRO
    else:
        return TRANSFER_PENALTY_BUS


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

            speed_kmh = get_route_speed(str(curr_row.route_name))
            travel_time = (
                haversine(curr_stop.lat, curr_stop.lon, next_stop.lat, next_stop.lon) / speed_kmh
            ) * 60

            connection = NextStopInfo(next_stop, travel_time, str(curr_row.route_name))
            curr_stop.next_stops.append(connection)

    return sorted(all_stops.values(), key=lambda s: (str(s.name), str(s.id)))

# III. HÀM XỬ LÝ HÌNH HỌC ĐƯỜNG CONG

def get_curved_segment(route_id, lat_A, lon_A, lat_B, lon_B, db_path=None):
    """
    Truy vấn Database để lấy mảng tọa độ uốn lượn thực tế.
    Phiên bản Ultimate: Tự động phát hiện đúng chiều đi (Outbound/Inbound).
    """
    if db_path is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        db_path = os.path.join(base_dir, "data", "stib_database.db")
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. Lấy TẤT CẢ các shape_id của tuyến xe này (bao gồm cả lượt đi và về)
        # Ép kiểu CAST sang TEXT để tránh lỗi khác biệt dữ liệu int/string
        cursor.execute("""
            SELECT DISTINCT t.shape_id 
            FROM trips t
            JOIN routes r ON t.route_id = r.route_id
            WHERE CAST(r.route_short_name AS TEXT) = ? 
        """, (str(route_id),))
        
        shape_ids = [row[0] for row in cursor.fetchall() if row[0]]
        
        if not shape_ids:
            conn.close()
            print(f"Cảnh báo: Không tìm thấy dây hình học cho tuyến {route_id}.")
            return [(lat_A, lon_A), (lat_B, lon_B)]

        def find_nearest_idx_and_dist(target_lat, target_lon, pts):
            min_dist = float('inf')
            best_idx = 0
            for i, (p_lat, p_lon) in enumerate(pts):
                dist = (target_lat - p_lat)**2 + (target_lon - p_lon)**2
                if dist < min_dist:
                    min_dist = dist
                    best_idx = i
            return best_idx, min_dist

        best_segment = [(lat_A, lon_A), (lat_B, lon_B)]
        min_total_dist = float('inf')

        # 2. Duyệt qua từng sợi dây để tìm ra sợi khớp nhất với bến A và B
        for sid in shape_ids:
            cursor.execute("""
                SELECT shape_pt_lat, shape_pt_lon 
                FROM shapes 
                WHERE shape_id = ? 
                ORDER BY shape_pt_sequence
            """, (sid,))
            shape_pts = cursor.fetchall()

            if not shape_pts: continue

            idx_A, dist_A = find_nearest_idx_and_dist(lat_A, lon_A, shape_pts)
            idx_B, dist_B = find_nearest_idx_and_dist(lat_B, lon_B, shape_pts)
            
            total_dist = dist_A + dist_B

            # 3. Chọn sợi dây có tổng khoảng cách tới 2 bến là nhỏ nhất (Đúng chiều nhất)
            if total_dist < min_total_dist:
                min_total_dist = total_dist
                
                # Chốt chặn an toàn: Ngưỡng 0.0003 (~600m). 
                if idx_A != idx_B and dist_A < 0.0003 and dist_B < 0.0003:
                    if idx_A < idx_B:
                        segment = shape_pts[idx_A : idx_B + 1]
                    else:
                        segment = shape_pts[idx_B : idx_A + 1][::-1]
                        
                    best_segment = [(lat_A, lon_A)] + segment + [(lat_B, lon_B)]

        conn.close()
        return best_segment
        
    except Exception as e:
        print(f"Lỗi truy xuất đường cong DB (Tuyến {route_id}): {e}")
        return [(lat_A, lon_A), (lat_B, lon_B)]
    

def resolve_db_path():
    from pathlib import Path
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    candidates = [
        BASE_DIR / "data" / "stib_database.db",
        BASE_DIR / "src" / "data_engine" / "stib_database.db",
        BASE_DIR / "src" / "data" / "stib_database.db",
    ]
    for path in candidates:
        if path.exists(): return path
    return candidates[0]

@st.cache_resource(show_spinner=False)
def load_stops_table(db_path: str, disabled_routes: tuple) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT stop_id, stop_name, stop_lat, stop_lon FROM stops", conn)
    conn.close()
    df["stop_id"] = df["stop_id"].astype(str)
    df["stop_lat"] = pd.to_numeric(df["stop_lat"], errors="coerce")
    df["stop_lon"] = pd.to_numeric(df["stop_lon"], errors="coerce")
    return df.dropna(subset=["stop_lat", "stop_lon"]).drop_duplicates(subset=["stop_id"]).sort_values(["stop_name", "stop_id"])

@st.cache_resource(show_spinner=False)
def load_route_objects(db_path: str, disabled_routes: tuple):
    conn = sqlite3.connect(db_path)
    route_paths = pd.read_sql_query("SELECT * FROM route_paths", conn)
    conn.close()
    if disabled_routes:
        route_paths = route_paths[~route_paths['route_name'].astype(str).isin(disabled_routes)]
    route_paths = normalize_route_paths_dataframe(route_paths)
    all_stops = load_data(route_paths) 
    coordinates = {str(stop.id): (float(stop.lat), float(stop.lon)) for stop in all_stops}
    return route_paths, all_stops, coordinates

@st.cache_resource(show_spinner=False)
def make_stop_lookup(db_path: str, disabled_routes: tuple):
    df = load_stops_table(db_path, disabled_routes)
    return {row.stop_id: {"stop_name": row.stop_name, "stop_lat": float(row.stop_lat), "stop_lon": float(row.stop_lon)} for row in df.itertuples(index=False)}

def build_route_segments(path_nodes):
    if not path_nodes or len(path_nodes) < 2:
        return pd.DataFrame(columns=["Tuyến", "Từ", "Đến", "Số bến", "Thời gian (phút)"])
    segments = []
    seg_start_idx = 1  
    route_of = lambda node: str(getattr(node, "route_id", None) or "---")
    current_route = route_of(path_nodes[1])
    for idx in range(2, len(path_nodes)):
        nxt_route = route_of(path_nodes[idx])
        if nxt_route != current_route:
            segments.append({"Tuyến": current_route, "Từ": getattr(path_nodes[seg_start_idx - 1].stop, "name", "---"), "Đến": getattr(path_nodes[idx - 1].stop, "name", "---"), "Số bến": idx - seg_start_idx, "Thời gian (phút)": round(float(path_nodes[idx - 1].g - path_nodes[seg_start_idx - 1].g), 2)})
            seg_start_idx = idx; current_route = nxt_route
    segments.append({"Tuyến": current_route, "Từ": getattr(path_nodes[seg_start_idx - 1].stop, "name", "---"), "Đến": getattr(path_nodes[-1].stop, "name", "---"), "Số bến": len(path_nodes) - seg_start_idx, "Thời gian (phút)": round(float(path_nodes[-1].g - path_nodes[seg_start_idx - 1].g), 2)})
    return pd.DataFrame(segments)

def build_selected_route_rows(route_paths_df, selected_route_name):
    if not selected_route_name:
        return pd.DataFrame(columns=["route_name", "direction", "stop_order", "stop_id", "stop_name", "stop_lat", "stop_lon"])
    mask = route_paths_df["route_name"].astype(str) == str(selected_route_name)
    df = route_paths_df.loc[mask].copy()
    if df.empty: return pd.DataFrame(columns=["route_name", "direction", "stop_order", "stop_id", "stop_name", "stop_lat", "stop_lon"])
    return df.sort_values(["direction", "stop_order", "stop_id"]).reset_index(drop=True)