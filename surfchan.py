import configparser
import subprocess
import traceback
import asyncio
import shutil
import os
from enum import Enum

class MESSAGE_TYPE(Enum):
    INIT = 1
    START = 2
    TICK = 3
    MOVE = 4

class Message:
    def __init__(self, type, data):
        self.type = type
        self.data = data
    
    def __str__(self):
        return f"{self.type.value}:{self.data}"

async def decode_message(message_str):
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

config = configparser.ConfigParser()
config.read('config.cfg')

server_process = None
css_process = None
socket = None
cwriter = None
message_queue = asyncio.Queue()

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
    global server_process, socket, cwriter

    try:
        await start_server()
        await start_socket()

        while not cwriter:
            await asyncio.sleep(0.1)

        asyncio.create_task(process_messages())

        await send_message(MESSAGE_TYPE.INIT, "Hello from python")

        print("Press enter to start training...")
        input()
        # Coords are start location x,y,z
        await send_message(MESSAGE_TYPE.START, f"{config.getint('model', 'bot_count')},0,-128,336")

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
        
        if css_process and config.getboolean('css', 'close_on_script_close'):
            css_process.kill()
        
        if server_process and config.getboolean('server', 'close_on_script_close'):
            server_process.kill()

async def start_css(server_ip):
    global css_process

    server_maps_dir_path = os.path.join("css_server", "server", "cstrike", "maps")
    css_path = config.get('css', 'path')
    css_maps_dir_path = os.path.join(css_path, "cstrike", "maps")
    for map_path in os.listdir(server_maps_dir_path):
        src = os.path.join(server_maps_dir_path, map_path)
        dst = os.path.join(css_maps_dir_path, map_path)
        if not os.path.exists(dst):
            shutil.copy2(src, dst)

    css_exe_path = os.path.join(css_path, "hl2.exe")
    css_process = subprocess.Popen([css_exe_path, "-game", "cstrike", "-windowed", "-novid", "+connect", server_ip])

async def start_server():
    global server_process
    server_process = subprocess.Popen(["css_server/server/srcds.exe", "-console", "-game", "cstrike", "-insecure", "-tickrate", "66", \
        "+maxplayers", "16", "+map", "surf_beginner"])

async def start_socket():
    global socket
    socket = await asyncio.start_server(handle_client, config.get('server', 'host'), config.getint('server', 'port'))

async def handle_client(reader, writer):
    global cwriter, message_queue
    cwriter = writer

    addr = writer.get_extra_info('peername')
    print(f"Connected by {addr}")

    try:
        while True:
            data = await reader.read(256)
            if not data:
                print(f"Connection closed by {addr}")
                break

            message_str = data.decode().strip()
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
        move = await run_ai(message.data)
        await send_message(MESSAGE_TYPE.MOVE, move)

async def run_ai(data):
    # Will run the AI to get player movement
    return "f,1.0,0.0"

async def send_message(type, data):
    global cwriter
    if not cwriter or cwriter.is_closing():
        return

    message = Message(type, data)
    message_str = str(message)
    cwriter.write(message_str.encode())
    await cwriter.drain()

if __name__ == '__main__':
    main()
