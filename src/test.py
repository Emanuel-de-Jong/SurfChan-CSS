import asyncio
import gymnasium as gym
from torchrl.envs.libs.gym import GymEnv
from config import get_config
from SCEnv import SCEnv

async def main():
    env = None
    try:
        config = get_config()

        gym.register(
            id=config.env.name,
            entry_point=lambda: SCEnv()
        )

        env = GymEnv(config.env.name)
        
        await env.env.start(config.infer.map)
        
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    except asyncio.CancelledError:
        pass
    finally:
        print("Closing...")
        
        if env:
            env.close()
        
        tasks = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
        if tasks:
            for task in tasks:
                task.cancel()
            
            await asyncio.gather(*tasks, return_exceptions=True)

if __name__ == "__main__":
    asyncio.run(main())
