def build_graph(stop_times):
    """
    Build graph: stop -> list of neighbors
    """
    graph = {}

    # group by trip
    trips = {}
    for trip_id, stop_id, arr, dep, seq in stop_times:
        trips.setdefault(trip_id, []).append((seq, stop_id, dep))

    # sort each trip by sequence
    for trip_id in trips:
        trips[trip_id].sort()

        for i in range(len(trips[trip_id]) - 1):
            _, current_stop, dep_time = trips[trip_id][i]
            _, next_stop, next_dep = trips[trip_id][i+1]

            graph.setdefault(current_stop, []).append((next_stop, dep_time))

    return graph
