#### Thuật toán A*
 ## tính năng các file, hàm
  #astar:
  -triển khai thuật toán A*, trả về những điểm sẽ đi qua
  #data_loader:
  - lấy bảng stop_times từ database'
  -lấy tọa độ các stop xuát hiện trong bảng stop_times 
  #graph_builder
   -Build graph: stop -> danh sách các lân cận neighbor :
     +trả về sao cho mỗi stop có các cạnh tới, thời điểm xuất phát,thời điểm tới neighbor
  #heuristic:
    -Hàm heuristic nhờ công thức haversine
  #routing utils:
     -xem xét thời điểm xuất phát đến neighbor có phù hợp k
  #neareststop: tìm stop gần nhất tới tọa độ xuấ phát
  #time_utils: chuyển thời gian dạng trong database sang seconds
  #test_astar : thử astar với thời gian thực và tọa độ trong thành phố brussels
## Project Structure

core/
  ├── a_star.py
  ├── data_loader.py
  ├── graph_builder.py
  ├── heuristic.py
  ├── routing_utils.py

utils/
  ├── nearest_stop.py
  ├── time_utils.py

data/
  └── stib_database.db
test_astar.py
  
