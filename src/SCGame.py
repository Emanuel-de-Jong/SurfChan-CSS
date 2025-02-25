import subprocess
import asyncio
import shutil
import os
import sys
import numpy as np
import win32gui
import mss
import cv2
from enum import Enum
from sc_config import get_config

class MESSAGE_TYPE(Enum):
    INIT = 1
    START = 2
    STEP = 3
    RESET = 4

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
    def __init__(self, name, start_angle, start_pos, finish_pos, ground):
        self.name = name
        self.start_angle = start_angle
        self.start_pos = start_pos
        self.finish_pos = finish_pos
        self.ground = ground

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
    last_message = None
    should_run_ai = None
    css_window_size = None
    should_downscale_pixels = False

    def __init__(self, env):
        self.env = env
        self.config = get_config()

    async def init(self, surfchan, map_name, should_run_ai):
        print(f"Initializing game...")
        try:
            self.surfchan = surfchan
            self.should_run_ai = should_run_ai
            await self.change_map(map_name)

            await self.init_server()
            await self.init_socket()

            while not self.socket_writer:
                await asyncio.sleep(0.1)

            asyncio.create_task(self.process_messages())

            await self.send_message(MESSAGE_TYPE.INIT, f"{self.config.env.game_speed}")

            while not self.css_process:
                await asyncio.sleep(0.1)

            await self.wait_for_start()
        except asyncio.CancelledError:
            pass
    
    async def change_map(self, map_name):
        map_config = self.config.maps[map_name]
        self.map = Map(map_name,
            map_config.start_angle,
            np.array(map_config.start),
            np.array(map_config.finish),
            map_config.ground)

    async def init_server(self):
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

        print("Initializing server...")
        self.server_process = subprocess.Popen(["css_server/server/srcds.exe", "-console", "-game", "cstrike", "-insecure", "-tickrate", "66", \
            "+maxplayers", "2", "+map", self.map.full_name()])

    async def init_socket(self):
        print("Initializing socket...")
        self.socket = await asyncio.start_server(self.handle_client, self.config.server.host, self.config.server.port)

    async def handle_client(self, reader, writer):
        try:
            addr = writer.get_extra_info('peername')
            print(f"Connected by css server {addr}")

            self.socket_writer = writer

            self.message_queue = asyncio.Queue()
            while reader is not None:
                try:
                    data = await reader.read(8000)
                except OSError:
                    break

                if not data:
                    print(f"Connection closed by css server {addr}")
                    break

                message_str = data.decode()
                message = Message.decode(message_str)
                if not message:
                    continue

                await self.message_queue.put(message)
        except asyncio.CancelledError:
            pass
        finally:
            self.socket_writer = None
            if writer is not None:
                writer.close()

    async def send_message(self, type, data):
        if not self.socket_writer or self.socket_writer.is_closing():
            return

        message = Message(type, data)
        message_str = str(message)
        self.socket_writer.write(message_str.encode())
        await self.socket_writer.drain()

    async def process_messages(self):
        while True:
            message = await self.message_queue.get()
            
            if not self.message_queue.empty():
                print(f"MESSAGES ARE STACKING! QUEUE SIZE: {self.message_queue.qsize()}")
            
            await self.handle_message(message)

    async def handle_message(self, message):
        self.last_message = message

        if message.type == MESSAGE_TYPE.INIT:
            server_ip = message.data
            await self.init_css(server_ip)
    
    async def wait_for_message(self, message_type):
        while not self.last_message or self.last_message.type != message_type:
            await asyncio.sleep(0.01)
        
        data = self.last_message.data
        self.last_message = None
        
        return data

    async def init_css(self, server_ip):
        # Copy autoexec
        css_path = self.config.css.path
        shutil.copy2(os.path.join("assets", "autoexec_css.cfg"), os.path.join(css_path, "cstrike", "cfg", "autoexec.cfg"))

        # Copy maps
        maps_dir_path = os.path.join("assets", "maps")
        for map_path in os.listdir(maps_dir_path):
            dst = os.path.join(css_path, "cstrike", "maps", map_path)
            if not os.path.exists(dst):
                shutil.copy2(os.path.join(maps_dir_path, map_path), dst)
        
        window_size = self.config.model.img_size
        if window_size < 500:
            self.should_downscale_pixels = True
            window_size = 500
        window_size = str(window_size)

        css_exe_path = os.path.join(css_path, "hl2.exe")
        print("Initializing CSS...")
        self.css_process = subprocess.Popen([css_exe_path, "-game", "cstrike", "-windowed", "-novid", \
            "-exec", "autoexec", "+connect", server_ip, "-w", window_size, "-h", window_size])
    
    async def step(self, buttons, mouseH, mouseV):
        message_data = '0'
        if self.should_run_ai:
            message_data = f'1,{buttons},{mouseH},{mouseV}'
        
        await self.send_message(MESSAGE_TYPE.STEP, message_data)

        data = await self.wait_for_message(MESSAGE_TYPE.STEP)
        sep_data = data.split(",")

        player_pos = np.array([float(sep_data[0]), float(sep_data[1]), float(sep_data[2])])
        angle = float(sep_data[3])
        velocity = [float(sep_data[4]), float(sep_data[5]), float(sep_data[6])]
        total_velocity = float(sep_data[7])
        is_crouch = sep_data[8]

        with mss.mss() as sct:
            pixels = np.array(sct.grab(self.css_window_size))
        
        if self.should_downscale_pixels:
            pixels = cv2.resize(pixels, (self.config.model.img_size, self.config.model.img_size), interpolation=cv2.INTER_LINEAR)
        pixels = cv2.cvtColor(pixels, cv2.COLOR_BGRA2RGB)
        
        return pixels, player_pos, total_velocity

    async def wait_for_start(self):
        print("Press enter to start...")
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
    
    async def reset(self):
        await self.send_message(MESSAGE_TYPE.RESET, "")
    
    def close(self):
        if self.socket:
            self.socket.close()

        if self.css_process and self.config.css.close_on_script_close:
            self.css_process.kill()
        
        if self.server_process and self.config.server.close_on_script_close:
            self.server_process.kill()
