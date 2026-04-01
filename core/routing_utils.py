from utils.time_utils import time_to_seconds

def get_next_departure(current_time, departure_time):
    dep = time_to_seconds(departure_time)
    return dep if dep >= current_time else None
