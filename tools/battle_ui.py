# -*- coding: utf-8 -*-
r"""전투 UI 그림 한글화 (2026-10-25, 하스피 «전투» 할일)
  SEN_DATA.DAT 0xA05C lz5 «CMD_DATA.DAT»(25,760 B, VDP1 0x25C01000, 8비트 색 = 0x300 + 화소) 안 조각을 같은 크기로 다시 그림.
    메뉴 64×18 ×5(0x0 + k×0x480) · HUD 이름 32×16 ×3(0x1E00 + k×0x300) ·
    超能力 머리 = A 조각 40×16(0x2E20 + k×0x280, 攻撃·回復·上昇·低下·吸収·反射) + B 조각 40×16(0x2BA0, 공용) 을 x, x+40 에 이어 찍음 ·
    アイテム 머리 = A 조각 32×16(0x4020 + k×0x200, 攻撃·回復·上昇) + B 조각 48×16(0x3D20, 공용) 을 x, x+32 에.
  머리는 80 px 한 줄로 한 번에 그린 뒤 경계에서 자름 — B(공용 뒷말)는 모든 앞말에서 같은 자리라 같은 화소(검산).
  글자(메뉴 갈무리14 굵게 · 머리 갈무리14 보통 · 이름 갈무리9) = 갈무리 비트맵 한 색(색 1) + 둘레 1 px 테두리(색 31) / 이름은 색 35 + 테두리 62(원본 색 번호 그대로).
  python tools/battle_ui.py preview → work/preview/battle_ui.png (원본|새것, 스샷에서 뽑은 실제 색)
  python tools/battle_ui.py build   → work/build/files/SEN/SEN_DATA.DAT 안 CMD_DATA 만 바꿈(★build_text 뒤에 돌릴 것)"""
import os, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
import bdf, lz5

G = r'C:\claude\utils\font\Galmuri-v2.40.3'
SRC = os.path.join(ROOT, 'work', 'disc', 'SEN', 'SEN_DATA.DAT')
OUT = os.path.join(ROOT, 'work', 'build', 'files', 'SEN', 'SEN_DATA.DAT')
NAME = 'CMD_DATA.DAT'

MENU = ['공격', '초능력', '도구', '방어', '도망']                  # 攻撃 超能力 道具 防御 逃亡
NAMES = ['마리카', '아키라', '카나메']                             # まりか あきら かなめ
PSI_PRE = ['공격', '회복', '상승', '저하', '흡수', '반사']          # + 초능력
ITEM_PRE = ['공격', '회복', '상승']                                 # + 아이템
INK, EDGE, NINK, NEDGE = 1, 31, 35, 62


def font(n): return bdf.Font(os.path.join(G, n))


def mask(f, text, W, H, x, y, bold=False, gap=0):
    """글자 잉크 0/1 — (x, y) = 왼쪽 위(윗선 기준 잉크 윗줄을 y 에 맞춤)"""
    ys = [py for c in '가힣' for _, py in f.draw(c)[0]]; top = min(ys)
    a = np.zeros((H, W), np.uint8); cx = x
    for ch in text:
        p, w = f.draw(ch)
        for px, py in p:
            for b in ((0, 1) if bold else (0,)):
                yy, xx = py - top + y, cx + px + b
                if 0 <= yy < H and 0 <= xx < W: a[yy, xx] = 1
        cx += w + gap + (1 if bold else 0)
    return a, cx - x


def width(f, text, bold=False, gap=0):
    return mask(f, text, 400, 40, 0, 0, bold, gap)[1] - gap


def outline(a, ink, edge):
    """잉크 + 8방향 1 px 테두리 → 색 번호"""
    H, W = a.shape; e = np.zeros_like(a)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            e[max(dy, 0):H + min(dy, 0), max(dx, 0):W + min(dx, 0)] |= a[max(-dy, 0):H + min(-dy, 0), max(-dx, 0):W + min(-dx, 0)]
    out = np.where(e > 0, edge, 0).astype(np.uint8); out[a > 0] = ink
    return out


def draw_menu(t):
    """64×18 — 원본처럼 두 글자는 넓게 벌려(攻　撃), 세 글자는 붙여"""
    f = font('Galmuri14.bdf'); W, H = 64, 18
    gap = 0 if len(t) == 3 else 12
    w = width(f, t, True, gap); x = (W - w) // 2
    a, _ = mask(f, t, W, H, x, 2, True, gap)
    return outline(a, INK, EDGE)


def draw_name(t):
    f = font('Galmuri9.bdf'); W, H = 32, 16                         # 3글자 30 px + 테두리 = 32(좁은꼴 11 은 «리» 찌그러짐)
    w = width(f, t); assert w <= W - 2, (t, w)
    a, _ = mask(f, t, W, H, (W - w) // 2, 6)
    return outline(a, NINK, NEDGE)


def draw_header(pre, post, cut, W=80):
    """앞말 + 띄어쓰기 + 뒷말 80×16 → (A = [:cut], B = [cut:]) — 뒷말은 늘 같은 x(앞말 길이와 무관)"""
    # 메뉴와 같은 갈무리14(2026-10-25 하스피 «폰트 맞춰») — 굵게는 «공격 아이템»이 80 px 넘어 보통 굵기, 띄어쓰기는 잉크 사이 sp px
    f = font('Galmuri14.bdf'); H = 16
    def ink(t):
        a, _ = mask(f, t, W, H, 0, 1); xs = np.nonzero(a.any(0))[0]; return a, xs[0], xs[-1] + 1
    _, l0, r0 = ink('공격'); wp = r0 - l0; _, l1, r1 = ink(post); wq = r1 - l1
    sp = min(5, W - 2 - wp - wq)
    x0 = max(1, (W - (wp + sp + wq)) // 2)
    a1, l, r = ink(pre); a1 = np.roll(a1, x0 + wp - r, 1)                      # 앞말 오른쪽 끝을 맞춤
    a2, l, r = ink(post); a2 = np.roll(a2, x0 + wp + sp - l, 1)
    a = outline(a1 | a2, INK, EDGE)
    assert sp >= 3 and not (a1 | a2)[:, [0, -1]].any(), (pre, post, sp, '칸 넘침')
    assert not (outline(a1, 1, 1)[:, cut:]).any(), (pre, '앞말이 공용 조각으로 넘어감')
    return a[:, :cut], a[:, cut:]


def pieces():
    """→ [(위치, 폭, 높이, 새 그림, 이름)]"""
    out = []
    for k, t in enumerate(MENU): out.append((k * 0x480, 64, 18, draw_menu(t), t))
    for k, t in enumerate(NAMES): out.append((0x1E00 + k * 0x300, 32, 16, draw_name(t), t))
    Bs = set()
    for k, p in enumerate(PSI_PRE):
        A, B = draw_header(p, '초능력', 40); out.append((0x2E20 + k * 0x280, 40, 16, A, p + '+')); Bs.add(B.tobytes())
    assert len(Bs) == 1; out.append((0x2BA0, 40, 16, B, '+초능력'))
    Bs = set()
    for k, p in enumerate(ITEM_PRE):
        A, B = draw_header(p, '아이템', 32); out.append((0x4020 + k * 0x200, 32, 16, A, p + '+')); Bs.add(B.tobytes())
    assert len(Bs) == 1; out.append((0x3D20, 48, 16, B, '+아이템'))
    return out


def load(path):
    d = open(path, 'rb').read()
    for h0, name, psz, osz, dp, hb in lz5.find(d):
        if name == NAME:
            out, _ = lz5.decode(d[dp:dp + psz], osz)
            return d, dict(h0=h0, psz=psz, osz=osz, dp=dp, hb=hb), bytearray(out)
    raise SystemExit('CMD_DATA 없음')


def apply(cmd):
    new = bytearray(cmd)
    for o, w, h, a, t in pieces():
        assert a.shape == (h, w); new[o:o + w * h] = a.tobytes()
    return new


# 스샷(전투메인메뉴·초능력)에서 뽑은 실제 색 — 상태 CRAM 은 장면 그림이 0x300 묶음을 덮어 다름
PAL = {0: None, 1: (248, 248, 248), 13: (77, 77, 77), 14: (144, 152, 152), 15: (40, 40, 40), 31: (0, 0, 0),
       35: (248, 248, 152), 62: (72, 32, 24)}


def rgb(a, bg):
    im = np.zeros(a.shape + (3,), np.uint8); im[:] = bg
    for k, c in PAL.items():
        if c: im[a == k] = c
    other = ~np.isin(a, list(PAL)); im[other] = (200, 200, 200)
    return im


def preview():
    d, e, cmd = load(SRC); new = apply(cmd)
    G_ = (4, 72, 5); N_ = (30, 24, 60)
    rows = []
    def piece(buf, o, w, h): return np.frombuffer(bytes(buf[o:o + w * h]), np.uint8).reshape(h, w)
    for k in range(5): rows.append([(piece(cmd, k * 0x480, 64, 18), piece(new, k * 0x480, 64, 18), G_)])
    for k in range(3): rows.append([(piece(cmd, 0x1E00 + k * 0x300, 32, 16), piece(new, 0x1E00 + k * 0x300, 32, 16), N_)])
    for k in range(6):
        A = 0x2E20 + k * 0x280
        rows.append([(np.hstack([piece(cmd, A, 40, 16), piece(cmd, 0x2BA0, 40, 16)]), np.hstack([piece(new, A, 40, 16), piece(new, 0x2BA0, 40, 16)]), G_)])
    for k in range(3):
        A = 0x4020 + k * 0x200
        rows.append([(np.hstack([piece(cmd, A, 32, 16), piece(cmd, 0x3D20, 48, 16)]), np.hstack([piece(new, A, 32, 16), piece(new, 0x3D20, 48, 16)]), G_)])
    W = 2 * 80 + 12; H = sum(r[0][0].shape[0] + 4 for r in rows)
    sheet = np.full((H, W, 3), 40, np.uint8); y = 0
    for (o, n, bg), in rows:
        h, w = o.shape
        sheet[y:y + h, 0:w] = rgb(o, bg); sheet[y:y + h, 86:86 + w] = rgb(n, bg); y += h + 4
    out = os.path.join(ROOT, 'work', 'preview', 'battle_ui.png')
    Image.fromarray(sheet).resize((W * 4, H * 4), Image.NEAREST).save(out); print(out)


def build():
    base = OUT if os.path.exists(OUT) else SRC
    d, e, cmd = load(base); _, e0, _ = load(SRC)
    assert (e['h0'], e['dp'], e['psz']) == (e0['h0'], e0['dp'], e0['psz']), 'CMD_DATA 자리가 원본과 다름'
    new = bytes(apply(cmd))
    for cands in (512, 2048, 8192):
        packed = lz5.encode(new, cands)
        if len(packed) <= e['psz']: break
    back, _ = lz5.decode(packed, len(new)); assert back == new, '왕복 실패'
    assert len(packed) <= e['psz'], ('압축 크기 넘침', len(packed), e['psz'])
    packed = packed + bytes(e['psz'] - len(packed))
    hdr = lz5.build_header(e['hb'], packed, new); assert len(hdr) == e['dp'] - e['h0']
    b = bytearray(d); b[e['h0']:e['dp']] = hdr; b[e['dp']:e['dp'] + e['psz']] = packed
    assert len(b) == len(d)
    assert bytes(b[:e['h0']]) == d[:e['h0']] and bytes(b[e['dp'] + e['psz']:]) == d[e['dp'] + e['psz']:], '범위 밖 바뀜'
    os.makedirs(os.path.dirname(OUT), exist_ok=True); open(OUT, 'wb').write(bytes(b))
    print('CMD_DATA 조각 %d개 · 압축 %d/%d B → %s' % (len(pieces()), len(packed.rstrip(b"\0")), e['psz'], OUT))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    {'preview': preview, 'build': build}[sys.argv[1]]()
