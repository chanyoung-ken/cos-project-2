// edge/edge.cpp 수정
void Edge::run()
{
  time_t curr;
  uint8_t opcode;
  uint8_t *data;
  DataSet *ds;
  int dlen;
  int data_count = 0;
  const int MAX_DATA_COUNT = 730; // 충분한 데이터 개수 설정

  cout << "[*] Running the edge device" << endl;

  curr = 1609459200;
  
  // 🔧 수정: 데이터 개수 기반으로 루프 제어
  while (data_count < MAX_DATA_COUNT)
  {
    ds = this->dr->getDataSet(curr);
    data = this->pm->processData(ds, &dlen);
    
    int result = this->nm->sendData(data, dlen);
    if (result == FAILURE) {
      cout << "[*] Failed to send data, retrying..." << endl;
      continue; // 실패 시 재시도
    }
    
    opcode = this->nm->receiveCommand();
    
    data_count++;
    curr += 86400;
    
    cout << "[*] Data sent: " << data_count << "/" << MAX_DATA_COUNT << endl;
    
    // 잠시 대기 (선택사항)
    // sleep(1);
  }

  cout << "[*] All data sent successfully" << endl;
}

// edge/network_manager.cpp 수정 - 연결 유지 방식
class NetworkManager {
private:
    int persistent_sock; // 지속적인 연결을 위한 소켓
    bool is_connected;
    
public:
    int connectToPersistentSocket() {
        if (is_connected && persistent_sock > 0) {
            return SUCCESS; // 이미 연결된 상태
        }
        
        struct sockaddr_in serv_addr;
        persistent_sock = socket(AF_INET, SOCK_STREAM, 0);
        
        if (persistent_sock < 0) {
            cout << "[*] Error: Failed to create persistent socket" << endl;
            return FAILURE;
        }
        
        memset(&serv_addr, 0, sizeof(serv_addr));
        serv_addr.sin_family = AF_INET;
        serv_addr.sin_port = htons(this->port);
        
        if (inet_pton(AF_INET, this->addr, &serv_addr.sin_addr) <= 0) {
            cout << "[*] Error: Invalid address" << endl;
            close(persistent_sock);
            return FAILURE;
        }
        
        if (connect(persistent_sock, (struct sockaddr*)&serv_addr, sizeof(serv_addr)) < 0) {
            cout << "[*] Error: Connection failed" << endl;
            close(persistent_sock);
            return FAILURE;
        }
        
        is_connected = true;
        cout << "[*] Persistent connection established" << endl;
        return SUCCESS;
    }
    
    int sendData(uint8_t *data, int dlen) {
        // 🔧 수정: 지속적인 연결 사용
        if (connectToPersistentSocket() == FAILURE) {
            return FAILURE;
        }
        
        if (dlen > BUFLEN || dlen < 0) {
            cout << "[*] Error: Invalid data length " << dlen << endl;
            return FAILURE;
        }
        
        // 헤더 구성
        uint8_t header[3];
        uint8_t *p = header;
        VAR_TO_MEM_1BYTE_BIG_ENDIAN(0x01, p);
        VAR_TO_MEM_2BYTES_BIG_ENDIAN(dlen, p);
        
        // 헤더 전송
        int offset = 0;
        while (offset < 3) {
            int sent = send(persistent_sock, header + offset, 3 - offset, 0);
            if (sent <= 0) {
                cout << "[*] Error: Failed to send header" << endl;
                closeConnection();
                return FAILURE;
            }
            offset += sent;
        }
        
        // 페이로드 전송
        offset = 0;
        while (offset < dlen) {
            int sent = send(persistent_sock, data + offset, dlen - offset, 0);
            if (sent <= 0) {
                cout << "[*] Error: Failed to send payload" << endl;
                closeConnection();
                return FAILURE;
            }
            offset += sent;
        }
        
        cout << "[*] Data sent successfully" << endl;
        return SUCCESS;
    }
    
    uint8_t receiveCommand() {
        return receiveCommand(persistent_sock);
    }
    
    void closeConnection() {
        if (persistent_sock > 0) {
            close(persistent_sock);
            persistent_sock = -1;
        }
        is_connected = false;
    }
};