import os
from flask import Flask, request, render_template
from core.a_star import a_star
from utils.nearest_stop import NearestStopFinder
from core.graph_builder import build_graph
from core.data_loader import load_stop_times,load_coordinates
from core.schedule_builder import build_schedule
import datetime 
from utils.time_utils import time_to_seconds

print(os.path.exists("data/stib_database.db"))

app = Flask(__name__)


# Load nearest stop system
finder = NearestStopFinder("data/stib_database.db")
trip_times = load_stop_times("data/stib_database.db")


# Example placeholders (you must build these)
graph = build_graph("data/stib_database.db")
coordinates = load_coordinates("data/stib_database.db")
schedule = build_schedule("data/stib_database.db")



@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        start_lat = float(request.form["start_lat"])
        start_lon = float(request.form["start_lon"])

        dest_lat = float(request.form["dest_lat"])
        dest_lon = float(request.form["dest_lon"])

        start_stop = finder.find(start_lat, start_lon)
        goal_stop = finder.find(dest_lat, dest_lon)

        now = datetime.datetime.now().strftime("%H:%M:%S")

        result = a_star(
            graph,
            start=start_stop,
            goal=goal_stop,
            start_time=time_to_seconds(now),
            coordinates=coordinates,
            schedule=schedule,
            trip_times=trip_times
        )

        if result is None:
            return render_template("index.html", error="No route found")

        path, trips = result

        return render_template("index.html", path=path, trips=trips)

    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)