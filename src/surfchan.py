import subprocess
import traceback
import asyncio
import shutil
import os
import numpy as np
import win32gui
import yaml
import cv2
import mss
from enum import Enum

class MESSAGE_TYPE(Enum):
    INIT = 1
    START = 2
    TICK = 3
    MOVES = 4

class Message:
    def __init__(self, type, data):
        self.type = type
        self.data = data
    
    def __str__(self):
        return f"{self.type.value}:{self.data}"

config = None
server_process = None
css_process = None
css_window_size = None
socket = None
cwriter = None
message_queue = asyncio.Queue()
finish_pos = None
sct = mss.mss()

def main():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run())
    except KeyboardInterrupt:
        loop.run_until_complete(shutdown_handler())
    except Exception:
        traceback.print_exc()
    finally:
        loop.close()

async def shutdown_handler():
    print("\nShutting down...")
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    await asyncio.gather(*tasks, return_exceptions=True)

async def run():
    global config, server_process, css_process, socket, cwriter

    try:
        await load_config()

        await start_server()
        await start_socket()

        while not cwriter:
            await asyncio.sleep(0.1)

        asyncio.create_task(process_messages())

        await send_message(MESSAGE_TYPE.INIT, "")

        while not css_process:
            await asyncio.sleep(0.1)

        asyncio.create_task(wait_for_start())

        while True:
            # Will show training progress later
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        pass
    except Exception:
        traceback.print_exc()
    finally:
        if socket:
            socket.close()
            await socket.wait_closed()
        
        if server_process and config['server']['close_on_script_close']:
            server_process.kill()
        
        if css_process and config['css']['close_on_script_close']:
            css_process.kill()

async def load_config():
    global config, finish_pos

    with open("config.yml", "r") as config_file:
        config = yaml.safe_load(config_file)
    
    finish_pos = config['maps'][config['map']]['finish']

async def start_server():
    global server_process

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

    map = f"surf_{config['map']}"
    print("Starting server...")
    server_process = subprocess.Popen(["css_server/server/srcds.exe", "-console", "-game", "cstrike", "-insecure", "-tickrate", "66", \
        "+maxplayers", "2", "+map", map])

async def start_socket():
    global config, socket
    print("Starting socket...")
    socket = await asyncio.start_server(handle_client, config['server']['host'], config['server']['port'])

async def handle_client(reader, writer):
    global cwriter, message_queue
    try:
        addr = writer.get_extra_info('peername')
        print(f"Connected by {addr}")

        cwriter = writer

        while True:
            data = await reader.read(8000)
            if not data:
                print(f"Connection closed by {addr}")
                break

            message_str = data.decode()
            message = await decode_message(message_str)
            if not message:
                continue

            await message_queue.put(message)
    except asyncio.CancelledError:
        pass
    except Exception:
        traceback.print_exc()
    finally:
        print(f"Disconnecting {addr}...")
        cwriter = None
        writer.close()
        await writer.wait_closed()

async def decode_message(message_str):
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

async def process_messages():
    global message_queue

    while True:
        message = await message_queue.get()
        
        if not message_queue.empty():
            print(f"MESSAGES ARE STACKING! QUEUE SIZE: {message_queue.qsize()}")
        
        await handle_message(message)

async def handle_message(message):
    if message.type == MESSAGE_TYPE.INIT:
        server_ip = message.data
        await start_css(server_ip)
    elif message.type == MESSAGE_TYPE.TICK:
        moves = await run_ai(message.data)
        await send_message(MESSAGE_TYPE.MOVES, moves)

async def run_ai(data):
    global finish_pos

    sep_data = data.split(",")

    position = [float(sep_data[0]), float(sep_data[1]), float(sep_data[2])]
    angle = float(sep_data[3])
    velocity = [float(sep_data[4]), float(sep_data[5]), float(sep_data[6])]
    total_velocity = float(sep_data[7])
    is_crouch = sep_data[8]

    screenshot = await get_screenshot()

    return f"f,1.0,0.0"

async def get_screenshot():
    global sct, css_window_size
    screenshot = sct.grab(css_window_size)
    screenshot = np.array(screenshot)

    # TODO: Remove
    if not os.path.exists("screenshot.png"):
        cv2.imwrite("screenshot.png", screenshot)

    return screenshot

async def send_message(type, data):
    global cwriter
    if not cwriter or cwriter.is_closing():
        return

    message = Message(type, data)
    message_str = str(message)
    cwriter.write(message_str.encode())
    await cwriter.drain()

async def start_css(server_ip):
    global config, css_process

    # Copy autoexec
    css_path = config['css']['path']
    shutil.copy2(os.path.join("assets", "autoexec_css.cfg"), os.path.join(css_path, "cstrike", "cfg", "autoexec.cfg"))

    # Copy maps
    maps_dir_path = os.path.join("assets", "maps")
    for map_path in os.listdir(maps_dir_path):
        dst = os.path.join(css_path, "cstrike", "maps", map_path)
        if not os.path.exists(dst):
            shutil.copy2(os.path.join(maps_dir_path, map_path), dst)

    css_exe_path = os.path.join(css_path, "hl2.exe")
    window_size = str(config['model']['img_size'])
    print("Starting CSS...")
    css_process = subprocess.Popen([css_exe_path, "-game", "cstrike", "-windowed", "-novid", \
        "-exec", "autoexec", "+connect", server_ip, "-w", window_size, "-h", window_size])

async def wait_for_start():
    global config, css_window_size

    print("Press enter to start training...")
    # Runs input() in a separate thread
    await asyncio.to_thread(input)

    map_start_pos = config['maps'][config['map']]['start']
    await send_message(MESSAGE_TYPE.START, \
        f"{map_start_pos[0]},{map_start_pos[1]},{map_start_pos[2]},{map_start_pos[3]}")
    
    hwnd = win32gui.FindWindow(None, "Counter-Strike Source")
    if hwnd:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)

        # Adjust for window border
        left += 3
        top += 26
        img_size = config['model']['img_size']
        css_window_size = { "left": left, "top": top, "width": img_size, "height": img_size }

if __name__ == '__main__':
    main()
