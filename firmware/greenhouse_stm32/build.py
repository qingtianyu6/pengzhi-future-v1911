"""No vendor SDK dependencies: direct register firmware, GCC or bundled Zig/Clang cross compiler."""
from pathlib import Path
import importlib.util
import os
import shutil
import subprocess
import sys
p=Path(__file__).resolve().parent
build=p/'build'; build.mkdir(exist_ok=True)
gcc=shutil.which('arm-none-eabi-gcc')
if gcc:
    cc=[gcc,'-mcpu=cortex-m3','-mthumb']
else:
    spec=importlib.util.find_spec('ziglang')
    if spec is None: raise SystemExit('Install toolchain: python -m pip install ziglang==0.13.0')
    zig=Path(spec.origin).parent/('zig.exe' if os.name=='nt' else 'zig')
    cc=[str(zig),'cc','-target','thumb-freestanding-eabi','-mcpu=cortex_m3']
cmd=cc+['-std=c11','-Os','-ffreestanding','-fno-builtin','-fno-stack-protector','-fdata-sections','-ffunction-sections',
    '-Wall','-Wextra','-Werror','-nostdlib','-Wl,--gc-sections','-Wl,-T,stm32f103c8.ld','-Wl,-e,Reset_Handler',
    'startup.c','main.c','board.c','control.c','oled.c','-o','build/greenhouse.elf']
subprocess.run(cmd,cwd=p,check=True)
if gcc:
    subprocess.run([shutil.which('arm-none-eabi-objcopy'),'-O','binary',str(build/'greenhouse.elf'),str(build/'greenhouse.bin')],check=True)
else:
    subprocess.run([str(zig),'objcopy','-O','binary',str(build/'greenhouse.elf'),str(build/'greenhouse.bin')],check=True)
import struct
elf=(build/'greenhouse.elf').read_bytes()
entry=struct.unpack_from('<I',elf,24)[0]
image=(build/'greenhouse.bin').read_bytes()
sp,reset=struct.unpack_from('<II',image)
assert struct.unpack_from('<H',elf,18)[0]==40, 'ELF must target ARM'
assert 0x08000000 <= (entry & ~1) < 0x08010000, 'Invalid ELF entry'
assert sp==0x20005000 and reset & 1 and 0x08000000 <= (reset & ~1) < 0x08010000, 'Invalid Cortex-M3 vector table'
assert len(image)<=65536, 'Flash overflow'
print(f'Image {len(image)} bytes; entry {entry:#x}; SP {sp:#x}; reset {reset:#x}')
print('Built Cortex-M3 ELF and BIN. Firmware outputs remain locked by config.h; HARDWARE_PENDING.')
