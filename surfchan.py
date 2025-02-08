import configparser
import subprocess
import traceback
import asyncio
import shutil
import signal
import os
from enum import Enum

class MESSAGE_TYPE(Enum):
    TEST = 0
    TICK = 1
    MOVE = 2

class Message:
    def __init__(self, type, data):
        self.type = type
        self.data = data
    
    def __str__(self):
        return f"{self.type.value}:{self.data}"

async def decode_message(message_str):
    message_parts = message_str.split(":")
    return Message(MESSAGE_TYPE(int(message_parts[0])), message_parts[1])

config = configparser.ConfigParser()
config.read('config.cfg')

server = None
cwriter = None

def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(shutdown_handler()))

    try:
        loop.run_until_complete(run())
    except KeyboardInterrupt:
        print("Shutting down gracefully...")
    finally:
        loop.close()

async def shutdown_handler():
    print("\nShutting down...")
    for task in asyncio.all_tasks():
        task.cancel()

async def run():
    global server

    try:
        await run_css()
        await run_server()

        while True:
            await asyncio.sleep(0.5)
            await send_message(MESSAGE_TYPE.TEST, "hello from python")
    except Exception as e:
        traceback.print_exc()
    finally:
        if server:
            server.close()
            await server.wait_closed()

async def run_css():
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

async def run_server():
    global server
    server = await asyncio.start_server(handle_client, config.get('server', 'host'), config.getint('server', 'port'))

async def handle_client(reader, writer):
    global cwriter
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
            await handle_message(message)
    except Exception as e:
        traceback.print_exc()
    finally:
        cwriter = None
        writer.close()
        await writer.wait_closed()

async def handle_message(message):
    if message.type == MESSAGE_TYPE.TEST:
        print(f"Received message: {message}")
    elif message.type == MESSAGE_TYPE.TICK:
        move = await run_ai(message.data)
        await send_message(MESSAGE_TYPE.MOVE, move)

async def run_ai(data):
    # Will run the AI to get player movement
    return "move_forward,rotate_right"

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
