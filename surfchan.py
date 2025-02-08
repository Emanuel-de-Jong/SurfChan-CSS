import configparser
import subprocess
import traceback
import asyncio
import shutil
import queue
import os
from enum import Enum

class MESSAGE_TYPE(Enum):
    TEST = 0
    START = 1
    TICK = 2
    MOVE = 3

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
    except Exception as e:
        print(f"Invalid message type: {message_parts[0]}")
        return None
    
    return Message(MESSAGE_TYPE(message_type), message_parts[1])

config = configparser.ConfigParser()
config.read('config.cfg')

css_process = None
server = None
cwriter = None
message_queue = queue.Queue()

def main():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run())
    except KeyboardInterrupt:
        loop.run_until_complete(shutdown_handler())
    except Exception as e:
        traceback.print_exc()
    finally:
        loop.close()

async def shutdown_handler():
    print("\nShutting down...")
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    await asyncio.gather(*tasks, return_exceptions=True)

async def run():
    global server, cwriter

    try:
        await start_css()
        await start_server()

        while not cwriter:
            await asyncio.sleep(0.1)
        await send_message(MESSAGE_TYPE.TEST, "hello from python")

        print("Press enter to start training...")
        input()
        await send_message(MESSAGE_TYPE.START, "")

        while True:
            # Will show training progress later
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        traceback.print_exc()
    finally:
        if server:
            server.close()
            await server.wait_closed()
        
        if css_process and config.getboolean('css', 'close_on_script_close'):
            css_process.kill()

async def start_css():
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
    css_process = subprocess.Popen([css_exe_path, "-game", "cstrike", "-windowed", "-novid", "+connect", config.get('server', 'local_ip')])

async def start_server():
    global server
    server = await asyncio.start_server(handle_client, config.get('server', 'host'), config.getint('server', 'port'))

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

            message_queue.put(message)
            check_messages()
    except asyncio.CancelledError:
        pass
    except Exception as e:
        traceback.print_exc()
    finally:
        print(f"Disconnecting {addr}...")
        cwriter = None
        writer.close()
        await writer.wait_closed()

async def check_messages():
    global message_queue
    if message_queue.empty():
        return
    
    if message_queue.qsize() > 1:
        print(f"MESSAGES ARE STACKING! QUEUE SIZE: {message_queue.qsize()}")
        
    await handle_message(message_queue.get())

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
