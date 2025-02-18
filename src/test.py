from SCGame import SCGame

class SCEnv:
    def __init__(self):
        self.game = SCGame(self.step)

    def step(self, screenshot, finish_pos, player_pos):
        return f"f,1.0,0.0"

if __name__ == "__main__":
    env = SCEnv()
