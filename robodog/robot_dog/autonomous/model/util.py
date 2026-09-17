"""학습 데이터 정리 유틸리티 (autonomous_examples/model/util.py 에 해당)"""
import os

IMAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "image")


def deleteImg(image_path=IMAGE_DIR):
    """이미지 폴더 안의 1KB 미만 파일(깨진 저장) 삭제"""
    if not os.path.exists(image_path):
        print("No image directory found.")
        return
    for root, _dirs, files in os.walk(image_path):
        for file in files:
            file_path = os.path.join(root, file)
            if os.path.getsize(file_path) < 1024:
                os.remove(file_path)
                print(f"Deleted {file_path}")
