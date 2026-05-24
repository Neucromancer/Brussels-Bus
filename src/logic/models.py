class Stop:
    def __init__(self, stop_id, name, lat, lon):
        self.id = stop_id
        self.name = name
        self.lat = lat
        self.lon = lon
        # Danh sách các đối tượng NextStopInfo
        self.next_stops = [] 

    def add_neighbor(self, stop_obj, time, route_id):
        self.next_stops.append(NextStopInfo(stop_obj, time, route_id))

class NextStopInfo:
    def __init__(self, stop_obj, travel_time, route_id):
        self.stop = stop_obj      # Đối tượng Stop kế tiếp
        self.travel_time = travel_time  # A(x)
        self.route_id = route_id  # Số tuyến next_stop (Ví dụ: "71", "3")

class Route:
    def __init__(self, route_id, route_name, wait_time):
        self.id = route_id
        self.name = route_name
        self.wait_time = wait_time # Dùng cho C(x)
        self.ordered_stops = []    # Danh sách Stop theo thứ tự (để vẽ map)
        self.stop_intervals = []   # Thời gian di chuyển giữa các chặng (A(x))

    def add_stop(self, stop_obj, time_from_prev=0):
        self.ordered_stops.append(stop_obj)
        self.stop_intervals.append(time_from_prev)

class AStarNode:
    def __init__(self, stop, parent=None, g=0, f=0, route_id=None):
        self.stop = stop
        self.parent = parent
        self.g = g # Chi phí thực tế đã đi (A + C)
        self.f = f # Chi phí dự đoán gồm có thực tế và cả ước lượng (g + B)
        self.route_id = route_id # Tuyến đang đi tại node này

    # Để Priority Queue so sánh được các Node với nhau
    def __lt__(self, other):
        return self.f < other.f

class Coords:
    def __init__(self, lat, lon):
        self.lat = lat
        self.lon = lon