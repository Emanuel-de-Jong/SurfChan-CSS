import socket
import configparser
import subprocess
import shutil
import os

config = configparser.ConfigParser()
config.read('config.cfg')

def run_ai(input):
    # Will run the AI to get player movement
    return "move_forward,rotate_right"

def main():
    run_css()
    run_server()

def run_css():
    server_maps_dir_path = os.path.join("css_server", "server", "cstrike", "maps")
    css_path = config.get('general', 'css_path')
    css_maps_dir_path = os.path.join(css_path, "cstrike", "maps")
    for map_path in os.listdir(server_maps_dir_path):
        src = os.path.join(server_maps_dir_path, map_path)
        dst = os.path.join(css_maps_dir_path, map_path)
        if not os.path.exists(dst):
            shutil.copy2(src, dst)

    css_exe_path = os.path.join(css_path, "hl2.exe")
    subprocess.Popen([css_exe_path, "-game", "cstrike", "-windowed", "-novid", "+connect", config.get('server', 'local_ip')])

def run_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        host = config.get('server', 'host')
        port = config.getint('server', 'port')
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
