# -*- coding: utf-8 -*-
"""자막 글꼴 비교 미리보기(2026-10-25): 지금(나눔고딕 15px 1비트) | 갈무리14 | 갈무리11 굵게 → work/preview/sub_font_cmp.png"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
import subdata as D, subhook as H, bdf
from PIL import Image, ImageFont

G = r'C:\claude\utils\font\Galmuri-v2.40.3'
LINES = ['당신을 비일상으로 이끄는 매개체이다.', '응, 엄마. 망상이 아니야. 몸이 좀 이상해.', '앙금·밤·잠·방·암흑·명랑·상냥함']


def galmuri(path, chars):
    f = bdf.Font(path)
    ys = [y for c in '가각힣맑앙ㅁ' for x, y in f.draw(c)[0]]
    top = min(ys); bot = max(ys); off = 1 - top + max(0, (14 - (bot - top + 1)) // 2)
    bits, advs = {}, {}
    for c in chars:
        pts, w = f.draw(c)
        rows = [0] * 16
        for x, y in pts:
            yy = y + off
            if 0 <= yy < 16 and 0 <= x < 16: rows[yy] |= 0x8000 >> x
        bits[c] = b''.join(struct.pack('>H', r) for r in rows); advs[c] = max(1, min(16, w if c != ' ' else 4))
    return bits, advs


def page(text, bits, advs):
    order = sorted(set(text)); idx = {c: i for i, c in enumerate(order)}
    fb = [bits[c] for c in order]; fa = [advs[c] for c in order]
    w = sum(fa[idx[c]] for c in text); x0 = (320 - w) // 2
    t = H.ref_render((0, 1, x0, w, [idx[c] for c in text]), fb, fa)
    im = Image.new('RGB', (320, 24), (60, 70, 90)); pal = {1: (0, 0, 0), 2: (255, 255, 255), 3: (82, 82, 148)}
    for y in range(24):
        for x in range(320):
            b = t[y * 160 + x // 2]; v = b >> 4 if x % 2 == 0 else b & 15
            if v: im.putpixel((x, y), pal[v])
    return im


def main():
    chars = set(''.join(LINES)) | {' '}
    f = ImageFont.truetype(D.FONT, D.PX); fbig = ImageFont.truetype(D.FONT, D.PX * 4)
    cur = {c: D.render_glyph(c, f, fbig) for c in chars}
    sets = [('지금', {c: v[0] for c, v in cur.items()}, {c: v[1] for c, v in cur.items()}),
            ('갈무리14', *galmuri(os.path.join(G, 'Galmuri14.bdf'), chars)),
            ('갈무리11 굵게', *galmuri(os.path.join(G, 'Galmuri11-Bold.bdf'), chars))]
    sheet = Image.new('RGB', (320, (24 * len(LINES) + 6) * len(sets)), (255, 255, 255))
    for k, (nm, b, a) in enumerate(sets):
        for j, L in enumerate(LINES): sheet.paste(page(L, b, a), (0, k * (24 * len(LINES) + 6) + 24 * j))
    out = os.path.join(ROOT, 'work', 'preview', 'sub_font_cmp.png'); sheet.resize((960, sheet.height * 3), Image.NEAREST).save(out); print(out, [s[0] for s in sets])


if __name__ == '__main__':
    main()
