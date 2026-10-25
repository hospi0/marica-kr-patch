# -*- coding: utf-8 -*-
"""작은 SH-2 어셈블러(버닝 레인저 build.py 의 A 그대로) — 라벨·분기·리터럴 풀"""
import struct


class A:
    def __init__(s, base): s.base = base; s.c = []; s.lab = {}; s.fix = []
    def w(s, *v): s.c.extend(x & 0xFFFF for x in v)
    def L(s, n): s.lab[n] = s.base + 2 * len(s.c)
    def br(s, op, n): s.fix.append((len(s.c), op, n)); s.c.append(0)
    def ld(s, rn, val): s.fix.append((len(s.c), 'lit', (rn, val))); s.c.append(0)
    def build(s):
        if len(s.c) % 2: s.c.append(0x0009)
        pool = s.base + 2 * len(s.c); vals = []
        for _, op, a in s.fix:
            if op == 'lit':
                v = s.lab[a[1]] if isinstance(a[1], str) else a[1]
                if v not in vals: vals.append(v)
        la = {v: pool + 4 * k for k, v in enumerate(vals)}
        for i, op, a in s.fix:
            pc = s.base + 2 * i
            if op == 'lit':
                d = la[s.lab[a[1]] if isinstance(a[1], str) else a[1]] - ((pc & ~3) + 4); assert d >= 0 and d % 4 == 0 and d // 4 < 256, (hex(pc), d); s.c[i] = 0xD000 | (a[0] << 8) | d // 4
            else:
                d = (s.lab[a] - (pc + 4)) // 2
                if op in ('bra', 'bsr'): assert -2048 <= d < 2048; s.c[i] = (0xA000 if op == 'bra' else 0xB000) | (d & 0xFFF)
                else: assert -128 <= d < 128, (op, a, d); s.c[i] = {'bt': 0x8900, 'bf': 0x8B00, 'bts': 0x8D00, 'bfs': 0x8F00}[op] | (d & 0xFF)   # ★bt/s·bf/s(지연) — 예전엔 bf 로 잘못 만들어짐
        return b''.join(struct.pack('>H', x) for x in s.c) + b''.join(struct.pack('>I', v) for v in vals)
