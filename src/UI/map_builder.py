import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from data_engine.data_process import get_curved_segment

DEFAULT_MAP_CENTER = (50.8503, 4.3517)

@dataclass(frozen=True)
class Coords:
    lat: float
    lon: float

def format_route_rank_text(rank: int) -> str:
    return {1: "Tuyến chính", 2: "Phương án 2", 3: "Phương án 3"}.get(rank, f"Phương án {rank}")

def nearest_stop_id(lat: float, lon: float, coordinates: Dict[str, Tuple[float, float]]) -> Optional[str]:
    if not coordinates: return None
    return min(coordinates.keys(), key=lambda sid: (lat - coordinates[sid][0]) ** 2 + (lon - coordinates[sid][1]) ** 2)

def collect_route_rows(path_nodes: List[object], stop_lookup: Dict) -> List[Dict]:
    rows = []
    for idx, node in enumerate(path_nodes, start=1):
        stop = getattr(node, "stop", None)
        if not stop: continue
        stop_id = str(getattr(stop, "id", ""))
        info = stop_lookup.get(stop_id, {})
        lat = getattr(stop, "lat", None) or info.get("stop_lat")
        lon = getattr(stop, "lon", None) or info.get("stop_lon")
        rows.append({
            "Step": idx, "Stop ID": stop_id,
            "Stop name": info.get("stop_name") or getattr(stop, "name", None) or f"Stop {stop_id}",
            "Lat": float(lat) if lat is not None else None,
            "Lon": float(lon) if lon is not None else None,
            "Route": getattr(node, "route_id", None) or "---",
            "Time (min)": round(float(getattr(node, "g", 0.0)), 2),
        })
    return rows

def get_current_coords(input_mode: str, stop_lookup: Dict) -> Tuple[Optional[Coords], Optional[Coords], Optional[str], Optional[str]]:
    if input_mode == "Ghim trên bản đồ":
        start, goal = st.session_state.map_start_coords, st.session_state.map_goal_coords
        start_coords = Coords(start["lat"], start["lon"]) if start else None
        goal_coords = Coords(goal["lat"], goal["lon"]) if goal else None
        start_label = goal_label = None
        if start_coords:
            nearest = st.session_state.map_start_nearest or ""
            start_label = f"{start_coords.lat:.6f}, {start_coords.lon:.6f}" + (f"  •  gần bến {stop_lookup[nearest]['stop_name']}" if nearest in stop_lookup else "")
        if goal_coords:
            nearest = st.session_state.map_goal_nearest or ""
            goal_label = f"{goal_coords.lat:.6f}, {goal_coords.lon:.6f}" + (f"  •  gần bến {stop_lookup[nearest]['stop_name']}" if nearest in stop_lookup else "")
        return start_coords, goal_coords, start_label, goal_label

    start_id, goal_id = st.session_state.manual_start_id, st.session_state.manual_goal_id
    start_info, goal_info = stop_lookup.get(start_id), stop_lookup.get(goal_id)
    start_coords = Coords(float(start_info["stop_lat"]), float(start_info["stop_lon"])) if start_info else None
    goal_coords = Coords(float(goal_info["stop_lat"]), float(goal_info["stop_lon"])) if goal_info else None
    start_label = f"{start_info['stop_name']} (ID: {start_id})" if start_info else None
    goal_label = f"{goal_info['stop_name']} (ID: {goal_id})" if goal_info else None
    return start_coords, goal_coords, start_label, goal_label

def draw_solution_path(m, path_nodes, stop_lookup, line_color, line_weight, line_opacity, dashed_walk_color="gray", show_markers=False, label=""):
    path_rows = collect_route_rows(path_nodes, stop_lookup)
    route_points = []
    for i in range(len(path_rows) - 1):
        row_A, row_B = path_rows[i], path_rows[i + 1]
        lat_A, lon_A = row_A.get("Lat"), row_A.get("Lon")
        lat_B, lon_B = row_B.get("Lat"), row_B.get("Lon")
        if None in (lat_A, lon_A, lat_B, lon_B): continue

        route_id = row_B.get("Route", "---")
        if route_id == "---":
            segment_path = [(lat_A, lon_A), (lat_B, lon_B)]
            folium.PolyLine(segment_path, color=dashed_walk_color, weight=max(3, line_weight - 2), dash_array="5, 10", opacity=min(0.85, line_opacity + 0.1), tooltip=f"Đi bộ / chuyển tuyến" + (f" · {label}" if label else "")).add_to(m)
        else:
            segment_path = get_curved_segment(route_id=route_id, lat_A=lat_A, lon_A=lon_A, lat_B=lat_B, lon_B=lon_B)
            folium.PolyLine(segment_path, color=line_color, weight=line_weight, opacity=line_opacity, tooltip=f"{label} · Tuyến {route_id}" if label else f"Tuyến {route_id}").add_to(m)
        route_points.extend(segment_path)

    if show_markers:
        for idx, row in enumerate(path_rows):
            lat, lon = row.get("Lat"), row.get("Lon")
            if None in (lat, lon): continue
            is_first, is_last = idx == 0, idx == len(path_rows) - 1
            color, icon = ("green", "play") if is_first else (("red", "flag") if is_last else ("blue", "circle"))
            popup_html = f"<b>{'Điểm đầu' if is_first else 'Điểm cuối' if is_last else 'Bến trung gian'}</b><br>{row.get('Stop name')}<br>ID: {row.get('Stop ID')}<br>Tuyến: {row.get('Route')}<br>({lat:.6f}, {lon:.6f})"
            folium.Marker([lat, lon], popup=folium.Popup(popup_html, max_width=320), tooltip=f"{row.get('Stop name')} · {row.get('Route')}", icon=folium.Icon(color=color, icon=icon, prefix="fa")).add_to(m)
    return route_points

def draw_route_stops(m, route_rows, stop_lookup):
    points = []
    if route_rows.empty: return points
    for _, row in route_rows.iterrows():
        lat, lon = row.get("stop_lat"), row.get("stop_lon")
        if pd.isna(lat) or pd.isna(lon): continue
        points.append((float(lat), float(lon)))
        popup_html = f"<b>Tuyến {row.get('route_name')}</b><br>Hướng: {row.get('direction')}<br>Thứ tự: {row.get('stop_order')}<br>{row.get('stop_name')}<br>ID: {row.get('stop_id')}<br>({lat:.6f}, {lon:.6f})"
        folium.CircleMarker([float(lat), float(lon)], radius=5, color="#ff7f0e", fill=True, fill_opacity=0.9, popup=folium.Popup(popup_html, max_width=320), tooltip=f"Tuyến {row.get('route_name')} · {row.get('stop_name')}").add_to(m)

    for (_, _direction), group in route_rows.groupby(["route_name", "direction"], sort=False):
        rows = list(group.sort_values(["stop_order", "stop_id"]).itertuples(index=False))
        for c, n in zip(rows, rows[1:]):
            segment_path = get_curved_segment(route_id=str(c.route_name), lat_A=float(c.stop_lat), lon_A=float(c.stop_lon), lat_B=float(n.stop_lat), lon_B=float(n.stop_lon))
            folium.PolyLine(segment_path, color="#ff7f0e", weight=3, opacity=0.75, tooltip=f"Tuyến {c.route_name}").add_to(m)
            points.extend(segment_path)
    return points

def build_route_map(all_stops, stop_lookup, path_nodes=None, start_coords=None, goal_coords=None, start_nearest_stop=None, goal_nearest_stop=None, selected_route_rows=None) -> folium.Map:
    coords = [(float(s.lat), float(s.lon)) for s in all_stops if getattr(s, "lat", None) is not None and getattr(s, "lon", None) is not None]
    center_lat, center_lon = (sum(lat for lat, _ in coords)/len(coords), sum(lon for _, lon in coords)/len(coords)) if coords else DEFAULT_MAP_CENTER
    if start_coords: center_lat, center_lon = start_coords.lat, start_coords.lon
    elif goal_coords: center_lat, center_lon = goal_coords.lat, goal_coords.lon

    m = folium.Map(location=[center_lat, center_lon], zoom_start=13, control_scale=True, tiles="OpenStreetMap", width="100%", height=650)
    bound_points = []

    if selected_route_rows is not None and not selected_route_rows.empty:
        bound_points.extend(draw_route_stops(m, selected_route_rows, stop_lookup))

    # --- ĐÃ SỬA: CHỈ VẼ DUY NHẤT 1 LỘ TRÌNH ĐANG CHỌN (path_nodes) ---
    if path_nodes:
        bound_points.extend(draw_solution_path(
            m, path_nodes, stop_lookup, 
            line_color="#1f77b4", line_weight=8, line_opacity=0.9, 
            show_markers=True, label="Lộ trình đang chọn"
        ))

    if start_coords is not None:
        folium.Marker([start_coords.lat, start_coords.lon], popup=folium.Popup(f"<b>Điểm đi</b><br>Gần: {stop_lookup[start_nearest_stop]['stop_name'] if start_nearest_stop in stop_lookup else ''}", max_width=320), tooltip="Điểm đi", icon=folium.Icon(color="green", icon="star", prefix="fa")).add_to(m)
    if goal_coords is not None:
        folium.Marker([goal_coords.lat, goal_coords.lon], popup=folium.Popup(f"<b>Điểm đến</b><br>Gần: {stop_lookup[goal_nearest_stop]['stop_name'] if goal_nearest_stop in stop_lookup else ''}", max_width=320), tooltip="Điểm đến", icon=folium.Icon(color="red", icon="flag", prefix="fa")).add_to(m)

    if path_nodes and start_coords is not None and path_nodes[0].stop is not None:
        bound_points.extend([(start_coords.lat, start_coords.lon), (path_nodes[0].stop.lat, path_nodes[0].stop.lon)])
        folium.PolyLine([(start_coords.lat, start_coords.lon), (path_nodes[0].stop.lat, path_nodes[0].stop.lon)], color="#2ca02c", weight=3, dash_array="6, 6", opacity=0.75).add_to(m)
    if path_nodes and goal_coords is not None and path_nodes[-1].stop is not None:
        bound_points.extend([(path_nodes[-1].stop.lat, path_nodes[-1].stop.lon), (goal_coords.lat, goal_coords.lon)])
        folium.PolyLine([(path_nodes[-1].stop.lat, path_nodes[-1].stop.lon), (goal_coords.lat, goal_coords.lon)], color="#d62728", weight=3, dash_array="6, 6", opacity=0.75).add_to(m)

    if bound_points: m.fit_bounds(bound_points, padding=(30, 30))
    return m

def render_map(m: folium.Map):
    return st_folium(m, width="100%", height=650, key="interactive_map")