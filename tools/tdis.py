"""TITLE.BIN(램 0x06002000, 타이틀 화면) SH-2 디스어셈 — python tools/tdis.py 시작 끝"""
import os, struct, sys, capstone
B = 0x06002000
s = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'disc', 'TITLE.BIN'), 'rb').read()
md = capstone.Cs(capstone.CS_ARCH_SH, capstone.CS_MODE_SH2 | capstone.CS_MODE_BIG_ENDIAN)
for ins in md.disasm(s[int(sys.argv[1], 16) - B:int(sys.argv[2], 16) - B], int(sys.argv[1], 16)):
    t = ins.op_str; note = ''
    if ins.mnemonic in ('mov.l', 'mov.w') and t.startswith('0x'):
        la = int(t.split(',')[0], 16); v = struct.unpack_from('>I' if ins.mnemonic == 'mov.l' else '>h', s, la - B)[0]; note = ' ; =%X' % (v & 0xFFFFFFFF)
    print('%08X %s %s%s' % (ins.address, ins.mnemonic, t, note))
