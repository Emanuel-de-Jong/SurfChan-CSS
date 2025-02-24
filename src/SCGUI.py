import asyncio
import threading
import tkinter as tk
from sc_config import get_config

class _GUIButton():
    _RELEASED_COLOR = "white"
    _PRESSED_COLOR = "gray"

    def __init__(self, root, label, row, col):
        self.label = tk.Label(root, text=label, width=7, height=3, bg=self._RELEASED_COLOR)
        self.label.grid(row=row, column=col, padx=4, pady=4)

    def update(self, pressed):
        self.label.config(bg=self._PRESSED_COLOR if pressed else self._RELEASED_COLOR)

class SCGUI():
    current_buttons = set()
    queue = asyncio.Queue()

    def __init__(self):
        self.config = get_config()

        root = tk.Tk()
        root.title("")
        root.attributes('-topmost', True)
        self.root = root

        self.buttons = {
            'f': _GUIButton(root, '↑', 1, 1),
            'b': _GUIButton(root, '↓', 2, 1),
            'l': _GUIButton(root, '←', 2, 0),
            'r': _GUIButton(root, '→', 2, 2),
            'c': _GUIButton(root, 'Crouch', 4, 0),
            'j': _GUIButton(root, 'Jump', 4, 2)
        }

        threading.Thread(target=self.start_socket_loop, daemon=True).start()

        root.after(10, self.process_queue)
        root.mainloop()

    def start_socket_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.handle_server())

    async def handle_server(self):
        try:
            reader, writer = await asyncio.open_connection(self.config.gui.host, self.config.gui.port)
            print("Connected to server")

            while True:
                data = await reader.read(1024)
                if not data:
                    print("Server closed connection")
                    break

                message = data.decode().strip()
                await self.queue.put(message)
        except Exception as e:
            print(f"Connection error: {e}")

    def process_queue(self):
        if not self.queue.empty():
            message = self.queue.get_nowait()
            self.update_buttons(message)
        
        self.root.after(10, self.process_queue)

    def update_buttons(self, button_str):
        pressed_buttons = set(button_str)
        for key, button in self.buttons.items():
            button.update(key in pressed_buttons)
        
        self.current_buttons = pressed_buttons

if __name__ == "__main__":
    sc_gui = SCGUI()
