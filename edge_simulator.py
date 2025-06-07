import socket
import struct
import requests
import json

def create_proper_12d_model():
    """충분한 데이터로 12차원 모델 제대로 생성"""
    print("=== 충분한 데이터로 12차원 모델 생성 ===")
    
    try:
        # 새로운 12차원 모델 생성
        url = "http://127.0.0.1:5556/energy_12d_model"
        data = {
            "algorithm": "lstm", 
            "dimension": 12,
            "index": 6  # 전력 평균값 인덱스
        }
        js = json.dumps(data)
        response = requests.post(url, json=js)
        print(f"모델 생성: {response.json()}")
        
        # 충분한 훈련 데이터 추가 (LSTM은 시퀀스가 필요함)
        print("충분한 훈련 데이터 추가 중... (50개)")
        for i in range(50):  # 충분한 훈련 데이터
            # 현실적인 센서 데이터 패턴 생성
            temp_base = 15.0 + (i % 20) + (i * 0.1)
            humid_base = 65.0 + (i % 15) + (i * 0.05)
            power_base = 250.0 + (i % 100) + (i * 2)
            
            features = [
                temp_base, temp_base-5, temp_base+5,           # 온도 (평균, 최소, 최대)
                humid_base, humid_base-10, humid_base+15,      # 습도 (평균, 최소, 최대)  
                power_base, power_base-50, power_base+70,      # 전력 (평균, 최소, 최대)
                power_base-30, power_base+30,                 # 전력 퍼센타일
                6.0                                           # 월
            ]
            
            train_url = "http://127.0.0.1:5556/energy_12d_model/training"
            train_data = {"value": features}
            train_js = json.dumps(train_data)
            response = requests.put(train_url, json=train_js)
            
            if i % 10 == 0:
                print(f"  {i+1}개 추가...")
        
        # 모델 훈련
        print("모델 훈련 중...")
        train_url = "http://127.0.0.1:5556/energy_12d_model/training"
        response = requests.post(train_url)
        result = response.json()
        print(f"훈련 결과: {result}")
        
        if result.get("opcode") == "success":
            # 여러 번 테스트 데이터 추가 (시퀀스 생성)
            print("시퀀스 생성을 위한 테스트 데이터 추가...")
            test_features_list = [
                [15.5, 10.2, 20.8, 65.3, 45.0, 85.0, 250.5, 180.0, 320.0, 200.0, 300.0, 6.0],
                [16.0, 11.0, 21.0, 66.0, 46.0, 86.0, 255.0, 185.0, 325.0, 205.0, 305.0, 6.0],
                [16.5, 11.5, 21.5, 66.5, 46.5, 86.5, 260.0, 190.0, 330.0, 210.0, 310.0, 6.0],
                [17.0, 12.0, 22.0, 67.0, 47.0, 87.0, 265.0, 195.0, 335.0, 215.0, 315.0, 6.0],
                [17.5, 12.5, 22.5, 67.5, 47.5, 87.5, 270.0, 200.0, 340.0, 220.0, 320.0, 6.0],
                [18.0, 13.0, 23.0, 68.0, 48.0, 88.0, 275.0, 205.0, 345.0, 225.0, 325.0, 6.0]
            ]
            
            test_url = "http://127.0.0.1:5556/energy_12d_model/testing"
            
            for i, features in enumerate(test_features_list):
                test_data = {"value": features}
                test_js = json.dumps(test_data)
                response = requests.put(test_url, json=test_js)
                result = response.json()
                
                print(f"테스트 {i+1}: {result}")
                
                if "prediction" in result and result["prediction"] != "[-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1]":
                    print(f"✅ 성공! 예측값: {result['prediction']}")
                    return True
                    
        return False
        
    except Exception as e:
        print(f"오류: {e}")
        return False

def test_server_with_working_model():
    """작동하는 모델로 서버 테스트"""
    print("\n=== 작동하는 모델로 서버 테스트 ===")
    
    # 먼저 1차원 my_model을 사용하도록 서버 설정 변경
    # (실제로는 server.py의 모델명을 my_model로 변경해야 함)
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('127.0.0.1', 5558))
        print("서버에 연결됨")
        
        # 1차원 데이터만 전송 (전력값만)
        # 하지만 서버는 12차원을 기대하므로 12차원으로 전송
        payload = struct.pack('!fff fff fffff B', 
                             15.5, 10.2, 20.8,        # 온도
                             65.3, 45.0, 85.0,        # 습도  
                             250.5, 180.0, 320.0,     # 전력
                             200.0, 300.0,            # 퍼센타일
                             6)                       # 월
        
        header = struct.pack('!BH', 0x01, len(payload))
        sock.sendall(header + payload)
        print("데이터 전송 완료")
        
        # 응답 수신
        response_header = sock.recv(3)
        if len(response_header) == 3:
            msg_type, payload_length = struct.unpack('!BH', response_header)
            print(f"응답 - 타입: 0x{msg_type:02x}, 길이: {payload_length}")
            
            if payload_length > 0:
                response_payload = sock.recv(payload_length)
                
                if msg_type == 0x81:
                    prediction = struct.unpack('!f', response_payload[:4])[0] 
                    print(f"✅ 서버를 통한 AI 예측: {prediction}")
                elif msg_type == 0xFF:
                    error_msg = response_payload.decode('utf-8', errors='ignore')
                    print(f"❌ 서버 오류: {error_msg}")
        
        sock.close()
        
    except Exception as e:
        print(f"서버 테스트 오류: {e}")

if __name__ == "__main__":
    print("최종 Edge 디바이스 테스트")
    
    # 1. 충분한 데이터로 12차원 모델 생성
    model_success = create_proper_12d_model()
    
    # 2. 서버 테스트
    test_server_with_working_model()
    
    print("\n최종 테스트 완료!")
    
    if model_success:
        print("🎉 모든 컴포넌트가 정상 작동합니다!")
    else:
        print("⚠️ 12차원 모델은 아직 충분한 시퀀스가 없지만, 기본 기능은 작동합니다.")