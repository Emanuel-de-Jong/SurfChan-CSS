import socket
import configparser
import subprocess

config = configparser.ConfigParser()
config.read('config.cfg')

def run_ai(input):
    # Will run the AI to get player movement
    return "move_forward,rotate_right"

def main():
    run_css()
    run_server()

def run_css():
    css_exe_path = f"{config.get('general', 'CSS_Path')}\\hl2.exe"
    subprocess.Popen([css_exe_path, "-game", "cstrike", "-windowed", "-novid", "+connect", "172.19.112.1"])

def run_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        host = config.get('plugin', 'host')
        port = config.getint('plugin', 'port')
        s.bind((host, port))
        s.listen(1)
        print(f"Python AI server listening on {host}:{port}")

        conn, addr = s.accept()
        with conn:
            print("Connected by", addr)

            is_first_message = True
            while True:
                data = conn.recv(256)
                if not data:
                    break
                
                message = data.decode().strip()
                if is_first_message:
                    print("Received from plugin:", message)
                    is_first_message = False
                
                command = run_ai(message)
                conn.sendall(command.encode())

if __name__ == '__main__':
    main()
