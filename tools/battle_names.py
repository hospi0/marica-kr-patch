# -*- coding: utf-8 -*-
r"""전투 적 이름 그림 한글화 (2026-10-25, 하스피 실기 «미추출 전투»)
  SEN/Bnn/Bnn_01.DAT 맨 앞 576 B = 72×16 4비트 이름 그림(색 1 = 글자, 0 = 바탕) — 글자가 아니라 미리 그린 그림이라 추출에 안 걸림.
  Bnn ↔ SEN_DATA 적 기록 0x19030 + (nn−1)×0x50 의 이름(B03 처럼 빠진 번호 있음) → 그 이름의 번역(work/tr/text.tsv)을 그림으로.
  글꼴 = 갈무리11(게임 글꼴과 같은 1px 획), 72 px 넘으면 갈무리11 좁은꼴, 그래도 넘으면 글자 사이를 좁힘. 왼쪽 x=1·윗줄 y=2(원본 잉크 행 2~13).
  python tools/battle_names.py preview → work/preview/battle_names.png (원본|새것)
  python tools/battle_names.py build   → work/build/files/SEN/Bnn/Bnn_01.DAT"""
import glob, os, re, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
import bdf, build_text as BT

G = r'C:\claude\utils\font\Galmuri-v2.40.3'
W, H, SZ = 72, 16, 576
REC0, RECSZ = 0x19030, 0x50


def names():
    R, loc = BT.load_text()
    inv = {}
    for n, ls in loc.items():
        for L in ls:
            f, o = L.rsplit(':', 1)
            if f == 'SEN/SEN_DATA.DAT': inv[int(o, 16)] = n
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'work', 'disc', 'SEN', 'B*', 'B*_01.DAT'))):
        nn = int(re.search(r'B(\d+)_01', f).group(1))
        n = inv.get(REC0 + (nn - 1) * RECSZ)
        src, t = R.get(n, ('', ''))
        out.append((f, nn, n, src, t))
    return out


def draw(text):
    """→ 16×72 0/1 배열"""
    for path in ('Galmuri11.bdf', 'Galmuri11-Condensed.bdf'):
        f = bdf.Font(os.path.join(G, path))
        ys = [y for c in '가각힣' for x, y in f.draw(c)[0]]; top = min(ys)
        pts, w = f.draw(text)
        if w <= W - 1: break
    gap = 0
    if w > W - 1:                                                   # 그래도 넘치면 글자마다 1 px 씩 당김
        n = len(text) - 1; gap = -min(2, -(-(w - (W - 1)) // max(1, n)))
    a = np.zeros((H, W), np.uint8)
    x = 1
    for ch in text:
        p, cw = f.draw(ch)
        for px, py in p:
            yy, xx = py - top + 2, x + px
            if 0 <= yy < H and 0 <= xx < W: a[yy, xx] = 1
        x += cw + gap
    return a, x


def unpack(b):
    a = np.frombuffer(b, np.uint8); p = np.empty(len(a) * 2, np.uint8); p[0::2] = a >> 4; p[1::2] = a & 15
    return p.reshape(H, W)


def pack(a):
    p = a.ravel(); return bytes((p[0::2] << 4 | p[1::2]).tolist())


def preview():
    rows = names(); im = Image.new('L', ((W + 6) * 2, (H + 2) * len(rows)), 60)
    for k, (f, nn, n, src, t) in enumerate(rows):
        old = unpack(open(f, 'rb').read()[:SZ]); new, x = draw(t)
        im.paste(Image.fromarray((old * 255).clip(0, 255).astype(np.uint8)), (0, k * (H + 2)))
        im.paste(Image.fromarray((new * 255).astype(np.uint8)), (W + 6, k * (H + 2)))
        if x > W or not t: print('  ⚠', os.path.basename(f), src, t, x)
    out = os.path.join(ROOT, 'work', 'preview', 'battle_names.png'); im.resize((im.width * 3, im.height * 3), Image.NEAREST).save(out); print(out)


def build():
    n_ok = 0
    for f, nn, n, src, t in names():
        assert t, (f, src, '번역 없음')
        d = bytearray(open(f, 'rb').read()); new, x = draw(t)
        d[:SZ] = pack(new)
        out = os.path.join(ROOT, 'work', 'build', 'files', 'SEN', os.path.basename(os.path.dirname(f)), os.path.basename(f))
        os.makedirs(os.path.dirname(out), exist_ok=True); open(out, 'wb').write(bytes(d)); n_ok += 1
    print('전투 이름 그림 %d개 → work/build/files/SEN/Bnn/' % n_ok)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    {'preview': preview, 'build': build}[sys.argv[1]]()
