
# 1. Tìm đường dẫn đến thư mục 'src'
# __file__ là db_manager.py, dirname là data_engine, dirname của nó là src
current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.dirname(current_dir) 

# 2. Thêm 'src' vào danh sách tìm kiếm của Python
if src_path not in sys.path:
    sys.path.insert(0, src_path)
