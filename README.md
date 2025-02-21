# SurfChan
Training and inference pipeline for a PPO model that can play Source Engine [surf](https://www.youtube.com/watch?v=3pCyKM2YWrI). Specifically on Counter-Strike: Source at the moment.

## Usage
### Dependencies
- Python
- Download maps [here](https://github.com/OuiSURF/Surf_Maps).
- [BSPSource](https://github.com/ata4/bspsrc/releases) to decompile maps and find spawn, trace point and finish locations in Hammer.

### Setup
- Install Python packages `pip install -r requirements.txt`.
    - For GPUs that have CUDA, do this first `pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118`.
- Setup server `css_server/create.md`.
- Copy `config_user_template.yml` and rename it to `config_user.yml`. Then change the values.
- Turn off Steam Overlay for CSS.
- Run `disable_server_internet.ps1` with admin privileges.
- When using Windows 11, [remove rounded corners](https://github.com/valinet/Win11DisableRoundedCorners/releases).

### Run
- Run one of the batch files.
    - `play.bat`: Move around in CSS yourself.
    - `train.bat`: Train a model.
    - `infer.bat`: Have a trained model play indefinitely.
    - `fake_infer.bat`: Acts as a model inferencing to test env, game, server, plugin and css.
- In CSS, select a team and press `F1` to run visual commands.

## Development
### Pre
- When using VS Code, the [SourcePawn Studio](https://marketplace.visualstudio.com/items?itemName=Sarrus.sourcepawn-vscode) extension is recommended.

### Socket format
`TYPE_INT:ITEM_1_VAL,ITEM_1_VAL;ITEM_2_VAL,ITEM_2_VAL`

### Inference Output
**Buttons**
f: forward
b: back
l: left
r: right
j: jump
c: crouch

**Mouse**
-180.00 - 180.00: mouse x
-180.00 - 180.00: mouse y (not AI)
