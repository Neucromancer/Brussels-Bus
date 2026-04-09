import os
import requests

def download_static_data():
    # 1. Thông tin API
    # Đây là endpoint chuẩn xác lấy từ tài liệu của STIB-MIVB
    api_url = "https://api-management-opendata-production.azure-api.net/api/gtfs/feed/stibmivb/static/" 
    
    headers = {
        # Sử dụng Primary Key của bạn ở đây
        "bmc-partner-key": "1ada3c80c34e446794790ed2652acf3c"
    }

    # 2. Xác định vị trí lưu file tự động
    # Lấy thư mục hiện tại của file code (src/data_engine)
    current_dir = os.path.dirname(os.path.abspath(__file__)) 
    # Lùi ra 1 cấp (src)
    src_dir = os.path.dirname(current_dir)                   
    # Lùi ra 1 cấp nữa về thư mục gốc của project (BRUSSELS-BUS)
    base_dir = os.path.dirname(src_dir)                      
    
    # Chỉ định đường dẫn tới thư mục data ở ngoài cùng
    data_dir = os.path.join(base_dir, "data")
    
    # Tự động tạo thư mục data nếu chưa có
    os.makedirs(data_dir, exist_ok=True) 
    
    # Tên file nén sẽ được lưu
    zip_file_path = os.path.join(data_dir, "brussels_gtfs.zip")

    # 3. Tiến hành gọi API và tải file
    print(f"Đang tiến hành tải dữ liệu GTFS từ máy chủ Azure...")
    try:
        # stream=True giúp tải file dung lượng lớn mà không làm treo RAM máy tính
        response = requests.get(api_url, headers=headers, stream=True)
        
        # Kiểm tra xem API có cho phép tải không (báo lỗi nếu sai Key)
        response.raise_for_status() 
        
        # Mở file zip và ghi dữ liệu từng phần vào ổ cứng
        with open(zip_file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        print(f"Tải thành công! File đã được lưu an toàn tại:\n{zip_file_path}")
        
    except requests.exceptions.HTTPError as err:
        print(f"Lỗi xác thực hoặc API từ chối: {err}")
    except requests.exceptions.RequestException as e:
        print(f"Lỗi kết nối mạng: {e}")

if __name__ == "__main__":
    download_static_data()