def build_graph(stop_times):
    """
    Build graph: stop -> list of neighbors
    danh sách stop và đỉnh kề
    """
    graph = {}

    # nhóm vào những dòng dữ liệu cùng trip_id
    trips = {}
    for trip_id, stop_id, arr, dep, seq in stop_times:
        trips.setdefault(trip_id, []).append((seq, stop_id, dep))

    # xếp theo thứ tự đầu cuối quãng đường nhờ thuộc tính sequence
    for trip_id in trips:
        trips[trip_id].sort()

        for i in range(len(trips[trip_id]) - 1):
            _, current_stop, dep_time = trips[trip_id][i]
            _, next_stop, next_dep = trips[trip_id][i+1]

            graph.setdefault(current_stop, []).append((next_stop, dep_time)) #1 cạnh của 1 node gồm thời gian xuất phát và điểm đến tiếp theo

    return graph
