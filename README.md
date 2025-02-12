# SurfChan

## Usage
### Pre
- Python
- [BSPSource](https://github.com/ata4/bspsrc/releases) to decompile maps and find spawn, trace point and finish locations in Hammer.

### Setup
- Install Python packages `pip install -r requirements.txt`
- Setup server `css_server/create.md`
- Copy `config_template.yml` and rename it to `config.yml`

### Run
- `./run.bat`

## Development
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
