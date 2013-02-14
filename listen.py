import socket
import struct

HOST = '127.0.0.1' # Symbolic name meaning the local host
PORT = 8000 # Arbitrary non-privileged port

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((HOST, PORT))
s.listen(1)
conn, addr = s.accept()

print 'Connected by', addr
conn.settimeout(1)

data = new_data = conn.recv(1024)
try:
    while True:
        print new_data
        new_data = conn.recv(1024)
        data += new_data
except socket.timeout:
    if 'NEWT' in data:
        i = data.index('NEWT')
        tid = struct.unpack('l', data[i+4:i+12])[0]
        print tid

    if 'LOAD' in data:
        print 'continuing'
        #conn.send('stpv')
        #conn.send(struct.pack('l', tid))

        #data = conn.recv(4)
        #print data
        #conn.recv(8)
        conn.send('resa')

conn.close()

