echo "=== My App Boot Script ==="
echo "Time: $(date)"
echo

cd /home/pi/Desktop/web_service || {
    echo "프로젝트 폴더로 이동 실패"
    read -p "Enter를 누르면 닫힘..."
    exit 1
}

echo "인터넷 연결 확인 중..."

# 인터넷 연결될 때까지 대기
until ping -c 1 -W 2 1.1.1.1 > /dev/null 2>&1; do
    echo "아직 인터넷 연결 안 됨... 3초 후 재시도"
    sleep 3
done

echo "인터넷 연결 확인됨!"

echo "5초간 대기 중..."
sleep 5
echo


echo "Python 코드 실행 시작"
echo "--------------------------------"

python3 -u flask_web.py

echo "--------------------------------"
echo "Python 코드가 종료됨. 종료 코드: $?"
echo

read -p "터미널을 닫으려면 Enter를 누르세요..."