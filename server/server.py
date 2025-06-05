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
        request = {}
        request['algorithm'] = self.algorithm
        request['dimension'] = self.dimension
        request['index'] = self.index
        js = json.dumps(request)
        logging.debug("[*] To be sent to the AI module: {}".format(js))
        result = requests.post(url, json=js)
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
                    logging.error("Please try again.")
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

    def send_instance(self, vlst, is_training):
        if is_training:
            url = "http://{}:{}/{}/training".format(self.caddr, self.cport, self.name)
        else:
            url = "http://{}:{}/{}/testing".format(self.caddr, self.cport, self.name)
        data = {}
        data["value"] = vlst
        req = json.dumps(data)
        response = requests.put(url, json=req)
        resp = response.json()

        if "opcode" in resp:
            if resp["opcode"] == "failure":
                logging.error("fail to send the instance to the ai module")

                if "reason" in resp:
                    logging.error(resp["reason"])
                else:
                    logging.error("unknown error")
                sys.exit(1)
        else:
            logging.error("unknown response")
            sys.exit(1)

    def parse_data(self, buf, is_training):
        temp = int.from_bytes(buf[0:1], byteorder="big", signed=True)
        humid = int.from_bytes(buf[1:2], byteorder="big", signed=True)
        power = int.from_bytes(buf[2:4], byteorder="big", signed=True)
        month = int.from_bytes(buf[4:5], byteorder="big", signed=True)

        lst = [temp, humid, power, month]
        logging.info("[temp, humid, power, month] = {}".format(lst))

        self.send_instance(lst, is_training)


    def handler(self, client):
        logging.info("[*] Server starts to process the client's request")

        try:
            while True:
                # 3바이트 헤더 수신: 메시지 타입(1바이트) + 페이로드 길이(2바이트, big-endian)
                # Receive 3-byte header: message type (1 byte) + payload length (2 bytes, big-endian)
                header_buf = client.recv(3)
                if len(header_buf) != 3:
                    logging.error("[*] Failed to receive complete header")
                    break
                
                # 헤더 파싱 / Parse header
                msg_type = header_buf[0]
                payload_length = struct.unpack('!H', header_buf[1:3])[0]
                
                logging.info(f"[*] Received header - msg_type: 0x{msg_type:02x}, payload_length: {payload_length}")
                
                # 페이로드 수신 / Receive payload
                if payload_length > 0:
                    payload_buf = client.recv(payload_length)
                    if len(payload_buf) != payload_length:
                        logging.error(f"[*] Failed to receive complete payload (expected: {payload_length}, got: {len(payload_buf)})")
                        break
                else:
                    payload_buf = b''
                
                # 메시지 타입별 분기 처리 / Handle different message types
                if msg_type == 0x01:  # 집계 데이터 수신 / Aggregated data reception
                    logging.info("[*] Processing aggregated data from edge device")
                    
                    try:
                        # struct.unpack을 사용해 big-endian float 벡터를 복원
                        # Restore big-endian float vector using struct.unpack
                        # 예상 데이터: 온도(평균,최소,최대) + 습도(평균,최소,최대) + 전력(평균,최소,최대,p25,p75) + 월(1바이트) = 45바이트
                        # Expected: temp(avg,min,max) + humid(avg,min,max) + power(avg,min,max,p25,p75) + month(1byte) = 45 bytes
                        
                        if payload_length >= 45:
                            # 온도 데이터 (12바이트) / Temperature data (12 bytes)
                            temp_avg, temp_min, temp_max = struct.unpack('!fff', payload_buf[0:12])
                            
                            # 습도 데이터 (12바이트) / Humidity data (12 bytes)  
                            humid_avg, humid_min, humid_max = struct.unpack('!fff', payload_buf[12:24])
                            
                            # 전력 데이터 (20바이트) / Power data (20 bytes)
                            power_avg, power_min, power_max, power_p25, power_p75 = struct.unpack('!fffff', payload_buf[24:44])
                            
                            # 월 데이터 (1바이트) / Month data (1 byte)
                            month = payload_buf[44]
                            
                            # AI 모듈에 전송할 특성 벡터 구성 / Create feature vector for AI module
                            features = [temp_avg, temp_min, temp_max, humid_avg, humid_min, humid_max, 
                                       power_avg, power_min, power_max, power_p25, power_p75, float(month)]
                            
                            logging.info(f"[*] Parsed features: {features}")
                            
                            # Python requests.post()를 사용해 AI 모듈의 /predict 엔드포인트에 JSON으로 전송
                            # Send to AI module's /predict endpoint using requests.post() with JSON
                            ai_url = f"http://{self.caddr}:{self.cport}/predict"
                            ai_request = {"features": features}
                            
                            logging.info(f"[*] Sending prediction request to {ai_url}")
                            ai_response = requests.post(ai_url, json=ai_request, timeout=5)
                            
                            if ai_response.status_code == 200:
                                # AI 응답 JSON에서 prediction 값을 float로 추출
                                # Extract prediction value as float from AI response JSON
                                ai_result = ai_response.json()
                                
                                if "prediction" in ai_result:
                                    prediction = float(ai_result["prediction"])
                                    logging.info(f"[*] AI prediction result: {prediction}")
                                    
                                    # struct.pack('!f', prediction)으로 빅엔디언 바이트 변환
                                    # Convert to big-endian bytes using struct.pack('!f', prediction)
                                    ai_bytes = struct.pack('!f', prediction)
                                    
                                    # 응답 헤더 구성 및 전송 / Compose and send response header
                                    resp_header = bytes([0x81]) + struct.pack('!H', 4)  # msg_type=0x81, length=4
                                    client.sendall(resp_header + ai_bytes)
                                    
                                    logging.info("[*] AI prediction result sent successfully")
                                else:
                                    # AI 응답에 prediction이 없는 경우 / No prediction in AI response
                                    raise ValueError("No prediction field in AI response")
                                    
                            else:
                                # HTTP 요청 실패 / HTTP request failed
                                raise requests.RequestException(f"AI module returned status {ai_response.status_code}")
                                
                        else:
                            # 페이로드 길이 부족 / Insufficient payload length
                            raise ValueError(f"Payload too short: expected 45 bytes, got {payload_length}")
                            
                    except Exception as e:
                        # 오류나 예외 발생 시 에러 응답 전송 / Send error response on exception
                        logging.error(f"[*] Error processing AI request: {str(e)}")
                        
                        error_msg = f"AI processing error: {str(e)}"
                        error_bytes = error_msg.encode('utf-8')
                        error_header = bytes([0xFF]) + struct.pack('!H', len(error_bytes))  # msg_type=0xFF
                        
                        try:
                            client.sendall(error_header + error_bytes)
                            logging.info("[*] Error response sent")
                        except:
                            logging.error("[*] Failed to send error response")
                
                elif msg_type == 0x02:  # 모드 변경 등 기타 메시지 / Mode change and other messages
                    logging.info("[*] Mode change or other command received")
                    # 기존 로직 유지 (ACK 응답) / Keep existing logic (ACK response)
                    ack_header = bytes([0x82]) + struct.pack('!H', 0)  # msg_type=0x82, length=0
                    client.sendall(ack_header)
                    logging.info("[*] ACK response sent")
                
                else:
                    # 알 수 없는 메시지 타입 / Unknown message type
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
            # 클라이언트 연결 정리 / Cleanup client connection
            try:
                client.close()
                logging.info("[*] Client connection closed")
            except:
                pass

    def print_result(self, result):
        logging.info("=== Result of Prediction ({}) ===".format(self.name))
        logging.info("   # of instances: {}".format(result["num"]))
        logging.debug("   sequence: {}".format(result["sequence"]))
        logging.debug("   prediction: {}".format(result["prediction"]))
        logging.info("   correct predictions: {}".format(result["correct"]))
        logging.info("   incorrect predictions: {}".format(result["incorrect"]))
        logging.info("   accuracy: {}\%".format(result["accuracy"]))

def command_line_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--algorithm", metavar="<AI algorithm to be used>", help="AI algorithm to be used", type=str, required=True)
    parser.add_argument("-d", "--dimension", metavar="<Dimension of each instance>", help="Dimension of each instance", type=int, default=1)
    parser.add_argument("-b", "--caddr", metavar="<AI module's IP address>", help="AI module's IP address", type=str, required=True)
    parser.add_argument("-c", "--cport", metavar="<AI module's listening port>", help="AI module's listening port", type=int, required=True)
    parser.add_argument("-p", "--lport", metavar="<server's listening port>", help="Server's listening port", type=int, required=True)
    parser.add_argument("-n", "--name", metavar="<model name>", help="Name of the model", type=str, default="model")
    parser.add_argument("-x", "--ntrain", metavar="<number of instances for training>", help="Number of instances for training", type=int, default=10)
    parser.add_argument("-y", "--ntest", metavar="<number of instances for testing>", help="Number of instances for testing", type=int, default=10)
    parser.add_argument("-z", "--index", metavar="<the index number for the power value>", help="Index number for the power value", type=int, default=0)
    parser.add_argument("-l", "--log", metavar="<log level (DEBUG/INFO/WARNING/ERROR/CRITICAL)>", help="Log level (DEBUG/INFO/WARNING/ERROR/CRITICAL)", type=str, default="INFO")
    args = parser.parse_args()
    return args

def main():
    args = command_line_args()
    logging.basicConfig(level=args.log)

    if args.ntrain <= 0 or args.ntest <= 0:
        logging.error("Number of instances for training or testing should be larger than 0")
        sys.exit(1)

    Server(args.name, args.algorithm, args.dimension, args.index, args.lport, args.caddr, args.cport, args.ntrain, args.ntest)

if __name__ == "__main__":
    main()
