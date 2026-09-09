"""
다리 1개의 발 좌표(x, y, z) -> 서보 3개(Hip/Knee/Wave)의 "영점 대비 각도 오프셋".

esp32_controller.ino의 IK(simple_linkage_ik / wiggle_plane_ik / single_leg_plane_ik /
single_leg_ctrl)를 그대로 파이썬으로 포팅한 것이다. 펌웨어 쪽 링크 치수나 서보
방향(ServoDirection)을 바꾸면 여기 상수도 반드시 같이 바꿔야 한다 — 이 파일이
그 동기화 대상 전부를 모아두는 곳이다.

펌웨어는 최종 서보 각도를 `중간각(영점) + 여기서 계산한 오프셋`으로 만든다.
이 모듈은 오프셋(순수 기구학)까지만 책임지고, 어떤 영점에 얹을지와 각도 제한은
호출하는 쪽이 정한다 — 그래야 "영점을 어디로 볼 것인가"를 호출부가 바꿀 수 있다.

motion_cont.py의 "예제 걷기" 자동 생성 기능이 이 모듈을 사용한다.
"""
import math

# WAVEGO 기구 치수 (esp32_controller.ino와 동일)
LINK_W, LINK_S = 19.15, 12.2
LINK_A, LINK_B = 40.0, 40.0
LINK_C, LINK_D, LINK_E = 39.8153, 31.7750, 30.8076
SERVO_DIR = [1, -1, -1, 1, 1, -1, -1, 1, 1, -1, -1, 1]
# 다리 번호 -> (Hip/FORE, Knee/BACK, Wave) 서보 인덱스
LEG_SERVOS = {1: (0, 1, 2), 2: (4, 5, 3), 3: (6, 7, 8), 4: (10, 11, 9)}


def _c1(v):
    return max(-1.0, min(1.0, v))


def _wiggle_plane_ik(a_in, b_in):
    """정면 평면 IK: (z, y) -> (Wave 서보 각도, 유효 다리 길이)"""
    la = LINK_W
    l2c = a_in * a_in + b_in * b_in
    lc = math.sqrt(l2c)
    lam = math.degrees(math.atan(a_in / b_in))
    psi = math.degrees(math.acos(_c1(la / lc)))
    lb = math.sqrt(max(0.0, l2c - la * la))
    return psi + lam - 90.0, lb


def _single_leg_plane_ik(x_in, y_in):
    """측면 평면 5절 링크 IK: (x, y) -> (Hip 각도 beta, 무릎 링크 좌표)"""
    ls2 = LINK_S / 2.0
    l_cd = (LINK_C + LINK_D) ** 2
    le2 = LINK_E ** 2
    la2 = LINK_A ** 2
    bs_sq = (x_in + ls2) ** 2 + y_in ** 2
    bs = math.sqrt(bs_sq)
    lam = math.acos(_c1((bs_sq + la2 - l_cd - le2) / (2.0 * bs * LINK_A)))
    delta = math.atan((x_in + ls2) / y_in)
    beta = lam - delta
    theta = math.atan((LINK_C + LINK_D) / LINK_E)
    sledc = math.sqrt(le2 + l_cd)
    omega = math.asin(_c1((y_in - math.cos(beta) * LINK_A) / sledc))
    nu = math.pi - theta - omega
    dfx, dfy = math.cos(nu) * LINK_E, math.sin(nu) * LINK_E
    mu = math.pi / 2.0 - nu
    dex, dey = math.cos(mu) * LINK_D, math.sin(mu) * LINK_D
    return math.degrees(beta), x_in + dfx - dex, y_in - dfy - dey


def _simple_linkage_ik(a_in, b_in):
    """2링크 IK: 무릎(BACK) 서보 각도 alpha"""
    la, lb = LINK_A, LINK_B
    l2c = a_in * a_in + b_in * b_in
    lc = math.sqrt(l2c)
    lam = math.degrees(math.atan(b_in / a_in)) if a_in != 0 else 0.0
    psi = math.degrees(math.acos(_c1((la * la - lb * lb + l2c) / (2.0 * la * lc))))
    return 90.0 - lam - psi


def leg_offsets(leg, x, y, z):
    """
    다리 1개의 발 좌표 -> {서보 인덱스: 영점 대비 각도 오프셋}
    (펌웨어 single_leg_ctrl에서 ServoMiddleAngle에 더해지는 부분과 동일)
    """
    nf, nb, nw = LEG_SERVOS[leg]
    w_alpha, w_len = _wiggle_plane_ik(z, y)
    beta, px, py = _single_leg_plane_ik(x, w_len)
    alpha = _simple_linkage_ik(py, px - LINK_S / 2.0)
    return {
        nw: w_alpha * SERVO_DIR[nw],
        nf: (90.0 - beta) * SERVO_DIR[nf],
        nb: alpha * SERVO_DIR[nb],
    }
