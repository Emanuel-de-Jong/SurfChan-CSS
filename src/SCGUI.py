import tkinter as tk

class _GUIButton():
    def __init__(self, root, label, row, col):
        self.label = tk.Label(root, text=label, width=7, height=7)
        self.label.grid(row=row, column=col, padx=4, pady=4)

    def update(self, pressed):
        self.label.config(bg="gray" if pressed else "white")

class SCGUI():
    current_buttons = set()

    def __init__(self):
        root = tk.Tk()
        root.title("SurfChan")
        self.root = root

        buttons = {}
        buttons['f'] = _GUIButton(root, '↑', 1, 1)
        buttons['b'] = _GUIButton(root, '↓', 2, 1)
        buttons['l'] = _GUIButton(root, '←', 2, 0)
        buttons['r'] = _GUIButton(root, '→', 2, 2)
        buttons['c'] = _GUIButton(root, 'Crouch', 4, 0)
        buttons['j'] = _GUIButton(root, 'Jump', 4, 2)
        self.buttons = buttons

        self.update("")

    def update(self, button_str):
        pressed_buttons = list(button_str)
        for key, button in self.buttons.items():
            button.update(key in pressed_buttons)
        
        self.current_buttons = pressed_buttons

        self._update()

    def _update(self):
        self.root.update_idletasks()
        self.root.update()
