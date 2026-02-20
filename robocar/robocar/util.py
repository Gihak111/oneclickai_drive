import time
import os
import cv2
import subprocess
from ftplib import FTP

# 웹서비스 정지
def stop_webservice():
    p = subprocess.run(['sudo', 'systemctl', 'stop', 'autoweb.service'], check=True, text=True, capture_output=True)

# 웹서비스 시작
def start_webservice():
    p = subprocess.run(['sudo', 'systemctl', 'start', 'autoweb.service'], check=True, text=True, capture_output=True)


# fps 계산용
def calc_fps(last_time):
    t_current = time.time()
    fps = round(1/(t_current-last_time + 10e-8),1)
    return fps

# 이미지 저장 폴더 생성
def makeImgDir():
    if not os.path.exists('image'):
        os.makedirs('image')
    if not os.path.exists('image' + os.sep + 'go'):
        os.makedirs('image' + os.sep + 'go')
    if not os.path.exists('image' + os.sep + 'left'):
        os.makedirs('image' + os.sep + 'left')   
    if not os.path.exists('image' + os.sep + 'right'):
        os.makedirs('image' + os.sep + 'right')  
    if not os.path.exists('image' + os.sep + 'brake'):
        os.makedirs('image' + os.sep + 'brake')  
    if not os.path.exists('image' + os.sep + 'parking'):
        os.makedirs('image' + os.sep + 'parking')  
    if not os.path.exists('image' + os.sep + 'other'):
        os.makedirs('image' + os.sep + 'other')  





# FTP 연결
def ftpLogin():
    # FTP 서버 정보
    server = 'osy044.ipdisk.co.kr'
    port = 21
    username = 'userTest'
    password = '00000000'

    # FTP 로그인
    ftp = FTP()
    ftp.connect(server, port)
    ftp.login(username, password)
    print(f"Connected to FTP server: {server}")
    return ftp

# FTP에 이미지 업로드
def ftpUpload(ftp, fileName):
    # Open the file in binary mode and upload it
    remote_path = 'HDD1/autonomous/' + fileName
    url_path = "http://osy044.ipdisk.co.kr:92/publist/" + remote_path
    
    with open(fileName, 'rb') as file:
        ftp.storbinary(f'STOR {remote_path}', file)
        # print(f"File '{fileName}' uploaded successfully to '{remote_path}'")
        
    return url_path
    
# FTP 연결 종료
def ftpQuit(ftp):
    # Close the FTP connection
    ftp.quit()
    print("FTP connection closed.")


if __name__ == '__main__':
    makeImgDir()
