import traceback
import asyncio
from config import get_config
from SCEnv import SCEnv

async def main():
    env = None
    try:
        config = get_config()
        env = SCEnv(config.infer.map)
        
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
