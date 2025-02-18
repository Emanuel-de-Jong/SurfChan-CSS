import sys
import asyncio
from enum import Enum
from config import get_config
from SCEnv import create_torchrl_env
# from SCTrain import SCTrain

class MODE(Enum):
    PLAY = 1
    TRAIN = 2
    INFER = 3

class SurfChan():
    env = None
    train = None
    infer = None

    async def run(self):
        try:
            self.config = get_config()

            self.mode = MODE.PLAY
            if len(sys.argv) > 1:
                mode_str = sys.argv[1].lower()
                if mode_str.startswith("t"):
                    self.mode = MODE.TRAIN
                elif mode_str.startswith("i"):
                    self.mode = MODE.INFER

            await self.create_env()

            if self.mode == MODE.TRAIN:
                self.create_train()
            elif self.mode == MODE.INFER:
                self.create_infer()
            
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass
        except asyncio.CancelledError:
            pass
        finally:
            print("Closing...")
            if self.train is not None:
                self.train.close()
            if self.infer is not None:
                self.infer.close()
            if self.env is not None:
                self.env.close()
            
            tasks = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
            if tasks:
                [task.cancel() for task in tasks]
                await asyncio.gather(*tasks, return_exceptions=True)
    
    async def create_env(self):
        self.env = create_torchrl_env()
        if self.mode == MODE.PLAY:
            self.env.env.game.should_run_ai = False
        
        await self.env.env.start(self.config.infer.map)
    
    def create_train(self):
        # self.train = SCTrain(self.env)
        return
    
    def create_infer(self):
        return

if __name__ == "__main__":
    surfchan = SurfChan()
    asyncio.run(surfchan.run())
