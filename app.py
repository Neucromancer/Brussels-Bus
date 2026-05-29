import os
import sys
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

# -----------------------------------------------------------------------------
# Make the project importable when running: streamlit run app.py
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"
for path in (BASE_DIR, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

# Project modules under src/
from UI.auth import login_form
from data_engine.data_process import load_data, normalize_route_paths_dataframe, get_curved_segment
from logic.router import a_star_search


DEFAULT_START_LAT = 50.8466
DEFAULT_START_LON = 4.3528
DEFAULT_GOAL_LAT = 50.8456
DEFAULT_GOAL_LON = 4.3572
DEFAULT_MAP_CENTER = (50.8503, 4.3517)


@dataclass(frozen=True)
class Coords:
    lat: float
    lon: float


# -----------------------------------------------------------------------------
# Session helpers
# -----------------------------------------------------------------------------
def init_state() -> None:
    defaults = {
        "pin_mode": "start",  # "start" or "goal"
        "map_start_coords": None,  # {"lat": ..., "lon": ...}
        "map_goal_coords": None,
        "map_start_nearest": None,
        "map_goal_nearest": None,
        "manual_start_id": None,
        "manual_goal_id": None,
        "route_result": None,
        "route_results": [],
        "selected_route_name": None,
        "last_processed_click": None,
        "active_input_mode": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_route_result() -> None:
    st.session_state.route_result = None
    st.session_state.route_results = []


def set_start_coords(lat: float, lon: float, nearest_stop: Optional[str] = None) -> None:
    st.session_state.map_start_coords = {"lat": float(lat), "lon": float(lon)}
    st.session_state.map_start_nearest = nearest_stop
    clear_route_result()


def set_goal_coords(lat: float, lon: float, nearest_stop: Optional[str] = None) -> None:
    st.session_state.map_goal_coords = {"lat": float(lat), "lon": float(lon)}
    st.session_state.map_goal_nearest = nearest_stop
    clear_route_result()


def reset_all() -> None:
    for key in [
        "pin_mode",
        "map_start_coords",
        "map_goal_coords",
        "map_start_nearest",
        "map_goal_nearest",
        "manual_start_id",
        "manual_goal_id",
        "route_result",
        "route_results",
        "selected_route_name",
        "last_processed_click",
    ]:
        st.session_state.pop(key, None)
    st.rerun()


# -----------------------------------------------------------------------------
# Data loading helpers
# -----------------------------------------------------------------------------
def resolve_db_path() -> Path:
    candidates = [
        BASE_DIR / "data" / "stib_database.db",
        BASE_DIR / "src" / "data_engine" / "stib_database.db",
        BASE_DIR / "src" / "data" / "stib_database.db",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


@st.cache_resource(show_spinner=False)
def load_stops_table(db_path: str, disabled_routes: Tuple[str, ...]) -> pd.DataFrame:
    """Load stop metadata for labels / dropdowns."""
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query(
            "SELECT stop_id, stop_name, stop_lat, stop_lon FROM stops",
            conn,
        )
    finally:
        conn.close()

    df["stop_id"] = df["stop_id"].astype(str)
    df["stop_name"] = df["stop_name"].astype(str)
    df["stop_lat"] = pd.to_numeric(df["stop_lat"], errors="coerce")
    df["stop_lon"] = pd.to_numeric(df["stop_lon"], errors="coerce")
    df = df.dropna(subset=["stop_lat", "stop_lon"])
    return df.drop_duplicates(subset=["stop_id"]).sort_values(["stop_name", "stop_id"])


@st.cache_resource(show_spinner=False)
def load_route_objects(db_path: str, disabled_routes: Tuple[str, ...]):
    """Load route_paths dataframe and convert it to the stop graph used by A*."""
    conn = sqlite3.connect(db_path)
    try:
        route_paths = pd.read_sql_query("SELECT * FROM route_paths", conn)
    finally:
        conn.close()

    if disabled_routes:
        route_paths = route_paths[~route_paths['route_name'].astype(str).isin(disabled_routes)]

    route_paths = normalize_route_paths_dataframe(route_paths)
    all_stops = load_data(route_paths) # Graph được build sạch sẽ 100% không dính tuyến lỗi
    coordinates = {str(stop.id): (float(stop.lat), float(stop.lon)) for stop in all_stops}
    return route_paths, all_stops, coordinates


@st.cache_resource(show_spinner=False)
def make_stop_lookup(db_path: str, disabled_routes: Tuple[str, ...]) -> Dict[str, Dict[str, object]]:
    # Truyền disabled_routes vào load_stops_table
    df = load_stops_table(db_path, disabled_routes)
    return {
        row.stop_id: {
            "stop_name": row.stop_name,
            "stop_lat": float(row.stop_lat),
            "stop_lon": float(row.stop_lon),
        }
        for row in df.itertuples(index=False)
    }

# -----------------------------------------------------------------------------
# Routing helpers
# -----------------------------------------------------------------------------
def nearest_stop_id(lat: float, lon: float, coordinates: Dict[str, Tuple[float, float]]) -> Optional[str]:
    if not coordinates:
        return None
    return min(
        coordinates.keys(),
        key=lambda sid: (lat - coordinates[sid][0]) ** 2 + (lon - coordinates[sid][1]) ** 2,
    )


def collect_route_rows(path_nodes: List[object], stop_lookup: Dict[str, Dict[str, object]]) -> List[Dict[str, object]]:
    rows = []
    for idx, node in enumerate(path_nodes, start=1):
        stop = getattr(node, "stop", None)
        if stop is None:
            continue

        stop_id = str(getattr(stop, "id", ""))
        info = stop_lookup.get(stop_id, {})
        stop_name = info.get("stop_name") or getattr(stop, "name", None) or f"Stop {stop_id}"

        lat = getattr(stop, "lat", None)
        lon = getattr(stop, "lon", None)
        if lat is None:
            lat = info.get("stop_lat")
        if lon is None:
            lon = info.get("stop_lon")

        rows.append(
            {
                "Step": idx,
                "Stop ID": stop_id,
                "Stop name": stop_name,
                "Lat": float(lat) if lat is not None else None,
                "Lon": float(lon) if lon is not None else None,
                "Route": getattr(node, "route_id", None) or "---",
                "Time (min)": round(float(getattr(node, "g", 0.0)), 2),
            }
        )
    return rows


def build_route_segments(path_nodes: List[object]) -> pd.DataFrame:
    """Group consecutive nodes by route_id to make the line plan easier to read."""
    if not path_nodes or len(path_nodes) < 2:
        return pd.DataFrame(columns=["Tuyến", "Từ", "Đến", "Số bến", "Thời gian (phút)"])

    segments = []
    seg_start_idx = 1  # path_nodes[0] is the walking-in/start anchor

    def route_of(node) -> str:
        return str(getattr(node, "route_id", None) or "---")

    current_route = route_of(path_nodes[1])

    for idx in range(2, len(path_nodes)):
        nxt_route = route_of(path_nodes[idx])
        if nxt_route != current_route:
            start_node = path_nodes[seg_start_idx]
            end_node = path_nodes[idx - 1]
            segments.append(
                {
                    "Tuyến": current_route,
                    "Từ": getattr(path_nodes[seg_start_idx - 1].stop, "name", "---"),
                    "Đến": getattr(end_node.stop, "name", "---"),
                    "Số bến": idx - seg_start_idx,
                    "Thời gian (phút)": round(float(end_node.g - path_nodes[seg_start_idx - 1].g), 2),
                }
            )
            seg_start_idx = idx
            current_route = nxt_route

    end_node = path_nodes[-1]
    segments.append(
        {
            "Tuyến": current_route,
            "Từ": getattr(path_nodes[seg_start_idx - 1].stop, "name", "---"),
            "Đến": getattr(end_node.stop, "name", "---"),
            "Số bến": len(path_nodes) - seg_start_idx,
            "Thời gian (phút)": round(float(end_node.g - path_nodes[seg_start_idx - 1].g), 2),
        }
    )


    return pd.DataFrame(segments)


def format_route_rank_text(rank: int) -> str:
    return {1: "Tuyến chính", 2: "Phương án 2", 3: "Phương án 3"}.get(rank, f"Phương án {rank}")


def set_route_results(results: List[Dict[str, object]]) -> None:
    st.session_state.route_results = results[:3]
    st.session_state.route_result = results[0] if results else None


def build_selected_route_rows(
    route_paths_df: pd.DataFrame,
    selected_route_name: Optional[str],
) -> pd.DataFrame:
    if not selected_route_name:
        return pd.DataFrame(columns=["route_name", "direction", "stop_order", "stop_id", "stop_name", "stop_lat", "stop_lon"])

    mask = route_paths_df["route_name"].astype(str) == str(selected_route_name)
    df = route_paths_df.loc[mask].copy()
    if df.empty:
        return pd.DataFrame(columns=["route_name", "direction", "stop_order", "stop_id", "stop_name", "stop_lat", "stop_lon"])
    return df.sort_values(["direction", "stop_order", "stop_id"]).reset_index(drop=True)


def draw_solution_path(
    m: folium.Map,
    path_nodes: List[object],
    stop_lookup: Dict[str, Dict[str, object]],
    *,
    line_color: str,
    line_weight: int,
    line_opacity: float,
    dashed_walk_color: str = "gray",
    show_markers: bool = False,
    label: str = "",
) -> None:
    path_rows = collect_route_rows(path_nodes, stop_lookup)
    route_points = []

    for i in range(len(path_rows) - 1):
        row_A = path_rows[i]
        row_B = path_rows[i + 1]
        lat_A, lon_A = row_A.get("Lat"), row_A.get("Lon")
        lat_B, lon_B = row_B.get("Lat"), row_B.get("Lon")
        if None in (lat_A, lon_A, lat_B, lon_B):
            continue

        route_id = row_B.get("Route", "---")
        if route_id == "---":
            segment_path = [(lat_A, lon_A), (lat_B, lon_B)]
            folium.PolyLine(
                segment_path,
                color=dashed_walk_color,
                weight=max(3, line_weight - 2),
                dash_array="5, 10",
                opacity=min(0.85, line_opacity + 0.1),
                tooltip="Đi bộ / chuyển tuyến" + (f" · {label}" if label else ""),
            ).add_to(m)
        else:
            segment_path = get_curved_segment(
                route_id=route_id,
                lat_A=lat_A,
                lon_A=lon_A,
                lat_B=lat_B,
                lon_B=lon_B,
            )
            folium.PolyLine(
                segment_path,
                color=line_color,
                weight=line_weight,
                opacity=line_opacity,
                tooltip=(f"{label} · Tuyến {route_id}" if label else f"Tuyến {route_id}"),
            ).add_to(m)
        route_points.extend(segment_path)

    if show_markers:
        for idx, row in enumerate(path_rows):
            lat = row.get("Lat")
            lon = row.get("Lon")
            if lat is None or lon is None:
                continue
            stop_name = row.get("Stop name", "---")
            stop_id = row.get("Stop ID", "---")
            route_id = row.get("Route", "---")
            is_first = idx == 0
            is_last = idx == len(path_rows) - 1
            color = "blue"
            icon = "circle"
            prefix = "fa"
            if is_first:
                color = "green"
                icon = "play"
            elif is_last:
                color = "red"
                icon = "flag"

            popup_html = f"""
            <b>{'Điểm đầu của lộ trình' if is_first else ('Điểm cuối của lộ trình' if is_last else 'Bến trung gian')}</b><br>
            {stop_name}<br>
            ID: {stop_id}<br>
            Tuyến: {route_id}<br>
            ({lat:.6f}, {lon:.6f})
            """
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=320),
                tooltip=f"{stop_name} · {route_id}",
                icon=folium.Icon(color=color, icon=icon, prefix=prefix),
            ).add_to(m)

    return route_points


def draw_route_stops(
    m: folium.Map,
    route_rows: pd.DataFrame,
    stop_lookup: Dict[str, Dict[str, object]],
) -> List[Tuple[float, float]]:
    points: List[Tuple[float, float]] = []
    if route_rows.empty:
        return points

    for _, row in route_rows.iterrows():
        lat = row.get("stop_lat")
        lon = row.get("stop_lon")
        if pd.isna(lat) or pd.isna(lon):
            continue
        lat = float(lat)
        lon = float(lon)
        stop_id = str(row.get("stop_id", ""))
        stop_name = str(row.get("stop_name", ""))
        route_name = str(row.get("route_name", ""))
        direction = row.get("direction", "")
        stop_order = row.get("stop_order", "")

        points.append((lat, lon))
        popup_html = f"""
        <b>Tuyến {route_name}</b><br>
        Hướng: {direction}<br>
        Thứ tự: {stop_order}<br>
        {stop_name}<br>
        ID: {stop_id}<br>
        ({lat:.6f}, {lon:.6f})
        """
        folium.CircleMarker(
            location=[lat, lon],
            radius=5,
            color="#ff7f0e",
            fill=True,
            fill_opacity=0.9,
            popup=folium.Popup(popup_html, max_width=320),
            tooltip=f"Tuyến {route_name} · {stop_name}",
        ).add_to(m)

    # Connect consecutive stops within each direction
    for (_, _direction), group in route_rows.groupby(["route_name", "direction"], sort=False):
        group = group.sort_values(["stop_order", "stop_id"])
        rows = list(group.itertuples(index=False))
        for curr_row, next_row in zip(rows, rows[1:]):
            lat_A, lon_A = float(curr_row.stop_lat), float(curr_row.stop_lon)
            lat_B, lon_B = float(next_row.stop_lat), float(next_row.stop_lon)
            segment_path = get_curved_segment(
                route_id=str(curr_row.route_name),
                lat_A=lat_A,
                lon_A=lon_A,
                lat_B=lat_B,
                lon_B=lon_B,
            )
            folium.PolyLine(
                segment_path,
                color="#ff7f0e",
                weight=3,
                opacity=0.75,
                tooltip=f"Tuyến {curr_row.route_name}",
            ).add_to(m)
            points.extend(segment_path)

    return points


def get_current_coords(
    input_mode: str,
    stop_lookup: Dict[str, Dict[str, object]],
) -> Tuple[Optional[Coords], Optional[Coords], Optional[str], Optional[str]]:
    """
    Return (start_coords, goal_coords, start_label, goal_label) based on current UI mode.
    """
    if input_mode == "Ghim trên bản đồ":
        start = st.session_state.map_start_coords
        goal = st.session_state.map_goal_coords

        start_coords = Coords(start["lat"], start["lon"]) if start else None
        goal_coords = Coords(goal["lat"], goal["lon"]) if goal else None

        start_label = None
        goal_label = None
        if start_coords:
            nearest = st.session_state.map_start_nearest or ""
            start_label = f"{start_coords.lat:.6f}, {start_coords.lon:.6f}"
            if nearest and nearest in stop_lookup:
                start_label += f"  •  gần bến {stop_lookup[nearest]['stop_name']}"
        if goal_coords:
            nearest = st.session_state.map_goal_nearest or ""
            goal_label = f"{goal_coords.lat:.6f}, {goal_coords.lon:.6f}"
            if nearest and nearest in stop_lookup:
                goal_label += f"  •  gần bến {stop_lookup[nearest]['stop_name']}"

        return start_coords, goal_coords, start_label, goal_label

    # Manual stop selection
    start_id = st.session_state.manual_start_id
    goal_id = st.session_state.manual_goal_id

    start_info = stop_lookup.get(start_id) if start_id else None
    goal_info = stop_lookup.get(goal_id) if goal_id else None

    start_coords = (
        Coords(float(start_info["stop_lat"]), float(start_info["stop_lon"])) if start_info else None
    )
    goal_coords = (
        Coords(float(goal_info["stop_lat"]), float(goal_info["stop_lon"])) if goal_info else None
    )

    start_label = f"{start_info['stop_name']} (ID: {start_id})" if start_info else None
    goal_label = f"{goal_info['stop_name']} (ID: {goal_id})" if goal_info else None
    return start_coords, goal_coords, start_label, goal_label



def build_route_map(
    all_stops: List[object],
    stop_lookup: Dict[str, Dict[str, object]],
    path_nodes: Optional[List[object]] = None,
    start_coords: Optional[Coords] = None,
    goal_coords: Optional[Coords] = None,
    start_nearest_stop: Optional[str] = None,
    goal_nearest_stop: Optional[str] = None,
    route_solutions: Optional[List[Dict[str, object]]] = None,
    selected_route_rows: Optional[pd.DataFrame] = None,
) -> folium.Map:
    coords = [
        (float(stop.lat), float(stop.lon))
        for stop in all_stops
        if getattr(stop, "lat", None) is not None and getattr(stop, "lon", None) is not None
    ]
    if coords:
        center_lat = sum(lat for lat, _ in coords) / len(coords)
        center_lon = sum(lon for _, lon in coords) / len(coords)
    else:
        center_lat, center_lon = DEFAULT_MAP_CENTER

    if start_coords:
        center_lat, center_lon = start_coords.lat, start_coords.lon
    elif goal_coords:
        center_lat, center_lon = goal_coords.lat, goal_coords.lon

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=13,
        control_scale=True,
        tiles="OpenStreetMap",
        width="100%",
        height=650,
    )

    bound_points: List[Tuple[float, float]] = []

    # Show chosen route from the route selector
    if selected_route_rows is not None and not selected_route_rows.empty:
        bound_points.extend(draw_route_stops(m, selected_route_rows, stop_lookup))

    # Show up to 3 best route solutions. Draw lower-ranked routes first so the
    # primary route stays visually on top.
    if route_solutions:
        palette = [
            (3, "#2ca02c", 6, 0.68, False),  # tertiary
            (2, "#ff7f0e", 6, 0.78, False),  # secondary
            (1, "#1f77b4", 9, 1.00, True),   # primary
        ]
        route_map = {idx + 1: result for idx, result in enumerate(route_solutions[:3])}
        for rank, color, weight, opacity, show_markers in palette:
            result = route_map.get(rank)
            if not result:
                continue
            path_nodes = result.get("path") or []
            if not path_nodes:
                continue
            route_label = format_route_rank_text(rank)
            path_points = draw_solution_path(
                m,
                path_nodes,
                stop_lookup,
                line_color=color,
                line_weight=weight,
                line_opacity=opacity,
                show_markers=show_markers,
                label=route_label,
            )
            bound_points.extend(path_points)

    # Original pinned points
    if start_coords is not None:
        popup = f"""
        <b>Điểm đi đã ghim</b><br>
        ({start_coords.lat:.6f}, {start_coords.lon:.6f})<br>
        {"Gần bến: " + stop_lookup[start_nearest_stop]["stop_name"] if start_nearest_stop in stop_lookup else ""}
        """
        folium.Marker(
            location=[start_coords.lat, start_coords.lon],
            popup=folium.Popup(popup, max_width=320),
            tooltip="Điểm đi",
            icon=folium.Icon(color="green", icon="star", prefix="fa"),
        ).add_to(m)

    if goal_coords is not None:
        popup = f"""
        <b>Điểm đến đã ghim</b><br>
        ({goal_coords.lat:.6f}, {goal_coords.lon:.6f})<br>
        {"Gần bến: " + stop_lookup[goal_nearest_stop]["stop_name"] if goal_nearest_stop in stop_lookup else ""}
        """
        folium.Marker(
            location=[goal_coords.lat, goal_coords.lon],
            popup=folium.Popup(popup, max_width=320),
            tooltip="Điểm đến",
            icon=folium.Icon(color="red", icon="flag", prefix="fa"),
        ).add_to(m)

    if path_nodes and start_coords is not None:
        first_stop = path_nodes[0].stop
        if first_stop is not None:
            bound_points.append((start_coords.lat, start_coords.lon))
            bound_points.append((first_stop.lat, first_stop.lon))
            folium.PolyLine(
                [(start_coords.lat, start_coords.lon), (first_stop.lat, first_stop.lon)],
                color="#2ca02c",
                weight=3,
                dash_array="6, 6",
                opacity=0.75,
                tooltip="Đoạn đi bộ vào bến",
            ).add_to(m)

    if path_nodes and goal_coords is not None:
        last_stop = path_nodes[-1].stop
        if last_stop is not None:
            bound_points.append((last_stop.lat, last_stop.lon))
            bound_points.append((goal_coords.lat, goal_coords.lon))
            folium.PolyLine(
                [(last_stop.lat, last_stop.lon), (goal_coords.lat, goal_coords.lon)],
                color="#d62728",
                weight=3,
                dash_array="6, 6",
                opacity=0.75,
                tooltip="Đoạn đi bộ ra điểm đến",
            ).add_to(m)

    if bound_points:
        m.fit_bounds(bound_points, padding=(30, 30))

    return m


def render_map(m: folium.Map) -> Dict[str, object]:
    return st_folium(m, width="100%", height=650, key="interactive_map")


# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Tìm đường đi tàu điện / bus",
    page_icon="🚌",
    layout="wide",
)

init_state()

st.title("🚌 Ứng dụng tìm đường đi tàu điện / bus")

db_path = resolve_db_path()

# Khai báo biến global ra ngoài để phía dưới cuối file Admin đọc được
route_paths_raw = None

with st.spinner("Đang nạp dữ liệu tuyến..."):
    try:
        # Khởi tạo trạng thái danh sách chặn nếu chưa có
        if "disabled_routes" not in st.session_state:
            st.session_state.disabled_routes = set()

        # Lấy danh sách tuyến bị Admin cấu hình chặn và chuyển sang tuple để dùng cho Cache
        disabled_routes_set = st.session_state.get("disabled_routes", set())
        disabled_routes_tuple = tuple(sorted(list(disabled_routes_set)))
        
        # Để lấy toàn bộ danh sách tuyến hiển thị ở menu Admin, ta nạp bản raw không chặn
        route_paths_raw, _, _ = load_route_objects(str(db_path), disabled_routes=())

        # 1. Đọc dữ liệu đã ĐƯỢC LỌC SẠCH từ trong hàm nhờ cơ chế kích hoạt Cache mới
        route_paths, all_stops, coordinates = load_route_objects(str(db_path), disabled_routes=disabled_routes_tuple)
        stop_lookup = make_stop_lookup(str(db_path), disabled_routes=disabled_routes_tuple)
        stops_df_filtered = load_stops_table(str(db_path), disabled_routes=disabled_routes_tuple)
        
        # 2. Lọc bến hiển thị trên Ô Selectbox tương ứng với mạng lưới đang chạy
        active_stop_ids = {str(stop.id) for stop in all_stops}
        stops_df = stops_df_filtered[stops_df_filtered['stop_id'].astype(str).isin(active_stop_ids)]

    except Exception as exc:
        st.error(f"Không thể nạp dữ liệu từ database: {exc}")
        st.stop()

# Main map first
st.subheader("Bản đồ")
route_options = ["— Không chọn —"] + sorted([str(r) for r in route_paths["route_name"].dropna().astype(str).unique()])
default_route_idx = 0
if st.session_state.get("selected_route_name") in route_options:
    default_route_idx = route_options.index(st.session_state.selected_route_name)
selected_route_name = st.selectbox(
    "Chọn tuyến để xem toàn bộ bến",
    route_options,
    index=default_route_idx,
    key="selected_route_selector",
)
selected_route_name = None if selected_route_name == "— Không chọn —" else selected_route_name
if st.session_state.get("selected_route_name") != selected_route_name:
    st.session_state.selected_route_name = selected_route_name

selected_route_rows = build_selected_route_rows(route_paths, selected_route_name)

input_mode = st.radio(
    "Cách chọn điểm",
    ["Ghim trên bản đồ", "Chọn bến có sẵn"],
    horizontal=True,
    key="input_mode_radio",
)

if st.session_state.active_input_mode is not None and st.session_state.active_input_mode != input_mode:
    clear_route_result()
st.session_state.active_input_mode = input_mode

start_coords, goal_coords, start_label, goal_label = get_current_coords(input_mode, stop_lookup)

nearest_start_stop = None
nearest_goal_stop = None
if input_mode == "Ghim trên bản đồ":
    if start_coords is not None:
        nearest_start_stop = nearest_stop_id(start_coords.lat, start_coords.lon, coordinates)
    if goal_coords is not None:
        nearest_goal_stop = nearest_stop_id(goal_coords.lat, goal_coords.lon, coordinates)

map_obj = build_route_map(
    all_stops=all_stops,
    stop_lookup=stop_lookup,
    path_nodes=st.session_state.route_result["path"] if st.session_state.route_result else None,
    start_coords=start_coords,
    goal_coords=goal_coords,
    start_nearest_stop=nearest_start_stop,
    goal_nearest_stop=nearest_goal_stop,
    route_solutions=st.session_state.get("route_results") or [],
    selected_route_rows=selected_route_rows,
)
map_state = render_map(map_obj)

# Capture map click for pin mode
clicked = (map_state or {}).get("last_clicked")
if input_mode == "Ghim trên bản đồ" and clicked:
    click_key = (round(float(clicked["lat"]), 6), round(float(clicked["lng"]), 6))
    if st.session_state.last_processed_click != click_key:
        st.session_state.last_processed_click = click_key
        target = st.session_state.pin_mode
        nearest = nearest_stop_id(float(clicked["lat"]), float(clicked["lng"]), coordinates)
        if target == "start":
            set_start_coords(float(clicked["lat"]), float(clicked["lng"]), nearest)
        else:
            set_goal_coords(float(clicked["lat"]), float(clicked["lng"]), nearest)
        st.rerun()


# Controls below the map
st.subheader("Điều khiển")

if input_mode == "Ghim trên bản đồ":
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Đặt điểm đi", use_container_width=True):
            st.session_state.pin_mode = "start"
    with c2:
        if st.button("Đặt điểm đến", use_container_width=True):
            st.session_state.pin_mode = "goal"
    with c3:
        if st.button("Clear", use_container_width=True):
            reset_all()

    pin_label = "Điểm đi" if st.session_state.pin_mode == "start" else "Điểm đến"
    st.info(f"Chế độ click hiện tại: **{pin_label}**")
else:
    left, right = st.columns(2)
    options = [f"{row.stop_name}  ·  {row.stop_id}" for row in stops_df.itertuples(index=False)]
    with left:
        choice_start = st.selectbox(
            "Bến xuất phát",
            options,
            index=0,
            key="manual_start_selector",
        )
        chosen_start_id = choice_start.split("·")[-1].strip()
        if st.session_state.manual_start_id != chosen_start_id:
            st.session_state.manual_start_id = chosen_start_id
            clear_route_result()
        start_info = stop_lookup.get(st.session_state.manual_start_id)
        if start_info:
            st.success(f"Xuất phát: **{start_info['stop_name']}** (ID: `{st.session_state.manual_start_id}`)")
    with right:
        choice_goal = st.selectbox(
            "Bến đích",
            options,
            index=min(1, len(options) - 1),
            key="manual_goal_selector",
        )
        chosen_goal_id = choice_goal.split("·")[-1].strip()
        if st.session_state.manual_goal_id != chosen_goal_id:
            st.session_state.manual_goal_id = chosen_goal_id
            clear_route_result()
        goal_info = stop_lookup.get(st.session_state.manual_goal_id)
        if goal_info:
            st.success(f"Điểm đến: **{goal_info['stop_name']}** (ID: `{st.session_state.manual_goal_id}`)")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Clear", use_container_width=True):
            reset_all()
    with c2:
        st.caption("Bạn vẫn có thể tìm đường ngay sau khi chọn bến ở phần này.")

if selected_route_rows is not None and not selected_route_rows.empty:
    st.subheader("Tuyến đang xem")
    route_name = selected_route_rows["route_name"].astype(str).iloc[0]
    st.caption(f"Đang hiển thị toàn bộ bến của tuyến **{route_name}**.")
    display_cols = ["route_name", "direction", "stop_order", "stop_name", "stop_id", "stop_lat", "stop_lon"]
    st.dataframe(
        selected_route_rows[display_cols].rename(
            columns={
                "route_name": "Tuyến",
                "direction": "Hướng",
                "stop_order": "Thứ tự",
                "stop_name": "Tên bến",
                "stop_id": "Mã bến",
                "stop_lat": "Vĩ độ",
                "stop_lon": "Kinh độ",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

# Show current coordinates summary
summary_cols = st.columns(2)
with summary_cols[0]:
    if start_coords is not None:
        st.write("**Điểm đi hiện tại**")
        st.code(start_label or f"{start_coords.lat:.6f}, {start_coords.lon:.6f}", language="text")
    else:
        st.warning("Chưa có điểm đi.")
with summary_cols[1]:
    if goal_coords is not None:
        st.write("**Điểm đến hiện tại**")
        st.code(goal_label or f"{goal_coords.lat:.6f}, {goal_coords.lon:.6f}", language="text")
    else:
        st.warning("Chưa có điểm đến.")

search_cols = st.columns([1, 1, 2])
with search_cols[0]:
    search_clicked = st.button("Tìm đường đi", type="primary", use_container_width=True)
with search_cols[1]:
    if st.button("Clear kết quả", use_container_width=True):
        clear_route_result()
        st.rerun()

# Execute route search
if search_clicked:
    start_coords, goal_coords, start_label, goal_label = get_current_coords(input_mode, stop_lookup)

    if start_coords is None or goal_coords is None:
        st.error("Bạn cần chọn đủ điểm đi và điểm đến trước khi tìm đường.")
    else:
        with st.spinner("Đang chạy thuật toán A*..."):
            try:
                results = a_star_search(start_coords, goal_coords, all_stops)
            except Exception as exc:
                st.error(f"Lỗi khi chạy tìm đường đi: {exc}")
                st.stop()

        if not results:
            st.warning("Không tìm được đường đi phù hợp từ dữ liệu hiện tại.")
            st.session_state.route_result = None
            st.session_state.route_results = []
        else:
            set_route_results(results)

# Present result if available
route_results = st.session_state.get("route_results") or ([] if st.session_state.route_result is None else [st.session_state.route_result])

if route_results:
    st.subheader("Kết quả")
    top = route_results[0]
    top_path = top["path"]

    st.success(
        f"Đã tìm được {min(3, len(route_results))} lộ trình tốt nhất. "
        f"Tuyến chính có {len(top_path)} bến, tổng thời gian ước tính: {top['duration']:.2f} phút."
    )

    cards = st.columns(min(3, len(route_results)))
    for idx, result in enumerate(route_results[:3]):
        path_nodes = result["path"]
        duration = result["duration"]
        title = format_route_rank_text(idx + 1)
        with cards[idx]:
            if idx == 0:
                st.markdown(f"### ⭐ {title}")
                st.markdown(f"**Thời gian:** {duration:.2f} phút")
                st.markdown(f"**Số bến:** {len(path_nodes)}")
            else:
                st.info(
                    f"{title}\n\n"
                    f"Thời gian: {duration:.2f} phút\n\n"
                    f"Số bến: {len(path_nodes)}"
                )

    route_segments = build_route_segments(top_path)
    if not route_segments.empty:
        st.write("**Các tuyến xe trong lộ trình chính**")
        st.dataframe(route_segments, use_container_width=True, hide_index=True)

        route_line = "  •  ".join(
            f"Tuyến {row['Tuyến']} ({row['Từ']} → {row['Đến']})"
            for _, row in route_segments.iterrows()
        )
        st.info(route_line)

    path_rows = collect_route_rows(top_path, stop_lookup)
    if path_rows:
        with st.expander("Chi tiết từng bến trong tuyến chính", expanded=False):
            st.dataframe(pd.DataFrame(path_rows), use_container_width=True, hide_index=True)

    final_walk_minutes = top["duration"] - float(top_path[-1].g)
    if final_walk_minutes > 0.1:
        st.caption(f"Còn khoảng {final_walk_minutes:.1f} phút đi bộ từ bến cuối tới điểm đến.")

st.divider()

with st.expander("Thông tin dữ liệu", expanded=False):
    info_cols = st.columns(3)
    info_cols[0].metric("Số bến", f"{len(stop_lookup):,}")
    info_cols[1].metric("Số node graph", f"{len(all_stops):,}")
    info_cols[2].metric("Số dòng route_paths", f"{len(route_paths):,}")
    st.write(f"**Database đang dùng:** `{db_path}`")

# Admin controls
login_form()

# --- Khu vực dành cho Admin ---
if st.session_state.get("is_admin", False):
    st.write("---")
    st.subheader("🛠️ Khu vực quản trị: Tạm dừng hoạt động các Tuyến Subway")

    df_for_menu = route_paths_raw if route_paths_raw is not None else route_paths                         # Lấy dataframe

    all_routes = sorted(list(df_for_menu['route_name'].unique())) 
    all_routes_str = [str(r) for r in all_routes]                                                         # Lấy danh sách tuyến định dạng string

    current_disabled = st.session_state.get("disabled_routes", set())                                     # Lấy list bến hủy từ session state
    default_blocked = [str(r) for r in current_disabled if str(r) in all_routes_str]                      # Chuyển về định dạng string

    selected_disabled = st.multiselect(                                                                   # Thanh chọn tuyến hủy     
        "Chọn các tuyến Subway muốn TẠM XÓA khỏi hệ thống:",
        options=all_routes_str,                                                                           # Danh sách tất cả tuyến
        default=default_blocked,                                                                          # Danh sách tuyến hủy
        key="admin_disable_routes_select"
    )

    if st.button("🚨 Cập nhật và Khởi động lại mạng lưới", type="primary"):
        st.session_state.disabled_routes = set(selected_disabled)                                         # Cập nhật Set các tuyến bị hủy mới
        st.success(f"Đã tạm dừng nạp dữ liệu cho các tuyến: {', '.join(selected_disabled)}")
        st.rerun()
