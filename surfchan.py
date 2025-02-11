import subprocess
import traceback
import asyncio
import shutil
import os
import yaml
from enum import Enum
from MapObjects import MapObjects

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

config = None
map_objects = None
server_process = None
css_process = None
socket = None
cwriter = None
message_queue = asyncio.Queue()
finish_pos = None

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
    global config, map_objects, server_process, css_process, socket, cwriter

    try:
        await load_config()

        await start_server()
        await start_socket()

        while not cwriter:
            await asyncio.sleep(0.1)

        map_objects_task = asyncio.create_task(load_map_objects())

        asyncio.create_task(process_messages())

        bot_count = config['model']['bot_count']
        start_angle = config['maps'][config['map']]['start'][3]
        await send_message(MESSAGE_TYPE.INIT, f"{bot_count},{start_angle}")

        while not css_process:
            await asyncio.sleep(0.1)
        
        await map_objects_task

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

async def load_map_objects():
    global map_objects
    print("Loading map objects...")
    map_objects = await asyncio.to_thread(MapObjects, config['map'])

async def start_server():
    global server_process

    max_players = str(config['model']['bot_count'] + 1)
    map = f"surf_{config['map']}"
    print("Starting server...")
    server_process = subprocess.Popen(["css_server/server/srcds.exe", "-console", "-game", "cstrike", "-insecure", "-tickrate", "66", \
        "+maxplayers", max_players, "+map", map])

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
        moves = await run_ai(message.data)
        await send_message(MESSAGE_TYPE.MOVES, moves)

async def run_ai(data):
    global map_objects, finish_pos

    moves = []
    bots_data = data.split(";")
    for i, bot_data_str in enumerate(bots_data):
        bot_data = bot_data_str.split(",")
    
        position = [float(bot_data[0]), float(bot_data[1]), float(bot_data[2])]
        angle = float(bot_data[3])
        velocity = [float(bot_data[4]), float(bot_data[5]), float(bot_data[6])]
        total_velocity = float(bot_data[7])
        is_crouch = bot_data[8]

        # map_objects.get_near_objects(position)

        temp_mouse_x = 1.0
        if i % 2 == 0:
            temp_mouse_x = -1.0
        moves.append(f"f,{temp_mouse_x},0.0")

    return ";".join(moves)

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

    server_maps_dir_path = os.path.join("css_server", "server", "cstrike", "maps")
    css_path = config['css']['path']
    css_maps_dir_path = os.path.join(css_path, "cstrike", "maps")
    for map_path in os.listdir(server_maps_dir_path):
        src = os.path.join(server_maps_dir_path, map_path)
        dst = os.path.join(css_maps_dir_path, map_path)
        if not os.path.exists(dst):
            shutil.copy2(src, dst)

    css_exe_path = os.path.join(css_path, "hl2.exe")
    print("Starting CSS...")
    css_process = subprocess.Popen([css_exe_path, "-game", "cstrike", "-windowed", "-novid", "+connect", server_ip])

async def wait_for_start():
    global config

    print("Press enter to start training...")
    # Runs input() in a separate thread
    await asyncio.to_thread(input)

    map_start_pos = config['maps'][config['map']]['start']
    await send_message(MESSAGE_TYPE.START, \
        f"{map_start_pos[0]},{map_start_pos[1]},{map_start_pos[2]}")

if __name__ == '__main__':
    main()
