import socket

HOST = '127.0.0.1'
PORT = 27015

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen(1)
        print(f"Python AI server listening on {HOST}:{PORT}")
        conn, addr = s.accept()
        with conn:
            print("Connected by", addr)
            while True:
                data = conn.recv(256)
                if not data:
                    break
                message = data.decode().strip()
                print("Received from plugin:", message)
                command = "Hello from Python\n"
                conn.sendall(command.encode())

if __name__ == '__main__':
    main()
