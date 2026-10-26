# -*- coding: utf-8 -*-
"""다이노 아일랜드 트랙 1 ISO 읽기(2026-10-10) — 파일 목록·꺼내기. python tools/disc.py <이름…> → work/disc/"""
import os, struct, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = r'D:\hospi\My Documents\한글패치\SS\ss\Marica - Shinjitsu no Sekai (Japan)\Marica - Shinjitsu no Sekai (Japan) (Track 1).bin'


def sec(f, l, n=1):
    out = b''
    for i in range(n):
        f.seek((l + i) * 2352 + 16); out += f.read(2048)
    return out


def files(path=BIN):
    f = open(path, 'rb'); pvd = sec(f, 16)
    out = []
    def walk(l, s, pre):
        d = sec(f, l, (s + 2047) // 2048); i = 0
        while i < len(d):
            L = d[i]
            if L == 0: i = (i // 2048 + 1) * 2048; continue
            nm = d[i + 33:i + 33 + d[i + 32]]
            lba, sz, fl = struct.unpack_from('<I', d, i + 2)[0], struct.unpack_from('<I', d, i + 10)[0], d[i + 25]
            if nm not in (b'\0', b'\1'):
                n = nm.decode('latin1').split(';')[0]
                if fl & 2: walk(lba, sz, pre + n + '/')
                else: out.append((pre + n, lba, sz))
            i += L
    walk(struct.unpack_from('<I', pvd, 158)[0], struct.unpack_from('<I', pvd, 166)[0], '/')
    return out


def read(name, path=BIN):
    for n, l, s in files(path):
        if n == name or n.split('/')[-1] == name:
            return sec(open(path, 'rb'), l, (s + 2047) // 2048)[:s]
    raise KeyError(name)


if __name__ == '__main__':
    os.makedirs(os.path.join(ROOT, 'work', 'disc'), exist_ok=True)
    for nm in sys.argv[1:]:
        d = read(nm); open(os.path.join(ROOT, 'work', 'disc', nm.split('/')[-1]), 'wb').write(d); print(nm, len(d))
