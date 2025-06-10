import socket
import requests
import threading
import argparse
import logging
import json
import sys
import struct

OPCODE_DATA = 1
OPCODE_WAIT = 2
OPCODE_DONE = 3
OPCODE_QUIT = 4

class Server:
    def __init__(self, name, algorithm, dimension, index, port, caddr, cport, ntrain, ntest):
        logging.info("[*] Initializing the server module to receive data from the edge device")
        self.name = name
        self.algorithm = algorithm
        self.dimension = dimension
        self.index = index
        self.caddr = caddr
        self.cport = cport
        self.ntrain = ntrain
        self.ntest = ntest
        self.data_counter = 0  # 데이터 카운터 초기화
        success = self.connecter()

        if success:
            self.port = port
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.bind(("0.0.0.0", port))
            self.socket.listen(10)
            self.listener()

    def connecter(self):
        success = True
        self.ai = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ai.connect((self.caddr, self.cport))
        url = "http://{}:{}/{}".format(self.caddr, self.cport, self.name)
        request = {
            'algorithm': self.algorithm,
            'dimension': self.dimension,
            'index': self.index
        }
        logging.debug("[*] To be sent to the AI module: {}".format(request))
        result = requests.post(url, json=request)
        response = json.loads(result.content)
        logging.debug("[*] Received: {}".format(response))

        if "opcode" not in response:
            logging.debug("[*] Invalid response")
            success = False
        else:
            if response["opcode"] == "failure":
                logging.error("Error happened")
                if "reason" in response:
                    logging.error("Reason: {}".format(response["reason"]))
                else:
                    logging.error("Reason: unknown. not specified")
                success = False
            else:
                assert response["opcode"] == "success"
                logging.info("[*] Successfully connected to the AI module")
        return success

    def listener(self):
        logging.info("[*] Server is listening on 0.0.0.0:{}".format(self.port))

        while True:
            client, info = self.socket.accept()
            logging.info("[*] Server accept the connection from {}:{}".format(info[0], info[1]))
            client_handle = threading.Thread(target=self.handler, args=(client,))
            client_handle.start()

    def handler(self, client):
        logging.info("[*] Server starts to process the client's request")

        try:
            while True:
                header_buf = client.recv(3)
                if len(header_buf) != 3:
                    logging.error("[*] Failed to receive complete header")
                    break

                msg_type = header_buf[0]
                payload_length = struct.unpack('!H', header_buf[1:3])[0]
                logging.info(f"[*] Received header - msg_type: 0x{msg_type:02x}, payload_length: {payload_length}")

                if payload_length > 0:
                    payload_buf = client.recv(payload_length)
                    if len(payload_buf) != payload_length:
                        logging.error(f"[*] Failed to receive complete payload (expected: {payload_length}, got: {len(payload_buf)})")
                        break
                else:
                    payload_buf = b''

                if msg_type == 0x01:
                    logging.info("[*] Processing aggregated data from edge device")

                    try:
                        if payload_length >= 45:
                            temp_avg, temp_min, temp_max = struct.unpack('!fff', payload_buf[0:12])
                            humid_avg, humid_min, humid_max = struct.unpack('!fff', payload_buf[12:24])
                            power_avg, power_min, power_max, power_p25, power_p75 = struct.unpack('!fffff', payload_buf[24:44])
                            month = payload_buf[44]

                            features = [temp_avg, temp_min, temp_max, humid_avg, humid_min, humid_max, 
                                       power_avg, power_min, power_max, power_p25, power_p75, float(month)]

                            logging.info(f"[*] Parsed features: {features}")

                            self.data_counter += 1
                            is_training = self.data_counter <= self.ntrain

                            if is_training:
                                # 훈련 데이터 추가
                                ai_url = f"http://{self.caddr}:{self.cport}/{self.name}/training"
                                ai_request = {"value": features}
                                logging.info(f"[*] Adding training data ({self.data_counter}/{self.ntrain}) to {ai_url}")
                                ai_response = requests.put(ai_url, json=ai_request, timeout=5)
                                
                                if ai_response.status_code == 200:
                                    logging.info(f"[*] Training data {self.data_counter} added successfully")
                                    
                                    # 마지막 훈련 데이터를 추가했다면 학습 시작
                                    if self.data_counter == self.ntrain:
                                        logging.info("[*] All training data collected. Starting model training...")
                                        train_start_url = f"http://{self.caddr}:{self.cport}/{self.name}/training"
                                        train_response = requests.post(train_start_url, timeout=60)  # 학습 시간 고려하여 타임아웃 증가
                                        
                                        if train_response.status_code == 200:
                                            train_result = train_response.json()
                                            if train_result.get("opcode") == "success":
                                                logging.info("[*] ✅ Model training completed successfully!")
                                            else:
                                                logging.error(f"[*] ❌ Model training failed: {train_result}")
                                        else:
                                            logging.error(f"[*] ❌ Model training request failed with status {train_response.status_code}")
                                    
                                    # 훈련 단계에서는 예측값 -1 반환
                                    prediction = -1.0
                                else:
                                    logging.error(f"[*] Failed to add training data: {ai_response.status_code}")
                                    prediction = -1.0
                            else:
                                # 테스트 데이터로 예측 수행
                                ai_url = f"http://{self.caddr}:{self.cport}/{self.name}/testing"
                                ai_request = {"value": features}
                                logging.info(f"[*] Sending prediction request to {ai_url}")
                                ai_response = requests.put(ai_url, json=ai_request, timeout=5)

                                if ai_response.status_code == 200:
                                    ai_result = ai_response.json()
                                    if "prediction" in ai_result:
                                        prediction = float(ai_result["prediction"])
                                        logging.info(f"[*] 🎯 AI prediction result: {prediction}")
                                    else:
                                        logging.warning("[*] No prediction field in AI response")
                                        prediction = -1.0
                                else:
                                    logging.error(f"[*] Prediction request failed with status {ai_response.status_code}")
                                    prediction = -1.0

                            # 클라이언트에 결과 전송
                            ai_bytes = struct.pack('!f', prediction)
                            resp_header = bytes([0x81]) + struct.pack('!H', 4)
                            client.sendall(resp_header + ai_bytes)
                            
                            if prediction != -1.0:
                                logging.info("[*] ✅ AI prediction result sent successfully")
                            else:
                                logging.info("[*] ⚠️ Sent default prediction (-1.0)")

                        else:
                            raise ValueError(f"Payload too short: expected 45 bytes, got {payload_length}")

                    except Exception as e:
                        logging.error(f"[*] Error processing AI request: {str(e)}")
                        error_msg = f"AI processing error: {str(e)}"
                        error_bytes = error_msg.encode('utf-8')
                        error_header = bytes([0xFF]) + struct.pack('!H', len(error_bytes))
                        try:
                            client.sendall(error_header + error_bytes)
                            logging.info("[*] Error response sent")
                        except:
                            logging.error("[*] Failed to send error response")

                elif msg_type == 0x02:
                    logging.info("[*] Mode change or other command received")
                    ack_header = bytes([0x82]) + struct.pack('!H', 0)
                    client.sendall(ack_header)
                    logging.info("[*] ACK response sent")
                else:
                    logging.warning(f"[*] Unknown message type: 0x{msg_type:02x}")
                    error_msg = f"Unknown message type: 0x{msg_type:02x}"
                    error_bytes = error_msg.encode('utf-8')
                    error_header = bytes([0xFF]) + struct.pack('!H', len(error_bytes))
                    client.sendall(error_header + error_bytes)

        except requests.Timeout:
            logging.error("[*] Timeout occurred while communicating with AI module")
        except requests.RequestException as e:
            logging.error(f"[*] Request error: {str(e)}")
        except Exception as e:
            logging.error(f"[*] Unexpected error in handler: {str(e)}")
        finally:
            try:
                client.close()
                logging.info("[*] Client connection closed")
            except:
                pass

def command_line_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--algorithm", type=str, required=True)
    parser.add_argument("-d", "--dimension", type=int, default=1)
    parser.add_argument("-b", "--caddr", type=str, required=True)
    parser.add_argument("-c", "--cport", type=int, required=True)
    parser.add_argument("-p", "--lport", type=int, required=True)
    parser.add_argument("-n", "--name", type=str, default="model")
    parser.add_argument("-x", "--ntrain", type=int, default=10)
    parser.add_argument("-y", "--ntest", type=int, default=10)
    parser.add_argument("-z", "--index", type=int, default=0)
    parser.add_argument("-l", "--log", type=str, default="INFO")
    return parser.parse_args()

def main():
    args = command_line_args()
    logging.basicConfig(level=args.log)

    if args.ntrain <= 0 or args.ntest <= 0:
        logging.error("Number of instances for training or testing should be larger than 0")
        sys.exit(1)

    Server(args.name, args.algorithm, args.dimension, args.index, args.lport, args.caddr, args.cport, args.ntrain, args.ntest)

if __name__ == "__main__":
    main()