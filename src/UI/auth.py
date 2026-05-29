# auth.py
import streamlit as st

def init_auth_state():
    """Khởi tạo trạng thái đăng nhập nếu chưa có"""
    if "is_admin" not in st.session_state:
        st.session_state.is_admin = False

def login_form():
    """Hiển thị form đăng nhập và quản lý trạng thái Admin"""
    init_auth_state()

    if not st.session_state.is_admin:
        with st.sidebar.expander("🔐 Đăng nhập Quản trị viên"):
            # Thêm `key` để tránh lỗi trùng lặp component trong Streamlit
            username = st.text_input("Tài khoản", key="auth_username")
            password = st.text_input("Mật khẩu", type="password", key="auth_password")
            
            if st.button("Đăng nhập", key="auth_login_button"):
                if username == "admin" and password == "brussels2026":
                    st.session_state.is_admin = True
                    st.success("Đăng nhập Admin thành công!")
                    st.rerun()
                else:
                    st.error("Sai tài khoản hoặc mật khẩu")
    else:
        st.sidebar.success("⚡ Chế độ: Quản trị viên")
        if st.sidebar.button("Đăng xuất", key="auth_logout_button"):
            st.session_state.is_admin = False
            st.rerun()