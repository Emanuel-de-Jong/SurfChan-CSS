# TODO

### **0.x:** Trainable to see if model improves at all
- fix action NA bug
- check if all variables needed for training resume are saved

### **1.0:** Good single stage finish
- fixed step time
- game speedup
- check biggest performance hassles (measure class)
- truncated after x steps
- copy content of tensorboard on model load
- better rewards
- simple model memory
- bigger nn

### **2.0:** Full linear map and inference
- multiple reward zones
- multiple batches before truncated (server 0.01 speed between batches)
- advanced ml techniques
    - clipped objective
    - entropy regularization
    - LSTM/GRU layer
    - frame stacking/short memory

### **3.0:** General model for multiple maps
- CSS auto select team
- CSS auto apply commands
- Server map switch
- [implement this](https://chatgpt.com/share/67a9d4b2-def8-8003-b0ff-6ebd88052055)

### **Tweaks and QoL**
- tensorboard more meaningful stats
- discrete output for buttons
- fix plugin angle return bug
- more nn input (angle, isCrouch)
- fix stuttery mouse movement
- CSS always on top
- screenshot window minimized
