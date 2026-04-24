from logic.models import Stop, NextStopInfo
from const import BUS_SPEED, TRANSFER_PENALTY
from logic.helpers import haversine

# I. Lấy thời gian chờ trung bình của tuyến (route_id) từ database

def get_waiting_time(route_id):
    return TRANSFER_PENALTY

# II. Nạp dữ liệu từ DataFrame Khởi tạo Stop

def load_data(route_path_dataframe):
    all_stops = {}                                                                            # {id: Stop object}
    
    # 1. --- Khởi tạo tất cả Stop trước, còn thiếu trường next_stops (Sử dụng stop_id làm khóa duy nhất) ---

    for _, row in route_path_dataframe.iterrows():                                            # Duyệt qua từng dòng của DataFrame
        sid = str(row['stop_id'])                                                             # Ép kiểu string cho chắc chắn
        if sid not in all_stops:                                                              # Nếu bến này chưa được khởi tạo
            all_stops[sid] = Stop(sid, row['stop_name'], row['stop_lat'], row['stop_lon'])    # Tạo đối tượng Stop và lưu vào dictionary với stop_id làm khóa

    # 2. --- Tạo kết nối NextStopInfo, thêm vào trường next_stops của các Stop ---

    df_sorted = route_path_dataframe.sort_values(['route_name', 'direction', 'stop_order'])   # Sắp xếp theo Tuyến -> Hướng -> Thứ tự bến
    
    for i in range(len(df_sorted) - 1):                                                       # Duyệt từng dòng, xét 2 dòng liên tiếp
        curr_row = df_sorted.iloc[i]
        next_row = df_sorted.iloc[i+1]
        
        if (curr_row['route_name'] == next_row['route_name'] and                              # Nếu cùng tuyến
            curr_row['direction'] == next_row['direction']):                                  # Và cùng hướng đi
                                                                                              
            curr_stop = all_stops[str(curr_row['stop_id'])]
            next_stop = all_stops[str(next_row['stop_id'])]

            travel_time = (haversine(curr_stop.lat, curr_stop.lon, next_stop.lat, next_stop.lon) / BUS_SPEED) * 60 
            
            connection = NextStopInfo(next_stop, travel_time, str(curr_row['route_name']),)   # Khởi tạo NextStopInfor
            curr_stop.next_stops.append(connection)                                           # Thêm vào danh sách next_stops của đối tượng Stop hiện tại
            
    return list(all_stops.values())                                                           # Trả về danh sách đối tượng Stop đã tạo