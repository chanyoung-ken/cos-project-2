import socket
import struct

print('서버에 연결 시도...')
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(('127.0.0.1', 5555))  # 포트 5557로 변경
print('연결 성공!')

# 'Alice' 이름 전송 (프로토콜에 따라)
name = b'Alice'
length = len(name)
s.send(struct.pack('!I', length))  # 길이 전송 (4바이트, big-endian)
s.send(name)  # 이름 전송
print('Alice 전송 완료')

# 응답 받기
resp_len = struct.unpack('!I', s.recv(4))[0]
resp_name = s.recv(resp_len)
print(f'서버로부터 받은 이름: {resp_name.decode()}')

s.close()
print('테스트 완료!')