I. Logic
I.1. File models.py
Cấu trúc dữ liệu cho Stop 
Cấu trúc dữ liệu cho AStarNode là một node của quá trình duyệt nhánh

I.2. File helpers.py
Gồm các hàm hỗ trợ tính toán:
+ 
+
+
+
+ (): 

I.3. File router.py
* a_star_search(user_coords, dest_coords, all_stops): 
- Nhận vào dữ liệu là địa chỉ đầu, địa chỉ cuối, danh sách bến
- Trả về list đường đi thỏa mãn từ nhanh đến chậm

II. Data

II.1. File api_client.py
* download_static_data(): Tải file zip dữ liệu về máy bao gồm có các file .txt chứa dữ liệu, đặt tại data/

II.2. File data_process.py
* load_data(route_path_dataframe): Nhận vào dữ liệu data_frame và khởi tạo các đối tượng Stop.
 Yêu cầu dữ liệu đầu vào là một data_frame chứa thông tin về Stop gồm các trường: 
+ stop_id (mã bến xe)
+ stop_name (tên bến xe) 
+ stop_lat (vĩ độ) 
+ stop_lon (kinh độ)
+ direction (hướng đi hay về)
+ route_name (tên chuyến) 
+ stop_order (thứ tự là Stop thứ mấy trong chuyến)

III.3. File db_manager.py
* unzip_files(): Giải nén file .zip thu được khi tải về thành các file .txt
* build_route_paths(): Tổng hợp dữ liệu từ các file .txt tạo dataframe route_paths