// ============================================================================
// 로봇개 ESP32 메인 컨트롤러 (역기구학 엔진 + 보행 + 포즈 보간)
//
// 아두이노 보드: ESP32 Dev Module / 라이브러리: Adafruit SSD1306, Adafruit GFX
//
// 시리얼 커맨드 (USB Serial, 115200):
//   M <fb> <lr>        이동 (-1/0/1)
//   S <speed>          보행 속도 (STEP_ITERATE, 0.0001~0.1)
//   F <n>              특수 기능: 1=엎드리기, 2=악수, 3=점프, 4=기립
//   J <ms> <a0..a11> [mode]
//                      포즈: 12개 서보를 ms 동안 보간 이동 (동작 재생용)
//                      mode 0=코사인(기본) 1=선형 2=ease-in 3=ease-out
//   K <ms> <i> <a> ... 부분 포즈: 지정한 서보(들)만 이동, 나머지는 현재 위치 유지
//                      (동작 편집 슬라이더 미리보기용, idx/angle 쌍 반복 가능)
//   T / E              토크 해제 / 토크 활성화(현재 실측 자세 동기화 후 켜서 튐 방지)
//   U / V              서보 실측 각도 읽기 -> "POS ..." (응답 없는 서보는 "?")
//                      / 목표 각도 읽기 -> "ANG ..."
//   C 0/1              캘리브레이션 모드 (스탠드 자세 유지하며 중간각 조정)
//   A <a0..a11>        캘리브레이션 중간각 12개
//   O <p0..p11>        서보 ID(핀) 맵 12개 / P <joint> <pin>: 단건
//   I <old> <new>      서보 ID 변경 (조립 유틸용)
//   Q <id>             서보 핑 -> "OK"/"ERR" (실패 시 "QDBG echo=.. rx=[..]" 진단 한 줄 추가)
//   Z                  서보 버스 진단: 에코 여부 재감지 -> "ECHO 0/1"
//   Y                  서보 버스 수신 자가진단: UART 내부 루프백으로 핑 패킷을 되돌려
//                      파서까지 도달하는지 확인 -> "LOOP OK"/"LOOP FAIL rx=[..]"
//                      (OK면 펌웨어 수신 경로는 정상 = 남는 원인은 배선/전원)
//   H                  하트비트 (워치독 갱신 전용)
//   L/R/D              조명/RGB(TODO)/OLED 텍스트
//
// 워치독: 보행 중 2초간 아무 커맨드가 없으면 자동 정지 (통신 두절 안전장치)
//
// 기준 자세: IK로 만드는 모든 자세(기립/보행/특수기능)는 "기준 자세"에서의 관절
//   오프셋(NeutralOffset)을 빼서 재중심화한다. 그래서 캘리브레이션 각도
//   (ServoMiddleAngle, A 커맨드)가 곧 로봇의 기준 자세가 되고, 조립 유틸리티
//   align_90.py로 맞춘 자세와 기준이 일치한다. (재중심화 전에는 WAVEGO 기준
//   웅크린 높이가 중심이라, 캘리브레이션 90도에서 수십 도 벗어난 자세를 중심으로
//   움직여 서보가 가동범위 끝에 몰렸다)
//
// 자세 전환(v3): 보행 시작/정지, 기립, 캘리브레이션 진입/종료가 전부 보간으로
//   부드럽게 이어진다. 정지 상태에서 보행을 시작할 때는 먼저 "보행 시작 자세"로
//   진입한 뒤 걷기 시작하므로, 토크 해제 후 손으로 잡은 임의 자세나 동작 재생
//   직후에도 다리가 튀지 않는다.
// ============================================================================
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Arduino.h>
#include <Wire.h>
#include <driver/uart.h> // 루프백 자가진단(Y)용
#include <math.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 32
#define OLED_RESET -1
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

String oledLine1 = "";
String oledLine2 = "";
String oledLine3 = "";

void updateOLED(String msg1, String msg2, String msg3) {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println(msg1);
  display.println(msg2);
  display.println(msg3);
  display.display();
}

void updateOLED_buffered(int lineIdx, String msg) {
  if (lineIdx == 1 || lineIdx == 0) oledLine1 = msg;
  else if (lineIdx == 2) oledLine2 = msg;
  else if (lineIdx == 3) oledLine3 = msg;
  updateOLED(oledLine1, oledLine2, oledLine3);
}

// 서보 버스 (Serial2, 1Mbaud)
#define RXD2 18
#define TXD2 19

// --- Configuration & Constants (WAVEGO 기구 치수) ---
const float linkage_w = 19.15;
const float wiggleError = 0;
const float linkage_s = 12.2;
const float linkage_a = 40.0;
const float linkage_b = 40.0;
const float linkage_c = 39.8153;
const float linkage_d = 31.7750;
const float linkage_e = 30.8076;

const float WALK_HEIGHT_MAX = 110.0;
const float WALK_HEIGHT_MIN = 75.0;
const float WALK_HEIGHT = 95.0;
const float WALK_LIFT = 9.0;
const float WALK_RANGE = 40.0;
const float WALK_ACC = 5.0;
const float WALK_EXTENDED_X = 16.0;
const float WALK_EXTENDED_Z = 25.0;
const float WALK_SIDE_MAX = 30.0;
const float STAND_HEIGHT = 95.0;
const float WALK_LIFT_PROP = 0.25;

// Precalculated
const float LAxLA = linkage_a * linkage_a;
const float LBxLB = linkage_b * linkage_b;
const float LWxLW = linkage_w * linkage_w;
const float LExLE = linkage_e * linkage_e;
const float LAxLA_LBxLB = LAxLA - LBxLB;
const float LBxLB_LAxLA = LBxLB - LAxLA;
const float L_CD = (linkage_c + linkage_d) * (linkage_c + linkage_d);
const float LAx2 = 2 * linkage_a;
const float LBx2 = 2 * linkage_b;
const float E_PI = 180.0 / PI;
const float LSs2 = linkage_s / 2.0;
const float aLCDE = atan((linkage_c + linkage_d) / linkage_e);
const float sLEDC = sqrt(linkage_e * linkage_e +
                         (linkage_d + linkage_c) * (linkage_d + linkage_c));

// --- State variables ---
float GLOBAL_STEP = 0.0;
float STEP_ITERATE = 0.005; // 보행 속도 (1사이클 = 1/STEP_ITERATE 틱 x 5ms)
int moveFB = 0;
int moveLR = 0;
int STAND_STILL = 1;
int funcMode = 0;
bool calibrationMode = false;
bool torqueOn = false;
unsigned long lastStepMillis = 0;

// 워치독: 보행 중 통신 두절 시 자동 정지
unsigned long lastCmdMillis = 0;
const unsigned long WATCHDOG_TIMEOUT_MS = 2000;

// 포즈(동작 재생) 보간 엔진 상태
enum PoseExit { POSE_HOLD = 0, POSE_TO_IDLE = 1, POSE_TO_GAIT = 2 };
enum PoseEase { EASE_INOUT = 0, EASE_LINEAR = 1, EASE_IN = 2, EASE_OUT = 3 };
bool poseMode = false;     // true면 보행 대신 포즈 보간 수행
bool poseDone = false;     // 보간 완료 후 유지(추가 쓰기 중단)
int poseExit = POSE_HOLD;  // 보간 완료 시: 유지 / 기립 대기 / 보행 시작
int poseEase = EASE_INOUT; // 보간 곡선
float poseStart[12] = {0};
float poseTarget[12] = {0};
unsigned long poseStartMs = 0;
int poseDurationMs = 100;
// 현재 GoalAngle이 스탠드(기립) 자세인지. false면 보행 시작 전 진입 보간을 길게 준다.
bool atStandPose = false;

// Buffers
float linkageBuffer[32] = {0.0};
float GoalAngle[12] = {90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90};
int ServoDirection[12] = {1, -1, -1, 1, 1, -1, -1, 1, 1, -1, -1, 1};
float ServoMiddleAngle[12] = {90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90};
int pin_mapping[12] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12};

// Leg Indices
const int LEG_A_FORE = 0;
const int LEG_A_BACK = 1;
const int LEG_A_WAVE = 2;
const int LEG_B_WAVE = 3;
const int LEG_B_FORE = 4;
const int LEG_B_BACK = 5;
const int LEG_C_FORE = 6;
const int LEG_C_BACK = 7;
const int LEG_C_WAVE = 8;
const int LEG_D_WAVE = 9;
const int LEG_D_FORE = 10;
const int LEG_D_BACK = 11;

// === SC90 Servo UART Functions ===
uint16_t logical_to_pulse(float angle_degrees) {
  int pulse = 500 + ((angle_degrees - 90.0) * (428.0 / 90.0));
  if (pulse < 0)
    pulse = 0;
  if (pulse > 4095)
    pulse = 4095;
  return (uint16_t)pulse;
}

float pulse_to_logical(int pulse) {
  return 90.0 + (pulse - 500) * (90.0 / 428.0);
}

void sync_write_sc90_positions(int time_ms) {
  uint16_t spd = (time_ms >= 0 && time_ms <= 2000) ? time_ms : 0;
  uint8_t spd_h = (spd >> 8) & 0xFF;
  uint8_t spd_l = spd & 0xFF;

  uint8_t address = 0x2A;
  uint8_t L = 4;
  uint8_t N = 12;
  uint8_t length = (L + 1) * N + 4;

  uint8_t packet[100];
  int idx = 0;
  packet[idx++] = 0xFF;
  packet[idx++] = 0xFF;
  packet[idx++] = 0xFE;
  packet[idx++] = length;
  packet[idx++] = 0x83;
  packet[idx++] = address;
  packet[idx++] = L;

  uint32_t checksum = 0xFE + length + 0x83 + address + L;

  for (int i = 0; i < 12; i++) {
    uint8_t servo_id = pin_mapping[i];
    uint16_t pos = logical_to_pulse(GoalAngle[i]);
    uint8_t pos_h = (pos >> 8) & 0xFF;
    uint8_t pos_l = pos & 0xFF;

    packet[idx++] = servo_id;
    packet[idx++] = pos_h;
    packet[idx++] = pos_l;
    packet[idx++] = spd_h;
    packet[idx++] = spd_l;

    checksum += servo_id + pos_h + pos_l + spd_h + spd_l;
  }

  packet[idx++] = ~(checksum)&0xFF;

  Serial2.write(packet, idx);
}

// 토크 레지스터(0x28=40): 1=켜기(고정), 0=끄기(해제)
void set_torque(bool on) {
  uint8_t val = on ? 1 : 0;
  for (int i = 0; i < 12; i++) {
    uint8_t servo_id = pin_mapping[i];
    uint8_t chk = ~(servo_id + 4 + 3 + 0x28 + val) & 0xFF;
    uint8_t pkt[] = {0xFF, 0xFF, servo_id, 4, 3, 0x28, val, chk};
    Serial2.write(pkt, 8);
    delay(3);
  }
  torqueOn = on;
}

// ---- 요청/응답형 서보 명령 (핑, 위치 읽기) ----
// 주의: Serial2.flush()는 쓰지 않는다. ESP32 코어의 flush()는 송신 완료를 기다린 뒤
// 수신 버퍼까지 비우기 때문에(flush(false) -> uart_flush_input), 요청 직후 바로 도착하는
// 서보 응답의 앞부분이 지워져 핑/위치 읽기가 전부 실패한다.
//
// 에코 보드: 일부 드라이버 보드는 ESP32가 보낸 바이트가 RX로 그대로 되돌아온다.
// 부팅 시 자동 감지해 두고(busEcho), 에코 보드면 요청 직후 보낸 바이트 수만큼 먼저
// 버린 뒤 응답을 읽는다. 응답 바이트 내용으로 에코를 구분하지 않는다 — 서보가 오류
// 비트를 켠 채 핑에 응답하면 요청과 똑같은 바이트열이 되어 정상 응답을 버리게 된다.
bool busEcho = false;
uint8_t rxDbg[24]; // 마지막 응답 대기에서 받은 바이트 (핑 실패 진단용)
int rxDbgLen = 0;

void bus_drain() {
  while (Serial2.available())
    Serial2.read();
}

// 에코 감지: 존재하지 않는 ID(253)에 핑을 보내 요청 바이트가 그대로 돌아오는지 본다
void detect_bus_echo() {
  const uint8_t id = 253;
  uint8_t pkt[] = {0xFF, 0xFF, id, 2, 1, (uint8_t)(~(id + 2 + 1) & 0xFF)};
  int hits = 0;
  for (int attempt = 0; attempt < 2; attempt++) {
    bus_drain();
    Serial2.write(pkt, 6);
    unsigned long t = millis();
    int got = 0;
    bool same = true;
    while (got < 6 && millis() - t < 20) {
      if (Serial2.available()) {
        uint8_t b = Serial2.read();
        if (b != pkt[got])
          same = false;
        got++;
      }
    }
    if (got == 6 && same)
      hits++;
    delay(5);
    bus_drain();
  }
  busEcho = (hits == 2);
}

// 요청 패킷 송신. 에코 보드면 되돌아온 요청 바이트를 먼저 버린다 (서보 응답은 그 뒤에 온다)
void servo_tx(const uint8_t *pkt, int len) {
  bus_drain(); // 이전 잔여 수신(ACK 등) 비우기
  Serial2.write(pkt, len);
  if (busEcho) {
    unsigned long t = millis();
    int skipped = 0;
    while (skipped < len && millis() - t < 5) {
      if (Serial2.available()) {
        Serial2.read();
        skipped++;
      }
    }
  }
  rxDbgLen = 0;
}

// 서보 응답 프레임 1개 수신: FF FF ID LEN ERR [param...] CHK
// paramLen: 기대 파라미터 바이트 수 (핑=0, 2바이트 읽기=2). params에 복사한다.
// ID/길이/체크섬이 맞지 않는 프레임은 버리고 계속 스캔한다.
bool servo_read_reply(uint8_t id, uint8_t paramLen, uint8_t *params,
                      unsigned long timeoutMs) {
  const int frameLen = 6 + paramLen;
  uint8_t frame[16];
  int got = 0;
  unsigned long t = millis();
  while (millis() - t < timeoutMs) {
    if (!Serial2.available())
      continue;
    uint8_t b = Serial2.read();
    if (rxDbgLen < (int)sizeof(rxDbg))
      rxDbg[rxDbgLen++] = b;
    if (got < 2) { // 헤더 FF FF 탐색
      if (b == 0xFF)
        frame[got++] = b;
      else
        got = 0;
      continue;
    }
    if (got == 2 && b == 0xFF)
      continue; // FF가 3개 이상 연속: 마지막 두 개를 헤더로 본다
    frame[got++] = b;
    if (got == 4 && (frame[2] != id || frame[3] != paramLen + 2)) {
      got = 0; // 다른 ID/길이의 프레임: 처음부터 다시
      continue;
    }
    if (got < frameLen)
      continue;
    uint8_t sum = 0;
    for (int i = 2; i < frameLen - 1; i++)
      sum += frame[i];
    if ((uint8_t)(~sum) == frame[frameLen - 1]) {
      if (params && paramLen)
        memcpy(params, frame + 5, paramLen);
      return true;
    }
    got = 0; // 체크섬 불일치: 다시 스캔
  }
  return false;
}

// 진단용: 마지막 응답 대기에서 받은 바이트를 16진수 문자열로
String rx_debug_hex() {
  String s = "";
  for (int i = 0; i < rxDbgLen; i++) {
    if (i)
      s += " ";
    if (rxDbg[i] < 16)
      s += "0";
    s += String(rxDbg[i], HEX);
  }
  return s;
}

// 서보 1개의 현재 실측 위치(펄스) 읽기 (레지스터 0x38, 2바이트). 실패 시 -1
int read_present_pulse(uint8_t id) {
  uint8_t chk = ~(id + 4 + 2 + 0x38 + 2) & 0xFF;
  uint8_t pkt[] = {0xFF, 0xFF, id, 4, 2, 0x38, 2, chk};
  for (int attempt = 0; attempt < 2; attempt++) { // 1회 재시도
    servo_tx(pkt, 8);
    uint8_t pos[2];
    if (servo_read_reply(id, 2, pos, 30)) {
      int pulse = ((int)pos[0] << 8) | pos[1];
      if (pulse >= 0 && pulse <= 4095)
        return pulse;
    }
  }
  return -1;
}

// 서보 핑. 응답 프레임(FF FF ID 02 ERR CHK)의 ID/길이/체크섬까지 검증한다.
bool ping_servo(uint8_t id) {
  uint8_t pkt[] = {0xFF, 0xFF, id, 2, 1, (uint8_t)(~(id + 2 + 1) & 0xFF)};
  servo_tx(pkt, 6);
  return servo_read_reply(id, 0, NULL, 50);
}

// 서보 버스 수신 경로 자가진단: UART2를 내부 루프백(TX->RX)으로 두고 핑 패킷을 보낸다.
// 핑 요청 프레임(FF FF ID 02 01 CHK)은 형식상 핑 응답과 같으므로(LEN=2, 체크섬 일치)
// 수신 드라이버와 파서가 정상이면 OK가 나와야 한다. 하드웨어 배선과 무관하게 동작한다.
bool bus_loopback_selftest() {
  bool savedEcho = busEcho;
  busEcho = false; // 루프백 바이트를 에코로 버리지 않도록
  uart_set_loop_back(UART_NUM_2, true);
  delay(2);
  const uint8_t id = 7;
  uint8_t pkt[] = {0xFF, 0xFF, id, 2, 1, (uint8_t)(~(id + 2 + 1) & 0xFF)};
  servo_tx(pkt, 6);
  bool ok = servo_read_reply(id, 0, NULL, 20);
  uart_set_loop_back(UART_NUM_2, false);
  busEcho = savedEcho;
  delay(2);
  bus_drain();
  return ok;
}

// GoalAngle을 서보 실측 위치로 동기화 (토크 켤 때 튀는 현상 방지)
void sync_goal_to_present() {
  for (int i = 0; i < 12; i++) {
    int pulse = read_present_pulse(pin_mapping[i]);
    if (pulse >= 0) {
      GoalAngle[i] = constrain(pulse_to_logical(pulse), 0, 180);
    }
  }
  atStandPose = false; // 실측 자세는 임의 자세로 본다 -> 보행 전 긴 진입 보간
}

// 토크가 꺼져 있으면 실측 자세를 목표로 동기화한 뒤 켠다
void ensure_torque() {
  if (!torqueOn) {
    sync_goal_to_present();
    set_torque(true);
  }
}

void release_torque() {
  set_torque(false);
  poseMode = false;
  moveFB = 0;
  moveLR = 0;
  // 토크 해제 상태에서 로봇 제어 루프가 기립 목표각을 써서
  // GoalAngle이 실제 자세와 어긋나는 것을 방지 (대기 상태로 고정)
  STAND_STILL = 1;
  atStandPose = false; // 손으로 자세가 바뀔 수 있음
}

// === IK Core Math (WAVEGO 원본 그대로) ===
void simple_linkage_ik(float LA, float LB, float aIn, float bIn, int alphaIdx,
                       int betaIdx, int deltaIdx) {
  float alpha = 0, beta = 0, delta = 0;
  if (bIn == 0) {
    if (LAx2 * aIn == 0)
      return;
    float psi_arg = (LAxLA_LBxLB + aIn * aIn) / (LAx2 * aIn);
    psi_arg = constrain(psi_arg, -1.0, 1.0);
    float psi = acos(psi_arg) * E_PI;
    alpha = 90 - psi;

    if (LBx2 * aIn == 0)
      return;
    float omega_arg = (aIn * aIn + LBxLB_LAxLA) / (LBx2 * aIn);
    omega_arg = constrain(omega_arg, -1.0, 1.0);
    float omega = acos(omega_arg) * E_PI;
    beta = psi + omega;
  } else {
    float L2C = aIn * aIn + bIn * bIn;
    float LC = sqrt(L2C);
    float lambda_val = atan(bIn / aIn) * E_PI;

    if (2 * LA * LC == 0)
      return;
    float psi_arg = (LAxLA_LBxLB + L2C) / (2 * LA * LC);
    psi_arg = constrain(psi_arg, -1.0, 1.0);
    float psi = acos(psi_arg) * E_PI;
    alpha = 90 - lambda_val - psi;

    if (2 * LC * LB == 0)
      return;
    float omega_arg = (LBxLB_LAxLA + L2C) / (2 * LC * LB);
    omega_arg = constrain(omega_arg, -1.0, 1.0);
    float omega = acos(omega_arg) * E_PI;
    beta = psi + omega;
  }
  delta = 90 - alpha - beta;
  linkageBuffer[alphaIdx] = alpha;
  linkageBuffer[betaIdx] = beta;
  linkageBuffer[deltaIdx] = delta;
}

void wiggle_plane_ik(float LA, float aIn, float bIn, int alphaIdx, int lenIdx) {
  float alpha = 0;
  float LB = 0;
  if (bIn > 0) {
    float L2C = aIn * aIn + bIn * bIn;
    float LC = sqrt(L2C);
    float lambda_val = atan(aIn / bIn) * E_PI;

    if (LC == 0)
      return;
    float psi_arg = LA / LC;
    psi_arg = constrain(psi_arg, -1.0, 1.0);
    float psi = acos(psi_arg) * E_PI;

    LB = sqrt(max(0.0f, L2C - LWxLW));
    alpha = psi + lambda_val - 90;
  } else if (bIn == 0) {
    if (aIn == 0)
      return;
    float alpha_arg = LA / aIn;
    alpha_arg = constrain(alpha_arg, -1.0, 1.0);
    alpha = asin(alpha_arg) * E_PI;
    float L2C = aIn * aIn + bIn * bIn;
    LB = sqrt(L2C);
  } else {
    bIn = -bIn;
    float L2C = aIn * aIn + bIn * bIn;
    float LC = sqrt(L2C);
    float lambda_val = atan(aIn / bIn) * E_PI;

    if (LC == 0)
      return;
    float psi_arg = LA / LC;
    psi_arg = constrain(psi_arg, -1.0, 1.0);
    float psi = acos(psi_arg) * E_PI;

    LB = sqrt(max(0.0f, L2C - LWxLW));
    alpha = 90 - lambda_val + psi;
  }
  linkageBuffer[alphaIdx] = alpha;
  linkageBuffer[lenIdx] = LB - wiggleError;
}

void single_leg_plane_ik(float LS, float LA, float LC, float LD, float LE,
                         float xIn, float yIn, int betaIdx, int xIdx,
                         int yIdx) {
  float bufferS_sq = (xIn + LSs2) * (xIn + LSs2) + yIn * yIn;
  float bufferS = sqrt(bufferS_sq);

  if (2 * bufferS * LA == 0)
    return;
  float lambda_arg = (bufferS_sq + LAxLA - L_CD - LExLE) / (2 * bufferS * LA);
  lambda_arg = constrain(lambda_arg, -1.0, 1.0);
  float lambda_val = acos(lambda_arg);

  if (yIn == 0)
    return;
  float delta = atan((xIn + LSs2) / yIn);
  float beta = lambda_val - delta;
  float beta_angle = beta * E_PI;

  float theta = aLCDE;

  if (sLEDC == 0)
    return;
  float omega_arg = (yIn - cos(beta) * LA) / sLEDC;
  omega_arg = constrain(omega_arg, -1.0, 1.0);
  float omega = asin(omega_arg);

  float nu = PI - theta - omega;
  float dFX = cos(nu) * LE;
  float dFY = sin(nu) * LE;

  float mu = PI / 2.0 - nu;
  float dEX = cos(mu) * LD;
  float dEY = sin(mu) * LD;

  float positionX = xIn + dFX - dEX;
  float positionY = yIn - dFY - dEY;

  linkageBuffer[betaIdx] = beta_angle;
  linkageBuffer[xIdx] = positionX;
  linkageBuffer[yIdx] = positionY;
}

// 다리 1개의 발 좌표 -> 관절 오프셋(영점 대비, ServoDirection 적용 전)과 서보 인덱스.
// 순수 기구학만 담당한다. 어떤 영점에 얹을지는 single_leg_ctrl이 정한다.
// 잘못된 다리 번호면 false.
bool leg_joint_offsets(int LegNum, float xPos, float yPos, float zPos, int &NumF,
                       int &NumB, int &NumW, float &offF, float &offB,
                       float &offW) {
  int alphaOut, xPosBuffer, yPosBuffer, betaOut, wiggleAlpha, wiggleLen;

  if (LegNum == 1) {
    NumF = LEG_A_FORE;
    NumB = LEG_A_BACK;
    NumW = LEG_A_WAVE;
    alphaOut = 0;
    xPosBuffer = 1;
    yPosBuffer = 2;
    betaOut = 3;
    wiggleAlpha = 6;
    wiggleLen = 7;
  } else if (LegNum == 2) {
    NumF = LEG_B_FORE;
    NumB = LEG_B_BACK;
    NumW = LEG_B_WAVE;
    alphaOut = 8;
    xPosBuffer = 9;
    yPosBuffer = 10;
    betaOut = 11;
    wiggleAlpha = 14;
    wiggleLen = 15;
  } else if (LegNum == 3) {
    NumF = LEG_C_FORE;
    NumB = LEG_C_BACK;
    NumW = LEG_C_WAVE;
    alphaOut = 16;
    xPosBuffer = 17;
    yPosBuffer = 18;
    betaOut = 19;
    wiggleAlpha = 22;
    wiggleLen = 23;
  } else if (LegNum == 4) {
    NumF = LEG_D_FORE;
    NumB = LEG_D_BACK;
    NumW = LEG_D_WAVE;
    alphaOut = 24;
    xPosBuffer = 25;
    yPosBuffer = 26;
    betaOut = 27;
    wiggleAlpha = 30;
    wiggleLen = 31;
  } else {
    return false;
  }

  int betaB = betaOut + 1;
  int betaC = betaOut + 2;

  wiggle_plane_ik(linkage_w, zPos, yPos, wiggleAlpha, wiggleLen);
  single_leg_plane_ik(linkage_s, linkage_a, linkage_c, linkage_d, linkage_e,
                      xPos, linkageBuffer[wiggleLen], alphaOut, xPosBuffer,
                      yPosBuffer);
  simple_linkage_ik(linkage_a, linkage_b, linkageBuffer[yPosBuffer],
                    (linkageBuffer[xPosBuffer] - linkage_s / 2.0), betaOut,
                    betaB, betaC);

  offW = linkageBuffer[wiggleAlpha];
  offF = 90.0 - linkageBuffer[betaOut];
  offB = linkageBuffer[alphaOut];
  return true;
}

// 기준 자세(발이 앞뒤 0, 지지 높이)에서의 관절 오프셋. 이 값을 빼서 궤적을
// 재중심화하면 "기준 자세 = 캘리브레이션 각도(ServoMiddleAngle)"가 된다.
// init_neutral_offsets() 전에는 0이므로, 호출 전 동작은 기존과 동일하다.
float NeutralOffset[12] = {0};

void init_neutral_offsets() {
  for (int i = 0; i < 12; i++)
    NeutralOffset[i] = 0;
  // 다리 1,3은 +X, 다리 2,4는 -X (stand_mass_center / simple_gait와 동일)
  const float legX[4] = {WALK_EXTENDED_X, -WALK_EXTENDED_X, WALK_EXTENDED_X,
                         -WALK_EXTENDED_X};
  for (int leg = 1; leg <= 4; leg++) {
    int NumF, NumB, NumW;
    float offF, offB, offW;
    if (leg_joint_offsets(leg, legX[leg - 1], WALK_HEIGHT, WALK_EXTENDED_Z,
                          NumF, NumB, NumW, offF, offB, offW)) {
      NeutralOffset[NumW] = offW;
      NeutralOffset[NumF] = offF;
      NeutralOffset[NumB] = offB;
    }
  }
}

// 발 좌표 -> GoalAngle. 캘리브레이션 각도를 기준 자세로 삼아 오프셋만 얹는다.
void single_leg_ctrl(int LegNum, float xPos, float yPos, float zPos) {
  int NumF, NumB, NumW;
  float offF, offB, offW;
  if (!leg_joint_offsets(LegNum, xPos, yPos, zPos, NumF, NumB, NumW, offF, offB,
                         offW))
    return;

  GoalAngle[NumW] =
      constrain(ServoMiddleAngle[NumW] +
                    (offW - NeutralOffset[NumW]) * ServoDirection[NumW],
                0, 180);
  GoalAngle[NumF] =
      constrain(ServoMiddleAngle[NumF] +
                    (offF - NeutralOffset[NumF]) * ServoDirection[NumF],
                0, 180);
  GoalAngle[NumB] =
      constrain(ServoMiddleAngle[NumB] +
                    (offB - NeutralOffset[NumB]) * ServoDirection[NumB],
                0, 180);
}

// 4다리 모두 같은 높이로 (GoalAngle 계산 + 전송)
void stand_up_t(float cmd_input, int time_ms) {
  single_leg_ctrl(1, WALK_EXTENDED_X, cmd_input, WALK_EXTENDED_Z);
  single_leg_ctrl(2, -WALK_EXTENDED_X, cmd_input, WALK_EXTENDED_Z);
  single_leg_ctrl(3, WALK_EXTENDED_X, cmd_input, WALK_EXTENDED_Z);
  single_leg_ctrl(4, -WALK_EXTENDED_X, cmd_input, WALK_EXTENDED_Z);
  sync_write_sc90_positions(time_ms);
}

void stand_up(float cmd_input) { stand_up_t(cmd_input, 5); }

// 스탠드 자세 GoalAngle 계산만 수행 (전송 없음)
void stand_mass_center(float aInput, float bInput) {
  single_leg_ctrl(1, (WALK_EXTENDED_X - aInput), STAND_HEIGHT,
                  (WALK_EXTENDED_Z - bInput));
  single_leg_ctrl(2, (-WALK_EXTENDED_X - aInput), STAND_HEIGHT,
                  (WALK_EXTENDED_Z - bInput));
  single_leg_ctrl(3, (WALK_EXTENDED_X - aInput), STAND_HEIGHT,
                  (WALK_EXTENDED_Z + bInput));
  single_leg_ctrl(4, (-WALK_EXTENDED_X - aInput), STAND_HEIGHT,
                  (WALK_EXTENDED_Z + bInput));
}

// ============================================================================
// 보행 (Gait)
// - 사이클의 75%: 지지구간 (발이 지면을 밀며 뒤로 이동, 다리 길이 일정)
// - 사이클의 25%: 스윙구간 (발을 사인 곡선으로 들어올려 앞으로 복귀)
// - 구간 경계에서 다리 길이가 연속이 되도록 수정됨 (기존: 9mm 불연속 점프)
// ============================================================================
void single_gait_ctrl(int LegNum, float statusInput, float cycleInput,
                      float directionInput, float extendedX, float extendedZ) {
  float rDist = 0;
  float yGait = 0;
  float rDirection = directionInput * PI / 180.0;

  if (cycleInput < (1.0 - WALK_LIFT_PROP)) {
    // 지지구간: 발을 지면에 붙인 채 뒤로 (다리 길이 일정 -> 몸이 안정적으로 전진)
    float cycle_prop = cycleInput / (1.0 - WALK_LIFT_PROP);
    rDist =
        (WALK_RANGE * statusInput / 2.0 + WALK_ACC) * (1.0 - 2.0 * cycle_prop);
    yGait = WALK_HEIGHT;
  } else {
    // 스윙구간: 발을 들어올려(sin 리프트) 앞으로 복귀. 경계에서 yGait 연속.
    float cycle_prop = (cycleInput - (1.0 - WALK_LIFT_PROP)) / WALK_LIFT_PROP;
    yGait = WALK_HEIGHT - WALK_LIFT * sin(cycle_prop * PI);
    rDist = -(WALK_RANGE * statusInput / 2.0 + WALK_ACC) +
            (WALK_RANGE * statusInput + WALK_ACC * 2.0) * cycle_prop;
  }

  float xGait = cos(rDirection) * rDist;
  float zGait = sin(rDirection) * rDist;
  single_leg_ctrl(LegNum, (xGait + extendedX), yGait, (zGait + extendedZ));
}

void simple_gait(float GlobalInput, float directionAngle, int turnCmd) {
  float Group_A = GlobalInput;
  float Group_B = GlobalInput + 0.5;
  if (Group_B > 1.0)
    Group_B -= 1.0;

  if (turnCmd == 0) {
    single_gait_ctrl(1, 1, Group_A, directionAngle, WALK_EXTENDED_X,
                     WALK_EXTENDED_Z);
    single_gait_ctrl(4, 1, Group_A, -directionAngle, -WALK_EXTENDED_X,
                     WALK_EXTENDED_Z);
    single_gait_ctrl(2, 1, Group_B, directionAngle, -WALK_EXTENDED_X,
                     WALK_EXTENDED_Z);
    single_gait_ctrl(3, 1, Group_B, -directionAngle, WALK_EXTENDED_X,
                     WALK_EXTENDED_Z);
  } else if (turnCmd == -1) {
    single_gait_ctrl(1, 1.5, Group_A, 90, WALK_EXTENDED_X, WALK_EXTENDED_Z);
    single_gait_ctrl(4, 1.5, Group_A, 90, -WALK_EXTENDED_X, WALK_EXTENDED_Z);
    single_gait_ctrl(2, 1.5, Group_B, -90, -WALK_EXTENDED_X, WALK_EXTENDED_Z);
    single_gait_ctrl(3, 1.5, Group_B, -90, WALK_EXTENDED_X, WALK_EXTENDED_Z);
  } else if (turnCmd == 1) {
    single_gait_ctrl(1, 1.5, Group_A, -90, WALK_EXTENDED_X, WALK_EXTENDED_Z);
    single_gait_ctrl(4, 1.5, Group_A, -90, -WALK_EXTENDED_X, WALK_EXTENDED_Z);
    single_gait_ctrl(2, 1.5, Group_B, 90, -WALK_EXTENDED_X, WALK_EXTENDED_Z);
    single_gait_ctrl(3, 1.5, Group_B, 90, WALK_EXTENDED_X, WALK_EXTENDED_Z);
  }
}

// ============================================================================
// 포즈 보간 엔진 (동작 재생 / 부드러운 자세 전환)
// ============================================================================
float bessel_ctrl(float num_start, float num_end, float rate_input) {
  return (num_end - num_start) * ((cos(rate_input * PI - PI) + 1.0) / 2.0) +
         num_start;
}

// 보간 곡선: 진행률 t(0~1) -> 보정된 진행률
//   EASE_INOUT : 코사인(양끝 속도 0). 단발 자세 전환용
//   EASE_LINEAR: 등속. 키프레임이 연속되는 동작(걷기 등)의 중간 구간용
//   EASE_IN/OUT: 시작만/끝만 감속. 연속 동작의 첫/마지막 구간용
float ease_rate(float t, int mode) {
  if (t <= 0.0f)
    return 0.0f;
  if (t >= 1.0f)
    return 1.0f;
  switch (mode) {
  case EASE_LINEAR:
    return t;
  case EASE_IN:
    return 1.0f - cos(t * PI / 2.0);
  case EASE_OUT:
    return sin(t * PI / 2.0);
  default:
    return (1.0f - cos(t * PI)) / 2.0f;
  }
}

// 현재 GoalAngle에서 target까지 ms 동안 보간 시작 (5ms 루프가 수행)
void begin_pose(const float target[12], int ms, int exitMode, int easeMode) {
  ensure_torque(); // 토크가 꺼져 있었다면 실측 자세를 시작점으로 동기화
  for (int i = 0; i < 12; i++) {
    poseStart[i] = GoalAngle[i];
    poseTarget[i] = constrain(target[i], 0, 180);
  }
  poseDurationMs = max(ms, 20);
  poseStartMs = millis();
  poseMode = true;
  poseDone = false;
  poseExit = exitMode;
  poseEase = easeMode;
  atStandPose = false; // POSE_TO_IDLE로 완료되면 true로 복구된다
}

// 현재 자세 -> 스탠드 자세로 부드럽게 전환
void begin_pose_to_stand(int ms, int exitMode) {
  float backup[12];
  memcpy(backup, GoalAngle, sizeof(backup));
  stand_mass_center(0, 0); // GoalAngle = 스탠드 자세 (전송 없음)
  float target[12];
  memcpy(target, GoalAngle, sizeof(target));
  memcpy(GoalAngle, backup, sizeof(backup)); // 현재 자세 복원
  begin_pose(target, ms, exitMode, EASE_INOUT);
}

// 현재 이동 명령(moveFB/moveLR) -> 보행 방향각 / 제자리 회전 명령
void gait_cmd_from_move(float &direction, int &turn) {
  direction = 0;
  turn = 0;
  if (moveFB == 1 && moveLR == 0)
    direction = 0;
  else if (moveFB == -1 && moveLR == 0)
    direction = 180;
  else if (moveFB == 1 && moveLR == -1)
    direction = 30;
  else if (moveFB == 1 && moveLR == 1)
    direction = -30;
  else if (moveFB == -1 && moveLR == 1)
    direction = -120;
  else if (moveFB == -1 && moveLR == -1)
    direction = 120;
  else if (moveFB == 0 && moveLR == -1)
    turn = -1;
  else if (moveFB == 0 && moveLR == 1)
    turn = 1;
}

// 현재 자세 -> 보행 사이클 시작 자세(GLOBAL_STEP=0)로 부드럽게 진입.
// 정지 상태에서 바로 보행을 시작하면 첫 틱에 발이 25mm가량 튀므로 이 진입을 거친다.
void begin_pose_to_gait(int ms) {
  float direction;
  int turn;
  gait_cmd_from_move(direction, turn);
  float backup[12];
  memcpy(backup, GoalAngle, sizeof(backup));
  simple_gait(0.0, direction, turn); // GoalAngle = 보행 시작 자세 (전송 없음)
  float target[12];
  memcpy(target, GoalAngle, sizeof(target));
  memcpy(GoalAngle, backup, sizeof(backup)); // 현재 자세 복원
  begin_pose(target, ms, POSE_TO_GAIT, EASE_INOUT);
}

// 블로킹 방식 부드러운 이동 (특수 기능 F1~F3 내부 전용)
void blocking_move_to(const float target[12], int ms) {
  float start[12];
  memcpy(start, GoalAngle, sizeof(start));
  int steps = max(ms / 5, 1);
  for (int s = 1; s <= steps; s++) {
    float rate = (float)s / steps;
    for (int i = 0; i < 12; i++) {
      GoalAngle[i] = bessel_ctrl(start[i], constrain(target[i], 0, 180), rate);
    }
    sync_write_sc90_positions(5);
    delay(5);
  }
}

// 블로킹 방식으로 스탠드 자세까지 이동 (특수 기능 시작 시 자세 정렬용)
void blocking_stand(int ms) {
  float backup[12];
  memcpy(backup, GoalAngle, sizeof(backup));
  stand_mass_center(0, 0);
  float target[12];
  memcpy(target, GoalAngle, sizeof(target));
  memcpy(GoalAngle, backup, sizeof(backup));
  blocking_move_to(target, ms);
}

// ============================================================================
// 메인 제어 루프 (5ms 주기)
// ============================================================================
void robot_ctrl() {
  // 1) 포즈 보간: 동작 재생, 기립/보행 진입 전환, 캘리브레이션 진입 전환
  //    (캘리브레이션 유지보다 먼저 검사해야 진입 전환이 부드럽게 끝난다)
  if (poseMode) {
    float t = (float)(millis() - poseStartMs) / (float)poseDurationMs;
    if (t >= 1.0f)
      t = 1.0f;
    if (!poseDone) {
      float r = ease_rate(t, poseEase);
      for (int i = 0; i < 12; i++) {
        GoalAngle[i] = poseStart[i] + (poseTarget[i] - poseStart[i]) * r;
      }
      sync_write_sc90_positions(5);
      if (t >= 1.0f) {
        poseDone = true;
        if (poseExit == POSE_TO_IDLE) {
          poseMode = false;
          STAND_STILL = 1;
          GLOBAL_STEP = 0;
          atStandPose = true;
        } else if (poseExit == POSE_TO_GAIT) {
          poseMode = false;
          STAND_STILL = 0;
          GLOBAL_STEP = 0; // 진입 자세 = 사이클 0 자세 -> 끊김 없이 보행 계속
        }
        // POSE_HOLD: 완료 자세를 유지 (다음 J/K/M/F 명령까지)
      }
    }
    return; // 포즈 중에는 보행 억제
  }

  // 2) 캘리브레이션: 현재 중간각으로 스탠드 자세를 계속 유지 (A 변경 즉시 반영)
  if (calibrationMode) {
    stand_mass_center(0, 0);
    sync_write_sc90_positions(0);
    return;
  }

  // 3) 보행 / 정지
  if (moveFB == 0 && moveLR == 0) {
    if (STAND_STILL == 0) {
      // 보행 중 정지: 스탠드 자세로 부드럽게 (기존: 5ms 속도로 즉시 스냅 -> "쿵")
      STAND_STILL = 1;
      begin_pose_to_stand(200, POSE_TO_IDLE);
    }
    return;
  }

  if (STAND_STILL == 1) {
    // 정지 상태에서 보행 시작: 먼저 보행 시작 자세로 부드럽게 진입.
    // 기립 자세면 짧게, 임의 자세(토크 해제 후 / 동작 재생 후)면 길게.
    begin_pose_to_gait(atStandPose ? 150 : 400);
    return;
  }

  if (GLOBAL_STEP > 1)
    GLOBAL_STEP = 0;
  float direction;
  int turn;
  gait_cmd_from_move(direction, turn);
  simple_gait(GLOBAL_STEP, direction, turn);
  sync_write_sc90_positions(5);
  GLOBAL_STEP += STEP_ITERATE;
}

// ============================================================================
// 특수 기능 (블로킹 시퀀스)
// ============================================================================
void function_stay_low() {
  funcMode = 1;
  ensure_torque();
  blocking_stand(400);
  for (int i = 0; i <= 50; i++) {
    stand_up(bessel_ctrl(WALK_HEIGHT, WALK_HEIGHT_MIN, i / 50.0));
    delay(6);
  }
  delay(300);
  for (int i = 0; i <= 50; i++) {
    stand_up(bessel_ctrl(WALK_HEIGHT_MIN, WALK_HEIGHT_MAX, i / 50.0));
    delay(6);
  }
  for (int i = 0; i <= 50; i++) {
    stand_up(bessel_ctrl(WALK_HEIGHT_MAX, WALK_HEIGHT, i / 50.0));
    delay(6);
  }
  funcMode = 0;
  poseMode = false;
  STAND_STILL = 1;
  atStandPose = true; // 스탠드 높이로 끝남
}

// 악수: 자세를 낮춰 안정화 후 앞오른다리(Leg 2)를 들어 위아래로 흔든다
void function_handshake() {
  funcMode = 1;
  ensure_torque();
  blocking_stand(400);

  const float crouch = 82.0; // 3다리 지지 안정성을 위해 살짝 웅크림
  for (int i = 0; i <= 40; i++) {
    stand_up(bessel_ctrl(WALK_HEIGHT, crouch, i / 40.0));
    delay(6);
  }

  // 앞오른다리 들어올리기 (앞으로 + 위로)
  for (int i = 0; i <= 40; i++) {
    float rate = i / 40.0;
    single_leg_ctrl(2, bessel_ctrl(-WALK_EXTENDED_X, 25.0, rate),
                    bessel_ctrl(crouch, 45.0, rate), WALK_EXTENDED_Z);
    sync_write_sc90_positions(5);
    delay(6);
  }

  // 위아래로 3회 흔들기
  for (int k = 0; k < 3; k++) {
    for (int i = 0; i <= 25; i++) {
      single_leg_ctrl(2, 25.0, bessel_ctrl(45.0, 60.0, i / 25.0),
                      WALK_EXTENDED_Z);
      sync_write_sc90_positions(5);
      delay(6);
    }
    for (int i = 0; i <= 25; i++) {
      single_leg_ctrl(2, 25.0, bessel_ctrl(60.0, 45.0, i / 25.0),
                      WALK_EXTENDED_Z);
      sync_write_sc90_positions(5);
      delay(6);
    }
  }

  // 다리 내리고 복귀
  for (int i = 0; i <= 40; i++) {
    float rate = i / 40.0;
    single_leg_ctrl(2, bessel_ctrl(25.0, -WALK_EXTENDED_X, rate),
                    bessel_ctrl(45.0, crouch, rate), WALK_EXTENDED_Z);
    sync_write_sc90_positions(5);
    delay(6);
  }
  for (int i = 0; i <= 40; i++) {
    stand_up(bessel_ctrl(crouch, WALK_HEIGHT, i / 40.0));
    delay(6);
  }

  funcMode = 0;
  poseMode = false;
  STAND_STILL = 1;
  atStandPose = true; // 스탠드 높이로 끝남
}

// 점프: 웅크렸다가 최대 속도로 다리를 펴서 도약 후 착지 복귀
void function_jump() {
  funcMode = 1;
  ensure_torque();
  blocking_stand(300);

  // 1) 천천히 웅크리기
  for (int i = 0; i <= 50; i++) {
    stand_up(bessel_ctrl(WALK_HEIGHT, WALK_HEIGHT_MIN, i / 50.0));
    delay(6);
  }
  delay(150);

  // 2) 점프! (time=0 -> 서보 최대 속도로 다리 폄)
  stand_up_t(WALK_HEIGHT_MAX, 0);
  delay(250);

  // 3) 착지 후 스탠드 높이로 복귀
  for (int i = 0; i <= 40; i++) {
    stand_up(bessel_ctrl(WALK_HEIGHT_MAX, WALK_HEIGHT, i / 40.0));
    delay(6);
  }

  funcMode = 0;
  poseMode = false;
  STAND_STILL = 1;
  atStandPose = true; // 스탠드 높이로 끝남
}

// ============================================================================
// 커맨드 파서
// ============================================================================

// "X v0 v1 v2 ..." 에서 실수 값들을 파싱. 파싱한 개수 반환
int parse_floats(const String &cmd, float *out, int maxCount) {
  int idx = 1;
  int count = 0;
  int len = cmd.length();
  while (count < maxCount && idx < len) {
    while (idx < len && cmd.charAt(idx) == ' ')
      idx++;
    if (idx >= len)
      break;
    int nextSpace = cmd.indexOf(' ', idx);
    if (nextSpace == -1)
      nextSpace = len;
    out[count++] = cmd.substring(idx, nextSpace).toFloat();
    idx = nextSpace + 1;
  }
  return count;
}

void parseCommand(String cmd) {
  cmd.trim();
  if (cmd.length() == 0)
    return;

  lastCmdMillis = millis(); // 워치독 갱신 (모든 커맨드 공통)

  char type = cmd.charAt(0);

  if (type == 'H') {
    // 하트비트: 워치독 갱신 외 아무것도 하지 않음
    return;
  } else if (type == 'S') {
    float speedVal = cmd.substring(2).toFloat();
    // 상한 0.02: 서보가 감당 못하는 과속 방지 (기존 0.1의 절반 이하로 제한)
    if (speedVal > 0.0001 && speedVal <= 0.02) {
      STEP_ITERATE = speedVal;
    }
  } else if (type == 'M') {
    int firstSpace = cmd.indexOf(' ');
    int secondSpace = cmd.indexOf(' ', firstSpace + 1);
    if (firstSpace > 0 && secondSpace > 0) {
      moveFB = constrain(cmd.substring(firstSpace + 1, secondSpace).toInt(), -1, 1);
      moveLR = constrain(cmd.substring(secondSpace + 1).toInt(), -1, 1);
      if (moveFB != 0 || moveLR != 0) {
        ensure_torque(); // 꺼져 있었다면 실측 자세 동기화 (atStandPose=false)
        if (poseMode) {
          if (poseExit == POSE_HOLD) {
            // 동작 재생/부분 포즈 중(또는 완료 후 유지 중): 포즈를 끝내고 정지
            // 상태로 두면 제어 루프가 현재 자세에서 보행 진입 보간(400ms)을 시작한다
            poseMode = false;
            STAND_STILL = 1;
          } else if (poseExit == POSE_TO_GAIT) {
            begin_pose_to_gait(150); // 진입 도중 방향이 바뀜: 새 시작 자세로
          }
          // POSE_TO_IDLE(기립 전환) 진행 중이면 완료 후 자동으로 보행 진입
        }
        // poseMode가 아니면 제어 루프가 atStandPose에 따라 150/400ms 진입 보간을
        // 수행한다 -> 토크 해제 후 임의 자세에서 걸어도 튀지 않음
      } else if (poseMode && poseExit == POSE_TO_GAIT) {
        begin_pose_to_stand(200, POSE_TO_IDLE); // 보행 진입 도중 키를 뗌
      }
    }
  } else if (type == 'J') {
    // J <ms> <a0..a11> [mode] : 포즈(동작 키프레임) 명령
    // mode: 0=코사인(기본, 생략 가능) 1=선형 2=ease-in 3=ease-out
    float vals[14];
    int n = parse_floats(cmd, vals, 14);
    if (n == 13 || n == 14) {
      moveFB = 0;
      moveLR = 0;
      calibrationMode = false; // 포즈 명령이 오면 캘리브레이션 유지는 끝난 것
      int ms = (int)vals[0];
      int mode = (n == 14) ? constrain((int)vals[13], 0, 3) : (int)EASE_INOUT;
      float target[12];
      for (int i = 0; i < 12; i++)
        target[i] = vals[i + 1];
      begin_pose(target, ms, POSE_HOLD, mode);
    }
  } else if (type == 'K') {
    // K <ms> <idx> <angle> [<idx> <angle> ...] : 부분 포즈 명령
    // 지정한 서보(들)만 목표 각도로 이동하고, 나머지는 현재 위치를 유지한다.
    // (동작 편집에서 슬라이더 하나를 움직였을 때 그 서보만 움직이게 하기 위함)
    float vals[25]; // ms + 최대 12쌍
    int n = parse_floats(cmd, vals, 25);
    if (n >= 3 && (n % 2) == 1) {
      moveFB = 0;
      moveLR = 0;
      calibrationMode = false;
      ensure_torque(); // 토크가 꺼져 있었다면 실측 자세를 먼저 동기화
      float target[12];
      for (int i = 0; i < 12; i++)
        target[i] = GoalAngle[i]; // 기본: 전부 현재 위치 유지
      for (int p = 1; p + 1 < n; p += 2) {
        int idx = (int)vals[p];
        if (idx >= 0 && idx < 12)
          target[idx] = vals[p + 1];
      }
      begin_pose(target, (int)vals[0], POSE_HOLD, EASE_INOUT);
    }
  } else if (type == 'C') {
    int val = cmd.substring(2).toInt();
    calibrationMode = (val == 1);
    moveFB = 0;
    moveLR = 0;
    // 진입/종료 모두 스탠드 자세로 부드럽게 전환한다 (기존 진입은 최대 속도 스냅).
    // 진입 시 전환이 끝나면 제어 루프가 캘리브레이션 유지(중간각 즉시 반영)를 시작.
    begin_pose_to_stand(500, POSE_TO_IDLE);
  } else if (type == 'F') {
    int func_id = cmd.substring(2).toInt();
    if (func_id == 1)
      function_stay_low();
    else if (func_id == 2)
      function_handshake();
    else if (func_id == 3)
      function_jump();
    else if (func_id == 4) {
      funcMode = 0;
      moveFB = 0;
      moveLR = 0;
      begin_pose_to_stand(500, POSE_TO_IDLE); // begin_pose가 토크를 보장한다
    }
  } else if (type == 'T') {
    release_torque();
  } else if (type == 'E') {
    ensure_torque(); // 꺼져 있었다면 실측 자세 동기화 후 켠다
    poseMode = false;
    moveFB = 0;
    moveLR = 0;
    STAND_STILL = 1; // 현재 자세 유지 (다음 보행 시작 시 진입 보간을 거친다)
  } else if (type == 'U') {
    // 서보 실측 각도 12개 응답: "POS a0 a1 ... a11". 응답 없는 서보는 "?"
    // (기존: 마지막 목표각으로 조용히 대체 -> 토크 해제 후 캡처 시 엉뚱한 값이 섞임)
    String reply = "POS";
    for (int i = 0; i < 12; i++) {
      int pulse = read_present_pulse(pin_mapping[i]);
      if (pulse >= 0)
        reply += " " + String(pulse_to_logical(pulse), 1);
      else
        reply += " ?";
    }
    Serial.println(reply);
  } else if (type == 'V') {
    // 현재 목표 각도 12개 응답: "ANG a0 a1 ... a11"
    String reply = "ANG";
    for (int i = 0; i < 12; i++) {
      reply += " " + String(GoalAngle[i], 1);
    }
    Serial.println(reply);
  } else if (type == 'O') {
    // Pins: O p0 p1 ... p11
    float vals[12];
    int n = parse_floats(cmd, vals, 12);
    if (n == 12) {
      for (int i = 0; i < 12; i++)
        pin_mapping[i] = (int)vals[i];
    }
  } else if (type == 'A') {
    // Angles: A a0 a1 ... a11
    float vals[12];
    int n = parse_floats(cmd, vals, 12);
    if (n == 12) {
      for (int i = 0; i < 12; i++)
        ServoMiddleAngle[i] = constrain(vals[i], 0, 180);
    }
    // 캘리브레이션 중이면 제어 루프(5ms)가 새 중간각으로 스탠드 자세를 다시 쓴다
  } else if (type == 'P') {
    int firstSpace = cmd.indexOf(' ');
    int secondSpace = cmd.indexOf(' ', firstSpace + 1);
    if (firstSpace > 0 && secondSpace > 0) {
      int jointId = cmd.substring(firstSpace + 1, secondSpace).toInt();
      int hardwarePin = cmd.substring(secondSpace + 1).toInt();
      if (jointId >= 0 && jointId < 12) {
        pin_mapping[jointId] = hardwarePin;
      }
    }
  } else if (type == 'I') {
    int firstSpace = cmd.indexOf(' ');
    int secondSpace = cmd.indexOf(' ', firstSpace + 1);
    if (firstSpace > 0 && secondSpace > 0) {
      int old_id = cmd.substring(firstSpace + 1, secondSpace).toInt();
      int new_id = cmd.substring(secondSpace + 1).toInt();

      updateOLED("Set ID Cmd", "Old: " + String(old_id),
                 "New: " + String(new_id));

      uint8_t unlock[] = {0xFF,
                          0xFF,
                          (uint8_t)old_id,
                          4,
                          3,
                          48,
                          0,
                          (uint8_t)(~(old_id + 4 + 3 + 48 + 0) & 0xFF)};
      Serial2.write(unlock, 8);
      delay(20);

      uint8_t setid[] = {0xFF,
                         0xFF,
                         (uint8_t)old_id,
                         4,
                         3,
                         5,
                         (uint8_t)new_id,
                         (uint8_t)(~(old_id + 4 + 3 + 5 + new_id) & 0xFF)};
      Serial2.write(setid, 8);
      delay(20);

      uint8_t lock[] = {0xFF,
                        0xFF,
                        (uint8_t)old_id,
                        4,
                        3,
                        48,
                        1,
                        (uint8_t)(~(old_id + 4 + 3 + 48 + 1) & 0xFF)};
      Serial2.write(lock, 8);
      delay(20);
    }
  } else if (type == 'Q') {
    int id = cmd.substring(2).toInt();
    bool replied = (id >= 0 && id <= 253) && ping_servo((uint8_t)id);
    if (replied) {
      updateOLED("Ping ID: " + String(id), "Status:", "OK (Success!)");
      Serial.println("OK");
    } else {
      updateOLED("Ping ID: " + String(id), "Status:", "ERR (Timeout)");
      Serial.println("ERR");
      // 진단: 에코 여부와 실제로 받은 바이트. rx=[]이면 응답이 전혀 없는 것(전원/RX 배선),
      // 정상 프레임이 보이는데 실패면 ID/체크섬 불일치.
      Serial.println("QDBG echo=" + String(busEcho ? 1 : 0) + " rx=[" + rx_debug_hex() + "]");
    }
  } else if (type == 'Z') {
    // 서보 버스 진단: 에코 여부 재감지 -> "ECHO 0/1"
    detect_bus_echo();
    Serial.println("ECHO " + String(busEcho ? 1 : 0));
  } else if (type == 'Y') {
    // 서보 버스 수신 자가진단 (내부 루프백)
    bool ok = bus_loopback_selftest();
    Serial.println(String(ok ? "LOOP OK" : "LOOP FAIL") + " rx=[" + rx_debug_hex() + "]");
  } else if (type == 'L') {
    // L <pwmA> <pwmB>
    int firstSpace = cmd.indexOf(' ');
    int secondSpace = cmd.indexOf(' ', firstSpace + 1);
    if (firstSpace > 0 && secondSpace > 0) {
      int pwmA = cmd.substring(firstSpace + 1, secondSpace).toInt();
      int pwmB = cmd.substring(secondSpace + 1).toInt();
      // TODO: 조명 제어 하드웨어 핀 연동
      updateOLED_buffered(3, "Lights: " + String(pwmA) + " " + String(pwmB));
    }
  } else if (type == 'R') {
    // R <id> <r> <g> <b>
    int sp1 = cmd.indexOf(' ');
    int sp2 = cmd.indexOf(' ', sp1 + 1);
    int sp3 = cmd.indexOf(' ', sp2 + 1);
    int sp4 = cmd.indexOf(' ', sp3 + 1);
    if (sp1 > 0 && sp2 > 0 && sp3 > 0) {
      int id = cmd.substring(sp1 + 1, sp2).toInt();
      int r = cmd.substring(sp2 + 1, sp3).toInt();
      int g = cmd.substring(sp3 + 1, sp4 == -1 ? cmd.length() : sp4).toInt();
      int b = (sp4 == -1) ? 0 : cmd.substring(sp4 + 1).toInt();
      // TODO: RGB 제어 하드웨어 핀 연동
      updateOLED_buffered(3, "RGB " + String(id) + ": " + String(r) + " " +
                                 String(g) + " " + String(b));
    }
  } else if (type == 'D') {
    // D <line> <text>
    int firstSpace = cmd.indexOf(' ');
    int secondSpace = cmd.indexOf(' ', firstSpace + 1);
    if (firstSpace > 0 && secondSpace > 0) {
      int lineNum = cmd.substring(firstSpace + 1, secondSpace).toInt();
      String text = cmd.substring(secondSpace + 1);
      updateOLED_buffered(lineNum, text);
    }
  }
}

// ============================================================================
// setup / loop
// ============================================================================
void setup() {
  Serial.setRxBufferSize(1024); // 블로킹 특수기능(최대 2.5초) 중 수신 누락 방지
  Serial.begin(115200);
  Serial.setTimeout(50); // 개행 없는 부분 수신이 제어 루프를 오래 막지 않도록
  Serial2.begin(1000000, SERIAL_8N1, RXD2, TXD2);
  delay(100);
  init_neutral_offsets(); // 기립/보행의 중앙을 캘리브레이션 각도에 맞추기 위한 기준값
  detect_bus_echo(); // 드라이버 보드 에코 여부 자동 감지 (핑/위치 읽기 파서가 사용)

  // 토크 활성화 (모터 고정)
  set_torque(true);
  delay(50);
  // 부팅 시 실제 서보 자세를 목표각으로 동기화 (첫 이동에서 튀는 현상 방지)
  sync_goal_to_present();

  Wire.begin(21, 22);
  Wire.setClock(400000); // OLED 갱신이 제어 루프를 방해하지 않도록 고속 I2C
  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("SSD1306 allocation failed");
  }

  updateOLED("Robot Dog Ready", "Serial 115200", "Motion FW v3");

  lastCmdMillis = millis();
  Serial.println("FIRMWARE_VER: RX=18, TX=19, MOTION_V3, ECHO=" + String(busEcho ? 1 : 0));
}

void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    parseCommand(cmd);
  }

  // 워치독: 보행 중 통신이 끊기면 자동 정지
  if ((moveFB != 0 || moveLR != 0) &&
      (millis() - lastCmdMillis > WATCHDOG_TIMEOUT_MS)) {
    moveFB = 0;
    moveLR = 0;
  }

  if (!funcMode) {
    unsigned long currentMillis = millis();
    if (currentMillis - lastStepMillis >= 5) {
      lastStepMillis = currentMillis;
      robot_ctrl();
    }
  }
}
