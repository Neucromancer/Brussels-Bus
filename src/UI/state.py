import streamlit as st
from typing import Optional, List, Dict

def init_state() -> None:
    defaults = {
        "pin_mode": "start",
        "map_start_coords": None,
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
        "selected_solution_idx": 0, # <-- BIẾN MỚI ĐỂ LƯU PHƯƠNG ÁN ĐANG CHỌN
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def clear_route_result() -> None:
    st.session_state.route_result = None
    st.session_state.route_results = []
    st.session_state.selected_solution_idx = 0 # Reset lại về 0

def set_start_coords(lat: float, lon: float, nearest_stop: Optional[str] = None) -> None:
    st.session_state.map_start_coords = {"lat": float(lat), "lon": float(lon)}
    st.session_state.map_start_nearest = nearest_stop
    clear_route_result()

def set_goal_coords(lat: float, lon: float, nearest_stop: Optional[str] = None) -> None:
    st.session_state.map_goal_coords = {"lat": float(lat), "lon": float(lon)}
    st.session_state.map_goal_nearest = nearest_stop
    clear_route_result()

def set_route_results(results: List[Dict[str, object]]) -> None:
    st.session_state.route_results = results[:3]
    st.session_state.route_result = results[0] if results else None
    st.session_state.selected_solution_idx = 0 # Khi tìm đường mới, mặc định chọn phương án 1

def reset_all() -> None:
    for key in [
        "pin_mode", "map_start_coords", "map_goal_coords", "map_start_nearest",
        "map_goal_nearest", "manual_start_id", "manual_goal_id", "route_result",
        "route_results", "selected_route_name", "last_processed_click",
        "selected_solution_idx"
    ]:
        st.session_state.pop(key, None)
    st.rerun()