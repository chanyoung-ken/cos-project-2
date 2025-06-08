# 엣지 컴퓨팅 기반 분산 AI 시스템

> EL 1001 Term Project - 에너지 모니터링을 위한 분산 AI 예측 시스템

## 📋 프로젝트 개요

이 프로젝트는 **엣지 디바이스 → 서버 → AI 모듈**의 3-tier 아키텍처를 사용하여 실시간 에너지 사용량을 예측하는 분산 AI 시스템입니다.

### 🏗️ 시스템 아키텍처

```
[엣지 디바이스] --TCP--> [중간 서버] --HTTP--> [AI 모듈]
     (C++)               (Python)           (Flask REST API)
     
   센서 데이터 수집    →    데이터 중개     →    AI 예측 수행
```

### 📊 데이터 파이프라인

1. **엣지 디바이스**: 온도, 습도, 전력, 월 데이터를 집계하여 12차원 특성 벡터 생성
2. **중간 서버**: TCP로 데이터 수신 후 AI 모듈에 HTTP 요청으로 전달
3. **AI 모듈**: LSTM 등의 머신러닝 알고리즘으로 에너지 사용량 예측

---

## 🚀 시작하기

### 📋 사전 요구사항

- **Python 3.7+** (AI 모듈 및 서버용)
- **C++ 컴파일러** (엣지 디바이스용)
- **Git**

### 📦 의존성 설치

```bash
# 프로젝트 클론
git clone https://github.com/[your-id]/cos-project-2.git
cd cos-project-2.1

# Python 의존성 설치
pip install -r requirements.txt
```

**필수 Python 라이브러리:**
- Flask & Flask-RESTful (AI 모듈 웹 서버)
- TensorFlow & Keras (머신러닝 모델)
- NumPy & scikit-learn (데이터 처리)
- Requests (HTTP 통신)

---

## ⚙️ 실행 방법

### 🎯 단계별 실행 가이드

#### 1️⃣ Terminal 1: AI 모듈 시작

```bash
cd ai-module
python ai.py --port 5556
```

**AI 모듈 기능:**
- REST API 서버 실행 (Flask)
- 머신러닝 모델 관리 (생성, 훈련, 예측)
- 지원 알고리즘: LSTM, CNN 등

#### 2️⃣ Terminal 2: AI 모델 설정 (선택사항)

```bash
python manual_ai_setup.py
```

**모델 설정 기능:**
- 사전 훈련된 모델 로드
- 초기 훈련 데이터 설정

#### 3️⃣ Terminal 3: 서버 시작

```bash
cd server
python server.py --algorithm lstm --dimension 12 --index 6 --caddr 127.0.0.1 --cport 5556 --lport 5555 --name energy_model
```

**서버 매개변수 설명:**
- `--algorithm`: AI 알고리즘 (lstm, cnn 등)
- `--dimension`: 입력 특성 차원 (12차원: 온도3 + 습도3 + 전력5 + 월1)
- `--index`: 예측 대상 인덱스 (6 = 전력 평균값)
- `--caddr`: AI 모듈 IP 주소
- `--cport`: AI 모듈 포트
- `--lport`: 서버 리스닝 포트
- `--name`: 모델 이름

#### 4️⃣ Terminal 4: 엣지 디바이스 실행

##### Windows (실행 파일):
```bash
cd edge
.\edge.exe --addr 127.0.0.1 --port 5555
```

##### Linux/Mac (컴파일 후 실행):
```bash
cd edge
make
./edge --addr 127.0.0.1 --port 5555
```

**엣지 디바이스 기능:**
- 센서 데이터 시뮬레이션
- TCP 프로토콜로 서버에 데이터 전송
- 실시간 AI 예측 결과 수신

---

## 📡 통신 프로토콜

### 🔄 엣지 ↔ 서버 통신 (TCP)

**메시지 형식:**
```
헤더 (3바이트): [메시지타입][페이로드길이(2바이트)]
페이로드: [센서데이터(45바이트)]
```

**데이터 구조 (45바이트):**
- 온도 데이터: 평균, 최소, 최대 (12바이트)
- 습도 데이터: 평균, 최소, 최대 (12바이트)  
- 전력 데이터: 평균, 최소, 최대, 25%, 75% (20바이트)
- 월 데이터: (1바이트)

### 🌐 서버 ↔ AI 모듈 통신 (HTTP REST API)

**주요 엔드포인트:**
- `POST /{model_name}`: 모델 생성
- `PUT /{model_name}/training`: 훈련 데이터 추가
- `POST /{model_name}/training`: 모델 훈련 실행
- `PUT /{model_name}/testing`: 예측 수행
- `GET /{model_name}/result`: 결과 조회

---

## 🧪 테스트 방법

### 🔍 개별 컴포넌트 테스트

```bash
# AI 모듈 테스트
cd ai-module
python prepare_ai_module.py

# 서버 단독 테스트  
python clienttest.py

# 엣지 시뮬레이터 실행
python edge_simulator.py
```

### 🏃‍♂️ 전체 시스템 테스트

1. 모든 터미널에서 컴포넌트 실행
2. 엣지 디바이스에서 데이터 전송 시작
3. AI 예측 결과 확인

---

## 📁 프로젝트 구조

```
cos-project-2.1/
├── ai-module/              # AI 모듈 (Flask REST API)
│   ├── algorithms/         # 머신러닝 알고리즘 구현
│   │   ├── lstm.py        # LSTM 알고리즘
│   │   └── algorithm.py   # 알고리즘 베이스 클래스
│   ├── modules/           # 데이터 및 모델 관리자
│   ├── putils/            # AI 유틸리티 함수
│   ├── ai.py             # 메인 AI 서버
│   └── add_algorithm.py   # 알고리즘 추가 도구
├── server/                # 중간 서버
│   └── server.py         # TCP-HTTP 게이트웨이
├── edge/                  # 엣지 디바이스 (C++)
│   ├── main.cpp          # 메인 실행 파일
│   ├── network_manager.*  # 네트워크 통신 관리
│   ├── data_receiver.*    # 데이터 수신 처리
│   └── Makefile          # 빌드 설정
├── tests/                 # 테스트 코드
├── edge_simulator.py      # Python 엣지 시뮬레이터
├── clienttest.py         # 클라이언트 테스트 도구
└── requirements.txt      # Python 의존성
```

---

## 🔧 설정 가능한 옵션

### AI 모듈 설정
- **포트**: `--port` (기본값: 5556)
- **로그 레벨**: `--log` (DEBUG/INFO/WARNING/ERROR/CRITICAL)

### 서버 설정
- **알고리즘**: `--algorithm` (lstm, cnn 등)
- **입력 차원**: `--dimension` (기본값: 12)
- **예측 인덱스**: `--index` (전력 평균값: 6)
- **AI 모듈 주소**: `--caddr`, `--cport`
- **서버 포트**: `--lport`

### 엣지 디바이스 설정
- **서버 주소**: `--addr` (기본값: 127.0.0.1)
- **서버 포트**: `--port` (기본값: 5555)

---

## 🐛 문제 해결

### 자주 발생하는 오류

1. **포트 충돌**: 다른 포트 번호 사용
2. **모델 훈련 실패**: 충분한 훈련 데이터 제공 (최소 10개 이상)
3. **연결 오류**: 방화벽 설정 확인
4. **LSTM 예측 실패**: 시퀀스 데이터 충분히 제공

### 로그 확인

```bash
# 디버그 모드로 실행
python ai.py --port 5556 --log DEBUG
python server.py --algorithm lstm --dimension 12 --index 6 --caddr 127.0.0.1 --cport 5556 --lport 5555 --name energy_model --log DEBUG
```

---

## 📈 성능 지표

- **예측 정확도**: 임계값 20% 내 예측 성공률
- **응답 시간**: 100ms 이하 예측 응답
- **처리량**: 초당 10개 이상 센서 데이터 처리
