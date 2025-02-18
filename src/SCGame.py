import subprocess
import asyncio
import shutil
import os
import numpy as np
import win32gui
import mss
from enum import Enum
from config import get_config

class MESSAGE_TYPE(Enum):
    INIT = 1
    START = 2
    TICK = 3
    MOVES = 4

class Message:
    def __init__(self, type, data):
        self.type = type
        self.data = data
    
    @staticmethod
    def decode(message_str):
        message_str = message_str.strip()
        
        if not message_str:
            print("Empty message received")
            return None

        message_parts = message_str.split(":")
        if len(message_parts) != 2:
            print(f"Message has invalid format: {message_str}")
            return None
        
        try:
            message_type = int(message_parts[0])
        except Exception:
            print(f"Invalid message type: {message_parts[0]}")
            return None
        
        return Message(MESSAGE_TYPE(message_type), message_parts[1])
    
    def __str__(self):
        return f"{self.type.value}:{self.data}"

class Map:
    def __init__(self, name, start_angle, start_pos, finish_pos):
        self.name = name
        self.start_angle = start_angle
        self.start_pos = start_pos
        self.finish_pos = finish_pos

        self.axis = np.argmax(np.abs(self.finish_pos - self.start_pos))

    def full_name(self):
        return f"surf_{self.name}"

class SCGame:
    env = None
    config = None
    map = None
    server_process = None
    socket = None
    socket_writer = None
    message_queue = None
    css_process = None
    should_run_ai = True
    sct = mss.mss()
    css_window_size = None

    def __init__(self, env):
        self.env = env

    async def start(self, map_name):
        try:
            self.config = get_config()
            await self.change_map(map_name)

            await self.start_server()
            await self.start_socket()

            while not self.socket_writer:
                await asyncio.sleep(0.1)

            asyncio.create_task(self.process_messages())

            await self.send_message(MESSAGE_TYPE.INIT, "")

            while not self.css_process:
                await asyncio.sleep(0.1)

            await self.wait_for_start()
        except asyncio.CancelledError:
            pass
    
    async def change_map(self, map_name):
        map_config = self.config.maps[map_name]
        self.map = Map(map_name, map_config.start_angle, np.array(map_config.start), np.array(map_config.finish))

    async def start_server(self):
        # Copy mapcycle
        server_path = os.path.join("css_server", "server")
        server_cfg_dir_path = os.path.join(server_path, "cstrike", "cfg")
        shutil.copy2(os.path.join("assets", "mapcycle.txt"), os.path.join(server_cfg_dir_path, "mapcycle.txt"))

        # Copy server config
        shutil.copy2(os.path.join("assets", "server.cfg"), os.path.join(server_cfg_dir_path, "server.cfg"))

        # Copy autoexec
        shutil.copy2(os.path.join("assets", "autoexec_server.cfg"), os.path.join(server_cfg_dir_path, "autoexec.cfg"))

        # Copy maps
        maps_dir_path = os.path.join("assets", "maps")
        for map_path in os.listdir(maps_dir_path):
            dst = os.path.join(server_path, "cstrike", "maps", map_path)
            if not os.path.exists(dst):
                shutil.copy2(os.path.join(maps_dir_path, map_path), dst)

        print("Starting server...")
        self.server_process = subprocess.Popen(["css_server/server/srcds.exe", "-console", "-game", "cstrike", "-insecure", "-tickrate", "66", \
            "+maxplayers", "2", "+map", self.map.full_name()])

    async def start_socket(self):
        print("Starting socket...")
        self.socket = await asyncio.start_server(self.handle_client, self.config.server.host, self.config.server.port)

    async def handle_client(self, reader, writer):
        try:
            addr = writer.get_extra_info('peername')
            print(f"Connected by {addr}")

            self.socket_writer = writer

            self.message_queue = asyncio.Queue()
            while True:
                data = await reader.read(8000)
                if not data:
                    print(f"Connection closed by {addr}")
                    break

                message_str = data.decode()
                message = Message.decode(message_str)
                if not message:
                    continue

                await self.message_queue.put(message)
        except asyncio.CancelledError:
            pass
        finally:
            print(f"Disconnecting {addr}...")
            self.socket_writer = None
            writer.close()
            await writer.wait_closed()

    async def process_messages(self):
        while True:
            message = await self.message_queue.get()
            
            if not self.message_queue.empty():
                print(f"MESSAGES ARE STACKING! QUEUE SIZE: {self.message_queue.qsize()}")
            
            await self.handle_message(message)

    async def handle_message(self, message):
        if message.type == MESSAGE_TYPE.INIT:
            server_ip = message.data
            await self.start_css(server_ip)
        elif message.type == MESSAGE_TYPE.TICK:
            moves = '0'
            if self.should_run_ai:
                moves = f'1,{await self.run_ai(message.data)}'
            await self.send_message(MESSAGE_TYPE.MOVES, moves)

    async def start_css(self, server_ip):
        # Copy autoexec
        css_path = self.config.css.path
        shutil.copy2(os.path.join("assets", "autoexec_css.cfg"), os.path.join(css_path, "cstrike", "cfg", "autoexec.cfg"))

        # Copy maps
        maps_dir_path = os.path.join("assets", "maps")
        for map_path in os.listdir(maps_dir_path):
            dst = os.path.join(css_path, "cstrike", "maps", map_path)
            if not os.path.exists(dst):
                shutil.copy2(os.path.join(maps_dir_path, map_path), dst)

        css_exe_path = os.path.join(css_path, "hl2.exe")
        window_size = str(self.config.model.img_size)
        print("Starting CSS...")
        self.css_process = subprocess.Popen([css_exe_path, "-game", "cstrike", "-windowed", "-novid", \
            "-exec", "autoexec", "+connect", server_ip, "-w", window_size, "-h", window_size])

    async def run_ai(self, data):
        sep_data = data.split(",")

        position = np.array([float(sep_data[0]), float(sep_data[1]), float(sep_data[2])])
        angle = float(sep_data[3])
        velocity = [float(sep_data[4]), float(sep_data[5]), float(sep_data[6])]
        total_velocity = float(sep_data[7])
        is_crouch = sep_data[8]

        screenshot = await self.get_screenshot()

        return self.env.step_test(screenshot, position, total_velocity)

    async def get_screenshot(self):
        screenshot = self.sct.grab(self.css_window_size)
        return np.array(screenshot)

    async def send_message(self, type, data):
        if not self.socket_writer or self.socket_writer.is_closing():
            return

        message = Message(type, data)
        message_str = str(message)
        self.socket_writer.write(message_str.encode())
        await self.socket_writer.drain()

    async def wait_for_start(self):
        print("Press enter to start training...")
        # Runs input() in a separate thread
        await asyncio.to_thread(input)

        await self.send_message(MESSAGE_TYPE.START, \
            f"{self.map.start_pos[0]},{self.map.start_pos[1]},{self.map.start_pos[2]},{self.map.start_angle}")
        
        hwnd = win32gui.FindWindow(None, "Counter-Strike Source")
        if hwnd:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)

            # Adjust for window border
            left += 3
            top += 26
            img_size = self.config.model.img_size
            self.css_window_size = { "left": left, "top": top, "width": img_size, "height": img_size }
    
    def close(self):
        if self.socket:
            self.socket.close()

        if self.css_process and self.config.css.close_on_script_close:
            self.css_process.kill()
        
        if self.server_process and self.config.server.close_on_script_close:
            self.server_process.kill()
