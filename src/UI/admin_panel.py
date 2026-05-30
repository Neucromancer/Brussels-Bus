import streamlit as st

def render_admin_panel(route_paths_raw, route_paths):
    if st.session_state.get("is_admin", False):
        st.write("---")
        st.subheader("🛠️ Khu vực quản trị: Tạm dừng hoạt động các Tuyến Subway")

        df_for_menu = route_paths_raw if route_paths_raw is not None else route_paths
        all_routes = sorted(list(df_for_menu['route_name'].dropna().unique())) 
        all_routes_str = [str(r) for r in all_routes] 

        current_disabled = st.session_state.get("disabled_routes", set())
        default_blocked = [str(r) for r in current_disabled if str(r) in all_routes_str]

        selected_disabled = st.multiselect(
            "Chọn các tuyến Subway muốn TẠM XÓA khỏi hệ thống:",
            options=all_routes_str,
            default=default_blocked,
            key="admin_disable_routes_select"
        )

        if st.button("🚨 Cập nhật và Khởi động lại mạng lưới", type="primary"):
            st.session_state.disabled_routes = set(selected_disabled)
            st.success(f"Đã tạm dừng nạp dữ liệu cho các tuyến: {', '.join(selected_disabled)}")
            st.rerun()