# -*- coding: utf-8 -*-
r"""타이틀 로고 부제 «〜真実の世界〜» → «〜진실의 세계〜» (2026-10-25, 하스피 지시 «타이틀 진실의 세계만 한글화»)
  그림 = TITLE.BIN 안 LHA -lz5- «TITL_WK.DT»(VDP1 VRAM 0x25C01000 부터 통째) 의 0x35FC0 = 320×128 8비트(색 뱅크 0x200).
  원본 부제 = 행 79~102 · 열 66~262 — 양쪽 〜(열 66~92, 230~262)은 원본 그대로, 가운데(열 94~229)만 지우고 한글.
  꼴: 흰 글자(색 1) + 1px 빨간 테두리(색 251) + 글자 가장자리 연분홍(147) — 원본 부제와 같은 색 번호.
  python tools/title_logo.py preview → work/preview/title_kr_preview.png (원본|새것, 실제 팔레트·배경)
  python tools/title_logo.py build   → work/build/TITLE.BIN (lz5 다시 묶어 같은 자리, 크기 넘으면 실패)"""
import os, struct, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(__file__))
import lz5

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO = 0x35FC0; W, H = 320, 128
Y0, Y1, X0, X1 = 79, 103, 94, 230
TEXT = '진실의 세계'
FONT = r'C:\claude\utils\font\nanum-gothic\NanumGothicExtraBold.ttf'
WHITE, RED, PINK = 1, 251, 147


def load():
    d = open(os.path.join(ROOT, 'work', 'disc', 'TITLE.BIN'), 'rb').read()
    h0, name, psz, osz, dp, hb = lz5.find(d)[0]
    assert name == 'TITL_WK.DT'
    out, _ = lz5.decode(d[dp:dp + psz], osz)
    return d, (h0, psz, dp, hb), bytearray(out)


def make(out, track=3):
    L = np.frombuffer(bytes(out[LOGO:LOGO + W * H]), np.uint8).reshape(H, W).copy()
    L[Y0:Y1, X0:X1] = 0                                          # 가운데 글자만 지움(〜 은 열 밖)
    L[Y0:Y1, X1:236] = 0                                         # 界 오른쪽 끝(열 230~235) — 오른쪽 〜 는 열 236 부터(화소 확인)
    fill, edge, ring = glyph_masks()
    blk = np.zeros(fill.shape, np.uint8)
    blk[ring] = RED; blk[edge] = PINK; blk[fill] = WHITE
    L[Y0:Y1, X0:X1] = blk
    new = bytearray(out); new[LOGO:LOGO + W * H] = L.tobytes()
    return new


def glyph_masks():
    """«진실의 세계» 글자 모양 (Y1−Y0)×(X1−X0) → (몸통, 가장자리, 1px 바깥 테두리) — 두 번째 타이틀(tools/opening.py)도 같은 모양을 씀"""
    S = 8; size = 26
    while True:                                                  # 잉크 높이 ≤ 20px(테두리 1px 씩 해서 24행 안)
        f = ImageFont.truetype(FONT, size * S); bb = f.getbbox(TEXT)
        if (bb[3] - bb[1]) / S <= 20: break
        size -= 1
    ws = [f.getlength(c) / S for c in TEXT]
    track = min(8, (X1 - X0 - 4 - sum(ws)) / (len(TEXT) - 1))           # 원본처럼 자리를 고르게 채움
    tw = sum(ws) + track * (len(TEXT) - 1)
    im = Image.new('L', ((X1 - X0) * S, (Y1 - Y0) * S), 0); dr = ImageDraw.Draw(im)
    x = ((X1 - X0) - tw) / 2
    y = ((Y1 - Y0) * S - (bb[3] - bb[1])) / 2 - bb[1]
    for c, w in zip(TEXT, ws):
        dr.text((x * S, y), c, font=f, fill=255); x += w + track
    cov = np.array(im.resize((X1 - X0, Y1 - Y0), Image.BOX), float) / 255
    fill = cov > 0.5
    edge = (cov > 0.2) & ~fill
    body = fill | edge
    pad = np.pad(body, 1)
    ring = np.zeros_like(body)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            ring |= pad[1 + dy:1 + dy + body.shape[0], 1 + dx:1 + dx + body.shape[1]]
    ring &= ~body
    print('글자 크기 %d · 폭 %.0f/%d' % (size, tw, X1 - X0))
    return fill, edge, ring


def palette():
    cram = open(os.path.join(ROOT, 'work', 'mem', 'title', 'CRAM.bin'), 'rb').read()
    def col(i):
        v = struct.unpack_from('<H', cram, i * 2)[0]
        return ((v & 31) << 3, ((v >> 5) & 31) << 3, ((v >> 10) & 31) << 3)
    return col


def picture(out):
    col = palette()
    bg = np.frombuffer(bytes(out[0x12C00:0x12C00 + 320 * 240]), np.uint8).reshape(240, 320)
    lg = np.frombuffer(bytes(out[LOGO:LOGO + W * H]), np.uint8).reshape(H, W)
    im = Image.new('RGB', (320, 240))
    px = im.load()
    for y in range(240):
        for x in range(320):
            v = lg[y - 8, x] if 8 <= y < 8 + H else 0
            px[x, y] = col(0x200 + int(v)) if v else col(0x100 + int(bg[y, x]))
    return im


def main(cmd):
    d, (h0, psz, dp, hb), out = load()
    new = make(out)
    if cmd == 'preview':
        a = picture(out).crop((40, 60, 290, 120)); b = picture(new).crop((40, 60, 290, 120))
        S = 5; c = Image.new('RGB', (a.width * S, a.height * S * 2 + 10), (0, 0, 0))
        c.paste(a.resize((a.width * S, a.height * S), Image.NEAREST), (0, 0))
        c.paste(b.resize((b.width * S, b.height * S), Image.NEAREST), (0, a.height * S + 10))
        os.makedirs(os.path.join(ROOT, 'work', 'preview'), exist_ok=True)
        c.save(os.path.join(ROOT, 'work', 'preview', 'title_kr_preview.png'))
        picture(new).resize((960, 720), Image.NEAREST).save(os.path.join(ROOT, 'work', 'preview', 'title_kr_full.png'))
        print('→ work/preview/title_kr_preview.png · title_kr_full.png')
    elif cmd == 'build':
        packed = lz5.encode(bytes(new))
        back, _ = lz5.decode(packed, len(new)); assert back == bytes(new), '왕복 실패'
        room = psz
        nxt = d.find(b'-lz5-', dp) - 2
        assert len(packed) <= room, ('압축이 원래보다 큼', len(packed), room)
        hdr = lz5.build_header(hb, packed, new)
        t = bytearray(d); t[h0:h0 + len(hdr)] = hdr; t[dp:dp + len(packed)] = packed
        t[dp + len(packed):dp + psz] = bytes(psz - len(packed))
        os.makedirs(os.path.join(ROOT, 'work', 'build'), exist_ok=True)
        open(os.path.join(ROOT, 'work', 'build', 'TITLE.BIN'), 'wb').write(t)
        print('압축 %d → %d B (자리 %d) → work/build/TITLE.BIN' % (psz, len(packed), room))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'preview')
