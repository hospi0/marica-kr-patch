# -*- coding: utf-8 -*-
"""SEN.BIN(램 0x06002000) SH-2 디스어셈 — 리터럴 값 주석. python tools/shdis.py 시작 끝"""
import struct, sys
import capstone
B = 0x06002000
s = open(__import__('os').path.join(__import__('os').path.dirname(__file__), '..', 'work', 'disc', 'SEN.BIN'), 'rb').read()
md = capstone.Cs(capstone.CS_ARCH_SH, capstone.CS_MODE_SH2 | capstone.CS_MODE_BIG_ENDIAN)


def dis(a, b):
    out = []
    for ins in md.disasm(s[a - B:b - B], a):
        t = ins.op_str; note = ''
        if ins.mnemonic in ('mov.l', 'mov.w') and t.startswith('0x'):
            la = int(t.split(',')[0], 16)
            if B <= la < B + len(s):
                v = struct.unpack_from('>I' if ins.mnemonic == 'mov.l' else '>h', s, la - B)[0]
                note = '    ; =%X' % (v & 0xFFFFFFFF)
        out.append('%08X %s %s%s' % (ins.address, ins.mnemonic, t, note))
    return out


if __name__ == '__main__':
    print('\n'.join(dis(int(sys.argv[1], 16), int(sys.argv[2], 16))))
