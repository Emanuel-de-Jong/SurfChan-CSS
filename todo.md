# TODO

### **0.x:** Trainable to see if model improves at all
- check lr change
    - starting too low
    - going low too fast
- check reward system
    - is mouse movement velocity
    - check map axis
    - multiply to reward higher change
    - higher overall reward closer to finish
- check value/critic model broken (does it even try to get better reward?)
- check sample_log_prob clamp not breaking

### **1.0:** Good single stage finish
- less vram usage
- check biggest performance hassles (measure class)
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
