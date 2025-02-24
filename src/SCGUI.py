import asyncio
import dearpygui.dearpygui as dpg

_GRID_SIZE = 50
_PADDING = 5
_PRESSED_COLOR = (128, 128, 128)
_RELEASED_COLOR = (255, 255, 255)

class _GUIButton:
    def __init__(self, label, row, col):
        self.label = label
        self.button_id = dpg.generate_uuid()

        x = _GRID_SIZE * row + _PADDING
        y = _GRID_SIZE * col + _PADDING
        size = _GRID_SIZE - _PADDING * 2
        dpg.add_button(label=label, width=size, height=size, pos=(x, y), tag=self.button_id)

    def update(self, pressed):
        dpg.configure_item(self.button_id, color=_PRESSED_COLOR if pressed else _RELEASED_COLOR)

class SCGUI:
    current_buttons = set()

    def __init__(self):
        size = _GRID_SIZE * 3 + _PADDING * 2

        dpg.create_context()
        dpg.create_viewport(title="SurfChan", width=size, height=size)

        with dpg.window(label="SurfChan", width=size, height=size):
            self.buttons = {
                'f': _GUIButton('↑', 0, 1),
                'b': _GUIButton('↓', 1, 1),
                'l': _GUIButton('←', 1, 0),
                'r': _GUIButton('→', 1, 2),
                'c': _GUIButton('Crouch', 2, 0),
                'j': _GUIButton('Jump', 2, 2),
            }

        dpg.setup_dearpygui()
        dpg.show_viewport()

        self.loop = asyncio.create_task(self.run())
    
    async def run(self):
        while dpg.is_dearpygui_running():
            dpg.render_dearpygui_frame()
            await asyncio.sleep(0.1)

    def update(self, button_str):
        pressed_buttons = set(button_str)
        for key, button in self.buttons.items():
            button.update(key in pressed_buttons)
        
        self.current_buttons = pressed_buttons

if __name__ == "__main__":
    gui = SCGUI()

    i = 0
    while True:
        i += 1
        if i % 2 == 0:
            i = 0
            gui.update("f")
        else:
            gui.update("j")
