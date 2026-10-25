# -*- coding: utf-8 -*-
"""Marica Track 1(MODE1/2352)에서 파일을 work/disc/ 로 뽑는다 (원본 읽기 전용, 2026-10-25).
  python tools/extract.py            → 전부 + work/disc/_files.tsv(경로·LBA·크기)
  python tools/extract.py 파일 …      → 지정 파일만"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from iso9660 import Iso

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACK1 = r'C:\claude\roms\ss\Marica - Shinjitsu no Sekai (Japan)\Marica - Shinjitsu no Sekai (Japan) (Track 1).bin'
OUT = os.path.join(ROOT, 'work', 'disc')


def main(want):
    iso = Iso(TRACK1); os.makedirs(OUT, exist_ok=True)
    rows = []
    for path, lba, size in iso.walk():
        rows.append((path, lba, size))
        if path.endswith('/'): continue
        if lba + (size + 2047) // 2048 > iso.nsec: continue      # 트랙 밖(CD-DA 를 가리키는 항목 등) — 목록에만
        name = path.strip('/').replace('/', os.sep)
        if want and os.path.basename(name).upper() not in want: continue
        dst = os.path.join(OUT, name); os.makedirs(os.path.dirname(dst) or OUT, exist_ok=True)
        open(dst, 'wb').write(iso.read(lba, size))
    if not want:
        with open(os.path.join(OUT, '_files.tsv'), 'w', encoding='utf-8') as w:
            w.write('경로\tLBA\t크기\n' + ''.join('%s\t%d\t%d\n' % r for r in rows))
    print('파일 %d개' % len(rows))


if __name__ == '__main__':
    main({a.upper() for a in sys.argv[1:]})
