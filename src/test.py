import traceback
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
    except Exception:
        traceback.print_exc()
    finally:
        if env:
            env.close()

if __name__ == "__main__":
    asyncio.run(main())
