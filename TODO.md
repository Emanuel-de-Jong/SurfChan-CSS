# TODO

### **0.x:** Trainable to see if model improves at all
- fix ground hit not detected
- check sample_log_prob clamp not breaking

### **1.0:** Good single stage finish
- float16 (mixed precision/autocast) for less vram usage
- check biggest performance hassles (measure class)
- CNN smaller first kernel
- copy content of tensorboard on model load
- better rewards
- simple model memory
- bigger nn

### **2.0:** Full linear map and inference
- multiple reward zones
- multiple batches before truncate (server 0.01 speed between batches)
- advanced ml techniques
    - clipped objective
    - entropy regularization
    - LSTM/GRU layer
    - frame stacking/short memory
    - experience replay

### **3.0:** General model for multiple maps
- CSS auto select team
- CSS auto apply commands
- Server map switch
- [implement this](https://chatgpt.com/share/67a9d4b2-def8-8003-b0ff-6ebd88052055)

### **Tweaks and QoL**
- tensorboard more meaningful stats
- convert batch files to powershell scripts
- discrete output for buttons
- more nn input (angle, isCrouch)
- fix stuttery mouse movement
- CSS always on top
- screenshot window minimized
