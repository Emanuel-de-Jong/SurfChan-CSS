import asyncio
import threading

_background_loop = asyncio.new_event_loop()

def _start_background_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

_background_thread = threading.Thread(target=_start_background_loop, args=(_background_loop,), daemon=True)
_background_thread.start()

def run_async(coro):
    future = asyncio.run_coroutine_threadsafe(coro, _background_loop)
    return future.result()
