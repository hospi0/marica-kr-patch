# -*- coding: utf-8 -*-
r"""오프닝(LAST/O01.D) 그림 한글화 (2026-10-25)
  O01.D = 팔레트 32 B + LHA -lz5- 15개. 다시 묶은 덩어리가 원래 압축 크기 이하면 0 으로 채워 «모든 덩어리 위치 그대로»
  (머리의 압축 크기도 원래 값 — 풀기는 원래 크기만큼만 읽고 멈춤), 넘치면 실패.
  ① 인물 이름표: OP_07·14·21·28_WK.DT 끝 3,456 B = 144×48 4비트. 색 1 = 흰 글자, 15 = 검은 테두리, 2~14 = 흰→검 회색 경계(스샷 my files/할일/3 대조).
  ② 스태프 크레딧 OP_02·08·15·22·29.CSB (OP_01 = feycraft 로고, 그대로) ③ 두 번째 타이틀 OP_30_WK.DT 6번째 칸 부제.
  팔레트 = work/opening/pal_op_state*.npy(스테이트 work/user_states/op_title_credit, CRAM u16 바이트 뒤집힘).
  python tools/opening.py preview → work/preview/opening_names.png · opening_credits.png (원본|새것)
  python tools/opening.py build   → work/build/files/LAST/O01.D"""
import os, struct, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
import lz5

FONT = r'C:\claude\utils\font\nanum-myeongjo\NanumMyeongjoExtraBold.ttf'
NAMES = {   # 덩어리 이름: (1줄, 성우 이름)
    'OP_07_WK.DT': ('칸자키 마리카', '미야무라 유코'),
    'OP_14_WK.DT': ('카네모토 아키라', '나가시마 유코'),
    'OP_21_WK.DT': ('토도 카나메', '와타나베 쿠미코'),
    'OP_28_WK.DT': ('진실의 사람', '호리 히데유키'),
}
ROLE = '성우'
CW, CH, CARD = 144, 48, 3456
S = 8                                                    # 초표본


def load():
    d = open(os.path.join(ROOT, 'work', 'disc', 'LAST', 'O01.D'), 'rb').read()
    ents = {}
    for h0, name, psz, osz, dp, hb in lz5.find(d):
        out, _ = lz5.decode(d[dp:dp + psz], osz)
        ents[name] = dict(h0=h0, psz=psz, osz=osz, dp=dp, hb=hb, data=bytearray(out))
    return d, ents


def unpack4(b):
    a = np.frombuffer(bytes(b), np.uint8); p = np.empty(len(a) * 2, np.uint8); p[0::2] = a >> 4; p[1::2] = a & 15
    return p


def pack4(p):
    p = p.astype(np.uint8).ravel(); return bytes((p[0::2] << 4 | p[1::2]).tolist())


def text_mask(txt, px, wmax):
    """→ 초표본 마스크 — 글자 크기는 고정(네 장 같은 크기), 폭 넘으면 가로만 줄임"""
    f = ImageFont.truetype(FONT, px * S)
    bb = f.getbbox(txt); w = (bb[2] - bb[0]) / S
    sx = min(1.0, wmax / w)
    im = Image.new('L', (bb[2] - bb[0] + 4 * S, bb[3] - bb[1] + 4 * S), 0)
    ImageDraw.Draw(im).text((2 * S - bb[0], 2 * S - bb[1]), txt, font=f, fill=255)
    if sx < 1: im = im.resize((max(1, int(im.width * sx)), im.height), Image.LANCZOS)
    return np.array(im, float) / 255, px, sx


def dilate(m, r):
    """원판 팽창(scipy 없음)"""
    out = m.copy(); H_, W_ = m.shape
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy > r * r: continue
            out[max(0, dy):H_ + min(0, dy), max(0, dx):W_ + min(0, dx)] |= m[max(0, -dy):H_ + min(0, -dy), max(0, -dx):W_ + min(0, -dx)]
    return out


def compose(hi):
    """초표본 마스크(카드 크기×S) → 4비트 칸: 테두리 1.5px 검정(15), 몸통 흰(1), 경계 회색 2~14"""
    body = dilate(hi > 0.5, int(0.4 * S))                     # 원본 명조보다 획이 가늘어 살짝 굵힘
    r = int(2.0 * S)
    outl = dilate(body, r)
    cov = body.reshape(CH, S, CW, S).mean((1, 3)); oc = outl.reshape(CH, S, CW, S).mean((1, 3))
    out = np.zeros((CH, CW), np.uint8)
    out[oc >= 0.5] = 15
    lvl = np.clip(np.round(15 - cov / 0.85 * 14), 1, 15).astype(np.uint8)
    m = (oc >= 0.5) & (cov > 0.08)
    out[m] = lvl[m]
    out[cov >= 0.85] = 1
    return out


def make_card(line1, actor):
    hi = np.zeros((CH * S, CW * S), float)
    def put(mask, x, y):
        h, w = mask.shape; x0, y0 = int(x * S) - 2 * S, int(y * S) - 2 * S
        ys0, xs0 = max(0, y0), max(0, x0)
        sub = mask[ys0 - y0:min(h, CH * S - y0), xs0 - x0:min(w, CW * S - x0)]
        hi[ys0:ys0 + sub.shape[0], xs0:xs0 + sub.shape[1]] = np.maximum(hi[ys0:ys0 + sub.shape[0], xs0:xs0 + sub.shape[1]], sub)
    m1, _, _ = text_mask(line1, 19, CW - 8)
    w1 = m1.shape[1] / S - 4; h1 = m1.shape[0] / S - 4
    put(m1, (CW - w1) / 2, 2 + (20 - h1) / 2)
    mr, _, _ = text_mask(ROLE, 17, 40)
    wr = mr.shape[1] / S - 4; hr = mr.shape[0] / S - 4
    ma, _, _ = text_mask(actor, 17, CW - 8 - wr - 12)
    wa = ma.shape[1] / S - 4; ha = ma.shape[0] / S - 4
    put(mr, 3, 26 + (19 - hr) / 2)
    put(ma, CW - 3 - wa, 26 + (19 - ha) / 2)
    return compose(hi)


PAL = [(0, 0, 0)] + [(((w & 31) << 3), ((w >> 5) & 31) << 3, ((w >> 10) & 31) << 3) for w in
                     (0x7FFF, 0x739C, 0x6B5A, 0x6318, 0x5AD6, 0x4E73, 0x4631, 0x3DEF, 0x35AD, 0x2D6B, 0x2108, 0x18C6, 0x1084, 0x0842)] + [(0, 0, 0)]


def show(card, bg=(70, 40, 90)):
    im = Image.new('RGB', (CW, CH), bg); px = im.load()
    for y in range(CH):
        for x in range(CW):
            v = card[y, x]
            if v: px[x, y] = PAL[v]
    return im


# ───────── ② 스태프 크레딧 OP_xx.CSB(320×240 8비트, 흰 바탕 255 · 검은 글자 64 · 회색 경계) ─────────
# 하스피 2026-10-25: 직함·사람 이름 모두 한글(이름은 일본어 읽기 음역, 거센소리 규칙).
# 칸: (글, 왼쪽 x 또는 None, 오른쪽 x 또는 None, 세로 가운데 y, 글자 크기)
NAME_PX, ROLE_PX, SMALL_PX = 22, 22, 16
CREDITS = {
    'OP_02.CSB': [('기획', 62, None, 61.5, ROLE_PX), ('코모리 하루노부', 144, None, 61.5, NAME_PX),
                  ('오카베 아츠시', 144, None, 117.5, NAME_PX), ('타니구치 마코토', 144, None, 173.5, NAME_PX)],
    'OP_08.CSB': [('캐릭터', None, 142, 73, SMALL_PX), ('디자인', None, 142, 89, SMALL_PX), ('키노시타 타카시', 161, None, 81, NAME_PX),
                  ('음악', 80, None, 161.5, ROLE_PX), ('미야우치 노부코', 161, None, 161.5, NAME_PX)],
    'OP_15.CSB': [('콘도 세이지', 166, None, 91.5, NAME_PX), ('프로그램', None, 138, 113.5, SMALL_PX), ('히라바야시 요시마사', 166, None, 147.5, NAME_PX)],
    'OP_22.CSB': [('코노 토시미', 170, None, 30.5, NAME_PX), ('하라 히로유키', 170, None, 86.5, NAME_PX), ('CG 디자인', None, 144, 115.5, SMALL_PX),
                  ('와타나베 츠요시', 170, None, 142.5, NAME_PX), ('토모타케 젠타', 170, None, 198.5, NAME_PX)],
    'OP_29.CSB': [('각본', 64, None, 107, ROLE_PX), ('감독', 64, None, 132, ROLE_PX), ('엔도 쇼지로', 146, None, 119.5, NAME_PX)],
}
CSB_BG, RIGHT_MAX = 255, 314


def gray_ramp(pal, used):
    """쓰인 색 번호 중 무채색만 → [(밝기, 번호)] (밝기 0 = 검정)"""
    out = {}
    for i in used:
        r, g, b = (int(v) for v in pal[i])
        if r == g == b: out.setdefault(r, i)
    return sorted(out.items())


def nearest(ramp, lum):
    return min(ramp, key=lambda t: abs(t[0] - lum))[1]


def draw_line(hi, txt, xl, xr, yc, px, xmax):
    f = ImageFont.truetype(FONT, px * S); bb = f.getbbox(txt)
    w = (bb[2] - bb[0]) / S; h = (bb[3] - bb[1]) / S
    x0 = xl if xl is not None else xr - w
    sx = 1.0
    if x0 + w > xmax: sx = (xmax - x0) / w; assert sx >= 0.7, (txt, '너무 김', sx)
    im = Image.new('L', (bb[2] - bb[0], bb[3] - bb[1]), 0)
    ImageDraw.Draw(im).text((-bb[0], -bb[1]), txt, font=f, fill=255)
    if sx < 1: im = im.resize((int(im.width * sx), im.height), Image.LANCZOS)
    m = dilate(np.array(im) > 127, int((0.35 if px >= 18 else 0.15) * S)).astype(float)   # 원본 굵은 명조만큼(작은 글자는 속 막힘 막게 조금만)
    X, Y = int(x0 * S), int((yc - h / 2) * S)
    sub = m[:hi.shape[0] - Y, :hi.shape[1] - X]
    hi[Y:Y + sub.shape[0], X:X + sub.shape[1]] = np.maximum(hi[Y:Y + sub.shape[0], X:X + sub.shape[1]], sub)


def make_credit(old, items, pal):
    img = np.frombuffer(bytes(old), np.uint8).reshape(240, 320).copy()
    ramp = gray_ramp(pal, set(img.flatten().tolist()))
    ramp = [ramp[i] for i in np.linspace(0, len(ramp) - 1, 6).round().astype(int)]   # 경계 6단계 — 단계가 많으면 다시 묶은 크기가 원래 자리를 넘침(OP_02)
    img[:] = CSB_BG
    hi = np.zeros((240 * S, 320 * S), float)
    for txt, xl, xr, yc, px in items: draw_line(hi, txt, xl, xr, yc, px, RIGHT_MAX)
    cov = hi.reshape(240, S, 320, S).mean((1, 3))
    bgl = int(pal[CSB_BG][0])
    for y, x in zip(*np.where(cov > 0.06)):
        img[y, x] = nearest(ramp, bgl * (1 - cov[y, x]))
    return bytes(img)


# ───────── ③ 두 번째 타이틀(OP_30_WK.DT 6번째 칸 = 행 1200~): 부제 «真実の世界» → «진실의 세계» (〜 는 원본) ─────────
T_OFF = 1200 * 320
T_Y0, T_Y1, T_X0, T_X1 = 134, 160, 89, 230                # 지우는 칸(양쪽 〜 바깥)
T_TEXT = '진실의 세계'
T_FONT = r'C:\claude\utils\font\nanum-gothic\NanumGothicExtraBold.ttf'   # 명조를 속 빈 글자로 하면 가는 획이 뭉개짐 → 첫 타이틀과 같은 고딕


def make_title(old_slot, pal):
    """첫 타이틀(tools/title_logo.py)과 같은 글자 모양(glyph_masks)을 이 로고 색으로: 몸통 = 바탕 흰색(속 빈 글자), 가장자리 = 중간 회색, 테두리 = 검정
       (2026-10-25 하스피 «두 번째도 첫 번째랑 맞춰»)"""
    import title_logo as TL
    img = np.frombuffer(bytes(old_slot), np.uint8).reshape(240, 320).copy()
    ramp = gray_ramp(pal, set(img[T_Y0:T_Y1].flatten().tolist())); bg = 1
    img[T_Y0:T_Y1, T_X0:T_X1] = bg
    fill, edge, ring = TL.glyph_masks()
    h, w = fill.shape
    y0 = 135; x0 = 160 - w // 2                                  # 원본 부제 잉크 행 136~157 · 가운데 열 160
    for m, lum in ((ring, 0), (edge, 128)):
        for y, x in zip(*np.where(m)):
            yy, xx = y0 + y, x0 + x
            if T_Y0 <= yy < T_Y1 and T_X0 <= xx < T_X1: img[yy, xx] = nearest(ramp, lum)
    return bytes(img)


def palettes():
    return (np.load(os.path.join(ROOT, 'work', 'opening', 'pal_op_state.npy')),       # 크레딧(스테이트 op_title_credit/.state, 색 뱅크 0x100)
            np.load(os.path.join(ROOT, 'work', 'opening', 'pal_op_state1.npy')))      # 두 번째 타이틀(.state1, 뱅크 0x600)


def rgb(img8, pal, w=320, h=240):
    return Image.fromarray(pal[np.frombuffer(bytes(img8), np.uint8).reshape(h, w)])


def new_data(ents):
    pc, pt = palettes(); res = {}
    for name, (l1, act) in NAMES.items():
        new = bytearray(ents[name]['data']); new[-CARD:] = pack4(make_card(l1, act)); res[name] = new
    for name, items in CREDITS.items(): res[name] = bytearray(make_credit(ents[name]['data'], items, pc))
    new = res.get('OP_30_WK.DT') or bytearray(ents['OP_30_WK.DT']['data'])
    new[T_OFF:T_OFF + 76800] = make_title(new[T_OFF:T_OFF + 76800], pt); res['OP_30_WK.DT'] = new
    return res


def preview_credits(ents):
    pc, pt = palettes()
    sheet = Image.new('RGB', (648, 246 * (len(CREDITS) + 1)), (128, 128, 128))
    for k, (name, items) in enumerate(CREDITS.items()):
        old = ents[name]['data']; sheet.paste(rgb(old, pc), (0, 246 * k)); sheet.paste(rgb(make_credit(old, items, pc), pc), (328, 246 * k))
    slot = ents['OP_30_WK.DT']['data'][T_OFF:T_OFF + 76800]
    k = len(CREDITS); sheet.paste(rgb(slot, pt), (0, 246 * k)); sheet.paste(rgb(make_title(slot, pt), pt), (328, 246 * k))
    out = os.path.join(ROOT, 'work', 'preview', 'opening_credits.png'); sheet.resize((1296, sheet.height * 2), Image.NEAREST).save(out); print(out)


def preview():
    d, ents = load()
    preview_credits(ents)
    rows = []
    for name, (l1, act) in NAMES.items():
        old = unpack4(ents[name]['data'][-CARD:]).reshape(CH, CW)
        new = make_card(l1, act)
        im = Image.new('RGB', (CW * 2 + 8, CH), (255, 255, 255))
        im.paste(show(old), (0, 0)); im.paste(show(new), (CW + 8, 0)); rows.append(im)
    sheet = Image.new('RGB', (CW * 2 + 8, (CH + 6) * len(rows)), (255, 255, 255))
    for k, im in enumerate(rows): sheet.paste(im, (0, k * (CH + 6)))
    out = os.path.join(ROOT, 'work', 'preview', 'opening_names.png')
    sheet.resize((sheet.width * 3, sheet.height * 3), Image.NEAREST).save(out); print(out)


def build():
    d, ents = load()
    b = bytearray(d)
    for name, new in new_data(ents).items():
        e = ents[name]
        for cands in (512, 2048, 8192):                          # 원래 압축 크기 넘치면 후보를 늘려 더 촘촘히(OP_28 = 2048 에서 들어감)
            packed = lz5.encode(bytes(new), cands)
            if len(packed) <= e['psz']: break
        back, _ = lz5.decode(packed, len(new)); assert back == bytes(new), '왕복 실패'
        assert len(packed) <= e['psz'], (name, '압축 크기 넘침', len(packed), e['psz'])
        packed = packed + bytes(e['psz'] - len(packed))
        hdr = lz5.build_header(e['hb'], packed, bytes(new))
        assert len(hdr) == e['dp'] - e['h0']
        b[e['h0']:e['dp']] = hdr; b[e['dp']:e['dp'] + e['psz']] = packed
    assert len(b) == len(d)
    # 검산: 다시 풀어 같은지·위치 그대로
    for h0, name, psz, osz, dp, hb in lz5.find(bytes(b)):
        assert h0 == ents[name]['h0'] and dp == ents[name]['dp']
    out = os.path.join(ROOT, 'work', 'build', 'files', 'LAST', 'O01.D'); os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'wb').write(bytes(b)); print('→', out)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    {'preview': preview, 'build': build}[sys.argv[1]]()
