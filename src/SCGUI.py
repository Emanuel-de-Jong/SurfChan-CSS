import tkinter as tk

class SCGUI():
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SurfChan")

        self.buttons_map = {
            'f': ('↑', 1, 1),
            'b': ('↓', 2, 1),
            'l': ('←', 2, 0),
            'r': ('→', 2, 2),
            'c': ('Crouch', 4, 0),
            'j': ('Jump', 4, 2)
        }

        self.buttons = {}
        for key, (label, row, col) in self.buttons_map.items():
            btn = tk.Button(self.root, text=label, width=10, height=3, relief=tk.RAISED)
            btn.grid(row=row, column=col, padx=5, pady=5)
            self.buttons[key] = btn

        self.current_buttons = set()

        self._update()

    def update(self, pressed_buttons):
        pressed_set = set(pressed_buttons)

        for key, btn in self.buttons.items():
            if key in pressed_set and key not in self.current_buttons:
                btn.config(relief=tk.SUNKEN)
            elif key not in pressed_set and key in self.current_buttons:
                btn.config(relief=tk.RAISED)

        self.current_buttons = pressed_set
        self._update()

    def _update(self):
        self.root.update_idletasks()
        self.root.update()
