#include "network_manager.h"
#include <iostream>
#include <cstdlib>
#include <cstring>
#include <unistd.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <assert.h>
#include <errno.h>

#include "opcode.h"
#include "byte_op.h"
using namespace std;

NetworkManager::NetworkManager() 
{
  this->sock = -1;
  this->addr = NULL;
  this->port = -1;
}

NetworkManager::NetworkManager(const char *addr, int port)
{
  this->sock = -1;
  this->addr = addr;
  this->port = port;
}

void NetworkManager::setAddress(const char *addr)
{
  this->addr = addr;
}

const char *NetworkManager::getAddress()
{
  return this->addr;
}

void NetworkManager::setPort(int port)
{
  this->port = port;
}

int NetworkManager::getPort()
{
  return this->port;
}

int NetworkManager::init()
{
	struct sockaddr_in serv_addr;

	this->sock = socket(PF_INET, SOCK_STREAM, 0);
	if (this->sock == FAILURE)
  {
    cout << "[*] Error: socket() error" << endl;
    cout << "[*] Please try again" << endl;
    exit(1);
  }

	memset(&serv_addr, 0, sizeof(serv_addr));
	serv_addr.sin_family = AF_INET;
	serv_addr.sin_addr.s_addr = inet_addr(this->addr);
	serv_addr.sin_port = htons(this->port);

	if (connect(this->sock, (struct sockaddr*)&serv_addr, sizeof(serv_addr)) == FAILURE)
  {
    cout << "[*] Error: connect() error" << endl;
    cout << "[*] Please try again" << endl;
    exit(1);
  }
	
  cout << "[*] Connected to " << this->addr << ":" << this->port << endl;

  return sock;
}

int NetworkManager::sendData(uint8_t *data, int dlen)
{
  int sock_fd, sent, offset;
  uint8_t header[3];
  uint8_t *p;
  struct sockaddr_in serv_addr;

  // 소켓 생성 / Create socket
  sock_fd = socket(AF_INET, SOCK_STREAM, 0);
  if (sock_fd < 0) {
    cout << "[*] Error: Failed to create socket - " << strerror(errno) << endl;
    return FAILURE;
  }

  // 서버 주소 설정 / Setup server address
  memset(&serv_addr, 0, sizeof(serv_addr));
  serv_addr.sin_family = AF_INET;
  serv_addr.sin_port = htons(this->port);
  if (inet_pton(AF_INET, this->addr, &serv_addr.sin_addr) <= 0) {
    cout << "[*] Error: Invalid address - " << this->addr << endl;
    close(sock_fd);
    return FAILURE;
  }

  // 서버에 연결 / Connect to server
  if (connect(sock_fd, (struct sockaddr*)&serv_addr, sizeof(serv_addr)) < 0) {
    cout << "[*] Error: Connection failed - " << strerror(errno) << endl;
    close(sock_fd);
    return FAILURE;
  }

  cout << "[*] Connected to server " << this->addr << ":" << this->port << endl;

  // 버퍼 오버런 검사 / Buffer overflow check
  if (dlen > BUFLEN || dlen < 0) {
    cout << "[*] Error: Invalid data length " << dlen << endl;
    close(sock_fd);
    return FAILURE;
  }

  // 헤더 구성: 메시지 타입(1바이트) + 페이로드 길이(2바이트, big-endian)
  // Header format: message type (1 byte) + payload length (2 bytes, big-endian)
  p = header;
  VAR_TO_MEM_1BYTE_BIG_ENDIAN(0x01, p); // 집계 데이터 타입 / Aggregated data type
  VAR_TO_MEM_2BYTES_BIG_ENDIAN(dlen, p); // 페이로드 길이 / Payload length

  // 헤더 전송 / Send header
  offset = 0;
  while (offset < 3) {
    sent = send(sock_fd, header + offset, 3 - offset, 0);
    if (sent <= 0) {
      cout << "[*] Error: Failed to send header - " << strerror(errno) << endl;
      close(sock_fd);
      return FAILURE;
    }
    offset += sent;
  }

  // 페이로드 전송 (processData()에서 반환된 데이터) / Send payload (data from processData())
  offset = 0;
  while (offset < dlen) {
    sent = send(sock_fd, data + offset, dlen - offset, 0);
    if (sent <= 0) {
      cout << "[*] Error: Failed to send payload - " << strerror(errno) << endl;
      close(sock_fd);
      return FAILURE;
    }
    offset += sent;
  }

  cout << "[*] Data sent successfully (header: 3 bytes, payload: " << dlen << " bytes)" << endl;

  // 서버 응답 수신 / Receive server response
  uint8_t response = receiveCommand(sock_fd);
  
  // 소켓 닫기 / Close socket
  close(sock_fd);

  return (response != 0xFF) ? SUCCESS : FAILURE;
}

uint8_t NetworkManager::receiveCommand() 
{
  return receiveCommand(this->sock);
}

uint8_t NetworkManager::receiveCommand(int sock_fd)
{
  uint8_t header[3];
  uint8_t msg_type;
  uint16_t payload_length;
  uint8_t *payload = nullptr;
  int received, offset;
  uint8_t *p;

  // 3바이트 헤더 수신 / Receive 3-byte header
  offset = 0;
  while (offset < 3) {
    received = recv(sock_fd, header + offset, 3 - offset, 0);
    if (received <= 0) {
      cout << "[*] Error: Failed to receive header - " << strerror(errno) << endl;
      return 0xFF; // 에러 응답 / Error response
    }
    offset += received;
  }

  // 헤더 파싱: 메시지 타입 + 페이로드 길이 / Parse header: message type + payload length
  p = header;
  MEM_TO_VAR_1BYTE_BIG_ENDIAN(p, msg_type);
  MEM_TO_VAR_2BYTES_BIG_ENDIAN(p, payload_length);

  cout << "[*] Received header - msg_type: 0x" << hex << (int)msg_type 
       << ", payload_length: " << dec << payload_length << endl;

  // 버퍼 오버런 검사 / Buffer overflow check
  if (payload_length > BUFLEN) {
    cout << "[*] Error: Payload length too large: " << payload_length << endl;
    return 0xFF;
  }

  // 페이로드 수신 (길이가 0이 아닌 경우) / Receive payload (if length > 0)
  if (payload_length > 0) {
    payload = new uint8_t[payload_length];
    offset = 0;
    while (offset < payload_length) {
      received = recv(sock_fd, payload + offset, payload_length - offset, 0);
      if (received <= 0) {
        cout << "[*] Error: Failed to receive payload - " << strerror(errno) << endl;
        delete[] payload;
        return 0xFF;
      }
      offset += received;
    }
  }

  // 메시지 타입별 분기 처리 / Handle different message types
  switch (msg_type) {
    case 0x81: // AI 결과 / AI result
      cout << "[*] Received AI prediction result" << endl;
      if (payload_length >= 4 && payload != nullptr) {
        // AI 예측 결과를 float로 해석 / Interpret AI prediction result as float
        uint32_t ai_result_bits;
        p = payload;
        MEM_TO_VAR_4BYTES_BIG_ENDIAN(p, ai_result_bits);
        float ai_result = *(float*)&ai_result_bits;
        cout << "[*] AI Prediction: " << ai_result << endl;
      }
      break;
      
    case 0x82: // ACK 응답 / ACK response
      cout << "[*] Received ACK response" << endl;
      break;
      
    case 0xFF: // 에러 응답 / Error response
      cout << "[*] Received error response from server" << endl;
      if (payload_length > 0 && payload != nullptr) {
        // 에러 메시지 출력 가능 / Can print error message if needed
        cout << "[*] Error details received (" << payload_length << " bytes)" << endl;
      }
      break;
      
    default:
      cout << "[*] Warning: Unknown message type 0x" << hex << (int)msg_type << dec << endl;
      msg_type = 0xFF; // 알 수 없는 타입은 에러로 처리 / Treat unknown type as error
      break;
  }

  // 메모리 정리 / Cleanup memory
  if (payload != nullptr) {
    delete[] payload;
  }

  return msg_type;
}
