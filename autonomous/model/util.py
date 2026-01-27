import os



 # 이미지 사이즈 1kb 보다 작으면 삭제
def deleteImg():
    # 이미지 폴더 경로
    image_path = '../image'

    if not os.path.exists(image_path):
        print("No image directory found.")
        return
    
    # 이미지 폴더 내 모든 폴더 안의 파일에 대해 반복
    for root, dirs, files in os.walk(image_path):
        for file in files:
            # 파일 경로
            file_path = os.path.join(root, file)
            
            # 파일 크기 확인
            if os.path.getsize(file_path) < 1024:  # 1KB 보다 작으면 삭제
                os.remove(file_path)
                print(f"Deleted {file_path}")