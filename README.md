# SurfChan CSS
Training and inference pipeline for a PPO model that can play Source Engine [surf](https://www.youtube.com/watch?v=3pCyKM2YWrI). Specifically on Counter-Strike: Source at the moment.

> [!NOTE]
> The `stable-baselines3` branch uses baselines3 instead of torchrl. The branch still misses many of the features `main` has, but it created the first training results on which improvement is statistically (and even visually!) noticable. I have given up on finding what causes the torchrl code to break the training data. Meaning if I continue with the project, it will be on the `stable-baselines3` branch.

**Active Development:** 2025-02-07 - 2025-02-26<br>
**Last Change:** 2025-08-20<br>

This is a video of a training run with baselines3 after 4 hours of training. The low quality is due to the increased game speed for faster training as well as recording with a phone. As you can see, the model already knows to move forward as far as possbile and even uses the ramp, with a small flick at the end, to get further.

https://github.com/user-attachments/assets/07009aa6-c184-462c-bb81-4122f6198c06

| | |
| :---: | :---: |
| ![](/Screenshots/1-Training.png) | ![](/Screenshots/.png) |

## Usage
### Dependencies
- Python
- Download maps [here](https://github.com/OuiSURF/Surf_Maps).
- [BSPSource](https://github.com/ata4/bspsrc/releases) to decompile maps and find spawn, trace point and finish locations in Hammer.

### Setup
- Install Python packages `pip install -r requirements.txt`.
    - For GPUs with CUDA: `pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118`
    - For others, CPU is used: `pip install torch torchvision`
- Setup server `css_server/create.md`.
- Copy `config_user_template.yml` and rename it to `config_user.yml`. Then change the values.
- Change the CSS build to before the x64 update. Also disable Steam Overlay.
    - In Steam, right click on the game in your library list and click `Properties...`.
    - Uncheck the `Enable the Steam Overlay while in-game` slide.
    - Go to the `Betas` tab and for `Beta Participation` select `previous_build`.
    - Close the window. It will now start downloading the old version. Wait for it to finish.
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

### Env output
**Buttons**
f: forward
b: back
l: left
r: right
j: jump
c: crouch

**Mouse**
-180.00 - 180.00: mouse x
-90.00 - 90.00: mouse y

### Inference output
An array of 8 floats between 0.0 and 1.0 representing f to c and then mouse x and y.
 