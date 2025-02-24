import asyncio
import dearpygui.dearpygui as dpg

_TOOLBAR_HEIGHT = 50
_GRID_SIZE = 50
_BUTTON_PADDING = 5
_WINDOW_PADDING = 25
_PRESSED_COLOR = (128, 128, 128)
_RELEASED_COLOR = (255, 255, 255)

def create_theme(color):
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, color, category=dpg.mvThemeCat_Core)
    return theme

_PRESSED_THEME = create_theme(_PRESSED_COLOR)
_RELEASED_THEME = create_theme(_RELEASED_COLOR)

class _GUIButton:
    def __init__(self, label, row, col):
        self.label = label
        self.button_id = dpg.generate_uuid()

        x = _GRID_SIZE * col + _BUTTON_PADDING
        y = _GRID_SIZE * row + _BUTTON_PADDING + _TOOLBAR_HEIGHT
        size = _GRID_SIZE - _BUTTON_PADDING * 2

        dpg.add_button(label=label, width=size, height=size, pos=(x, y), tag=self.button_id)
        dpg.bind_item_theme(self.button_id, _RELEASED_THEME)

    def update(self, pressed):
        dpg.bind_item_theme(self.button_id, _PRESSED_THEME if pressed else _RELEASED_THEME)

class SCGUI:
    current_buttons = set()

    def __init__(self):
        window_width = _GRID_SIZE * 3 + _BUTTON_PADDING * 2
        window_height = window_width + _TOOLBAR_HEIGHT
        vp_width = window_width + _WINDOW_PADDING * 2
        vp_height = window_height + _WINDOW_PADDING * 2

        dpg.create_context()
        dpg.create_viewport(title="SurfChan", width=vp_width, height=vp_height, always_on_top=True)
        dpg.setup_dearpygui()

        with dpg.window(label="SurfChan", width=window_width, height=window_height):
            self.buttons = {
                'f': _GUIButton('^', 0, 1),
                'b': _GUIButton('v', 1, 1),
                'l': _GUIButton('<', 1, 0),
                'r': _GUIButton('>', 1, 2),
                'c': _GUIButton('Crouch', 2, 0),
                'j': _GUIButton('Jump', 2, 2),
            }

        dpg.show_viewport()

    def update(self, button_str):
        pressed_buttons = set(button_str)
        for key, button in self.buttons.items():
            button.update(key in pressed_buttons)
        
        self.current_buttons = pressed_buttons

if __name__ == "__main__":
    gui = SCGUI()
    dpg.start_dearpygui()
    dpg.destroy_context()
