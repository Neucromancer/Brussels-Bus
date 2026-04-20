from logic.models import Stop, NextStopInfo
from logic.const import TRANSFER_PENALTY

# 1. Lấy thời gian chờ trung bình của tuyến (route_id) từ database

def get_waiting_time(route_id):
    return TRANSFER_PENALTY

# 2. Nạp dữ liệu từ DataFrame Khởi tạo Stop

def load_data(route_path_dataframe):
    all_stops = {} # {id: Stop object}
    
    # 1. Khởi tạo tất cả bến xe trước (Sử dụng stop_id làm khóa duy nhất)
    for index, row in route_path_dataframe.iterrows():
        sid = str(row['stop_id']) # Ép kiểu string cho chắc chắn
        if sid not in all_stops:
            all_stops[sid] = Stop(sid, row['stop_name'], row['stop_lat'], row['stop_lon'])

    # 2. Tạo kết nối Neighbors
    # Sắp xếp theo Tên tuyến (route_name), Hướng (direction) và Thứ tự (stop_order)
    df_sorted = route_path_dataframe.sort_values(['route_name', 'direction', 'stop_order'])
    
    for i in range(len(df_sorted) - 1):
        curr_row = df_sorted.iloc[i]
        next_row = df_sorted.iloc[i+1]
        
        # KIỂM TRA QUAN TRỌNG: 
        # Chỉ nối nếu cùng Tuyến (route_name) VÀ cùng Hướng (direction)
        if (curr_row['route_name'] == next_row['route_name'] and 
            curr_row['direction'] == next_row['direction']):
            
            curr_stop = all_stops[str(curr_row['stop_id'])]
            next_stop = all_stops[str(next_row['stop_id'])]
            
            # t_time: Thời gian di chuyển (để 2 phút là thời gian di chuyển để test)
            t_time = 2 
            
            # Tạo kết nối mang theo route_name (ví dụ: "1", "71")
            connection = NextStopInfo(next_stop, t_time, str(curr_row['route_name']),)
            curr_stop.next_stops.append(connection)
            
    return list(all_stops.values())