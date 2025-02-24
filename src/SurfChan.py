import sys
import asyncio
import traceback
import subprocess
from enum import Enum
import numpy as np
import gymnasium as gym
from sc_config import get_config
from SCEnv import SCEnv, create_torchrl_env
from SCTrain import SCTrain
from SCInfer import SCInfer
from SCTimer import sc_timer

class MODE(Enum):
    PLAY = 1
    TRAIN = 2
    INFER = 3
    FAKE_INFER = 4

class SurfChan():
    env = None
    train = None
    infer = None
    gui_process = None
    gui_socket = None
    gui_writer = None

    async def run(self):
        try:
            self.config = get_config()

            gym.register(self.config.env.name, lambda: SCEnv())

            self.mode = MODE.PLAY
            if len(sys.argv) > 1:
                mode_str = sys.argv[1].lower()
                if mode_str.startswith("t"):
                    self.mode = MODE.TRAIN
                elif mode_str.startswith("i"):
                    self.mode = MODE.INFER
                elif mode_str.startswith("f"):
                    self.mode = MODE.FAKE_INFER

            if self.mode == MODE.PLAY:
                await self._create_play()
            elif self.mode == MODE.TRAIN:
                await self._create_train()
            elif self.mode == MODE.INFER:
                await self._create_infer()
            elif self.mode == MODE.FAKE_INFER:
                await self._create_fake_infer()
        except KeyboardInterrupt:
            pass
        except asyncio.CancelledError:
            pass
        except Exception:
            traceback.print_exc()
        finally:
            sc_timer.print()

            print("Closing...")
            if self.train is not None:
                self.train.close()
            if self.infer is not None:
                self.infer.close()
            if self.env is not None:
                self.env.close()
            if self.gui_process is not None:
                self.gui_process.kill()
            
            tasks = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
            if tasks:
                [task.cancel() for task in tasks]
                await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _create_play(self):
        print("Mode: Play")
        self.env = create_torchrl_env(self, self.config.infer.map, base_only=True, should_run_ai=False)
        while not self.env.is_closed:
            await asyncio.sleep(0.2)
            obs, reward, terminated, truncated, _ = self.env.env.step(self.env.env._fake_action())
    
    async def _create_train(self):
        print("Mode: Train")
        self.train = SCTrain(self)
        await self.train.train()
    
    async def _create_infer(self):
        print("Mode: Infer")
        await self._create_gui()
        
        self.infer = SCInfer(self)
        await self.infer.infer()
    
    async def _create_fake_infer(self):
        print("Mode: Fake Infer")
        await self._create_gui()

        self.env = create_torchrl_env(self, self.config.infer.map, True)

        action = self.env.env._fake_action()
        action[0] = 1.0 # forward
        action[self.env.env.button_count] = 0.7 # look right
        action[self.env.env.button_count + 1] = 0.5 # vertical center
        while not self.env.is_closed:
            await asyncio.sleep(0.034) # 30 fps
            self.env.env.step(action)
    
    async def _create_gui(self):
        self.gui_socket = await asyncio.start_server(self._handle_gui_connection, self.config.gui.host, self.config.gui.port)
        self.gui_process = subprocess.Popen(["python", "src/SCGUI.py"])
        await asyncio.sleep(2)
    
    async def _handle_gui_connection(self, reader, writer):
        try:
            addr = writer.get_extra_info('peername')
            print(f"Connected by gui {addr}")

            self.gui_writer = writer

            while reader is not None:
                try:
                    data = await reader.read(8000)
                except OSError:
                    break

                if not data:
                    print(f"Connection closed by gui {addr}")
                    break
        except asyncio.CancelledError:
            pass
        finally:
            self.gui_writer = None
            if writer is not None:
                writer.close()
    
    async def send_gui_message(self, message):
        if not self.gui_writer or self.gui_writer.is_closing():
            return

        self.gui_writer.write(message.encode())
        await self.gui_writer.drain()

if __name__ == "__main__":
    surfchan = SurfChan()
    asyncio.run(surfchan.run())
