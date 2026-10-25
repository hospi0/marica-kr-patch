# -*- coding: utf-8 -*-
r"""백업 램 안내 화면 그림 한글화 (2026-10-25) — TITLE.BIN 안 LHA -lz5- «TITL_WK1.DT»(192,576 B)
  앞 160×240 8비트 = 그림(그대로), 바이트 38,400~ = 320 폭 4비트 글자 판: 문구 11덩어리(겹치는 것 빼면 7종).
  꼴: 색 1 = 흰 1px 획, 15 = 테두리(8방향 1px), 2·3 = «!» 아이콘(그대로). 바탕 = 위쪽은 4·0 격자(짝수 열 4), 아래쪽(덩어리 10·11)은 0.
  덩어리 10·11 의 둘째 줄 «MARICA_» 는 게임이 뒤에 파일 이름을 찍을 수 있어 원본 그대로.
  글꼴 = 갈무리11(원본처럼 1px 획) — 줄 시작 x·줄 윗선은 원본 줄 그대로.
  다시 묶은 lz5 가 원래 압축 크기 이하면 0 으로 채워 같은 자리(넘치면 실패).
  python tools/backup_msg.py preview → work/preview/backup_msg.png (원본|새것)
  python tools/backup_msg.py build   → work/build/TITLE_wk1.BIN (build_text 가 바뀐 바이트만 합침)"""
import os, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
import lz5, bdf

GALMURI = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri11.bdf'
GALMURI_C = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri11-Condensed.bdf'
TXT0, W = 240 * 160, 320
A = ['카트리지 RAM이 초기화되어 있지 않습니다.', '카트리지 RAM을 초기화하고', '다시 시도해 주십시오.']
B = ['본체 RAM과 카트리지 RAM의', '저장 공간이 부족합니다.', '저장 데이터를 정리하고', '다시 시도해 주십시오.']
C = ['본체 RAM의 저장 공간이 부족합니다.', '저장 데이터를 정리하고 다시 시도해 주십시오.']
D = ['본체 RAM이 초기화되어 있지 않습니다.', '본체 RAM을 초기화하고 다시 시도해 주십시오.']
E = ['카트리지 RAM의 저장 공간이', '부족합니다.', '저장 데이터를 정리하고 다시 시도해 주십시오.']
F = ['본체 RAM과 카트리지 RAM이', '초기화되어 있지 않습니다.', '본체 RAM과 카트리지 RAM을', '초기화하고 다시 시도해 주십시오.']
G1 = ['본체 RAM의 데이터', None, '는 데이터가 손상되어 유감스럽게도', '사용할 수 없습니다.', '데이터를 지우고 다시 시도해 주십시오.']
G2 = ['카트리지 RAM의 데이터', None, '는 데이터가 손상되어 유감스럽게도', '사용할 수 없습니다.', '데이터를 지우고 다시 시도해 주십시오.']
# 덩어리: 글자 판 행 범위(원본 잉크, 판 행 기준) → 문구(None = 그 줄 원본 그대로)
BLOCKS = [((7, 52), A), ((104, 163), B), ((194, 225), C), ((236, 281), A), ((294, 325), D), ((386, 417), D),
          ((428, 473), E), ((485, 544), F), ((583, 614), C), ((772, 853), G1), ((868, 949), G2)]


def load():
    d = open(os.path.join(ROOT, 'work', 'disc', 'TITLE.BIN'), 'rb').read()
    for h0, name, psz, osz, dp, hb in lz5.find(d):
        if name == 'TITL_WK1.DT':
            out, _ = lz5.decode(d[dp:dp + psz], osz)
            return d, (h0, psz, dp, hb), bytearray(out)
    raise SystemExit('TITL_WK1.DT 없음')


def plane(wk):
    t = np.frombuffer(bytes(wk[TXT0:]), np.uint8); p = np.empty(len(t) * 2, np.uint8); p[0::2] = t >> 4; p[1::2] = t & 15
    n = len(p) // W
    return p[:n * W].reshape(n, W).copy()                      # 끝 자투리(행 안 됨)는 unplane 이 그대로 둠


def unplane(wk, a):
    p = a.ravel(); b = bytes((p[0::2] << 4 | p[1::2]).tolist()); wk[TXT0:TXT0 + len(b)] = b


def lines_of(a, y0, y1, n, icx):
    """덩어리 안 글자 줄: [(윗행, 아랫행, 시작 x)] — 줄끼리 테두리가 붙어 있어 덩어리 높이를 줄 수로 고르게 나눔(원본 줄 간격 15~16행)"""
    rows = [y for y in range(y0, y1 + 1) if ((a[y] == 1) | (a[y] == 15)).any()]
    segs = []; s = p = rows[0]
    for y in rows[1:] + [None]:                                  # 빈 행으로 먼저 나눔(덩어리 10·11), 안 맞으면 고르게
        if y is None or y > p + 1: segs.append((s, p)); s = y
        if y is not None: p = y
    if len(segs) != n:
        h = (y1 - y0 + 1) / n; segs = [(y0 + round(k * h), y0 + round((k + 1) * h) - 1) for k in range(n)]
    out = []
    for t, b in segs:
        xs = [x for x in np.where((a[t:b + 1] == 1).any(0))[0] if x > icx]
        out.append((t, b, min(xs)))
    return out


def bg_val(a, y, x, low):
    return 0 if low else (4 if x % 2 == 0 else 0)


def make(wk):
    a = plane(wk)
    f1, f2 = bdf.Font(GALMURI), bdf.Font(GALMURI_C)
    ys = [y for c in '가각힣' for x, y in f1.draw(c)[0]]; gtop = min(ys)
    for (y0, y1), msg in BLOCKS:
        low = y0 >= 700
        # «!» 아이콘 열(2·3 색이 있는 열)은 둠 — 아이콘 오른쪽 끝 + 2 부터 지움
        icon = np.where(((a[y0:y1 + 1] == 2) | (a[y0:y1 + 1] == 3)).any(0))[0]
        icx = icon.max() + 2 if len(icon) else 0
        ls = lines_of(a, y0, y1, len(msg), icx)
        for (t, b, x0), txt in zip(ls, msg):
            if txt is None: continue
            for y in range(t, b + 1):
                for x in range(max(x0 - 1, icx), W): a[y, x] = bg_val(a, y, x, low)
            for f in (f1, f2):
                pts, w = f.draw(txt)
                if x0 + w + 1 <= W: break
            assert x0 + w + 1 <= W, (txt, '폭 넘침', x0 + w)
            ink = np.zeros((b - t + 3, W + 2), bool)
            for x, y in pts:
                yy = y - gtop + 1 + max(0, ((b - t + 1) - 2 - 11) // 2); xx = x0 + x + 1
                if 0 <= yy < ink.shape[0] and 0 <= xx < W + 2: ink[yy, xx] = True
            ring = np.zeros_like(ink)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ring[max(0, dy):ink.shape[0] + min(0, dy), max(0, dx):ink.shape[1] + min(0, dx)] |= ink[max(0, -dy):ink.shape[0] + min(0, -dy), max(0, -dx):ink.shape[1] + min(0, -dx)]
            ring &= ~ink
            for yy, xx in zip(*np.where(ring | ink)):
                y, x = t - 1 + yy, xx - 1
                if t <= y <= b and max(x0 - 1, icx) <= x < W: a[y, x] = 1 if ink[yy, xx] else 15
    out = bytearray(wk); unplane(out, a); return out


PAL = {0: (40, 40, 40), 4: (90, 90, 90), 1: (255, 255, 255), 15: (0, 0, 0), 2: (200, 200, 200), 3: (150, 150, 150)}


def show(wk):
    a = plane(wk); im = Image.new('RGB', (W, a.shape[0])); px = im.load()
    for y in range(a.shape[0]):
        for x in range(W): px[x, y] = PAL.get(int(a[y, x]), (255, 0, 255))
    return im


def preview():
    d, meta, wk = load(); new = make(wk)
    o, n = show(wk), show(new)
    sheet = Image.new('RGB', (W * 2 + 8, o.height), (255, 255, 255)); sheet.paste(o, (0, 0)); sheet.paste(n, (W + 8, 0))
    out = os.path.join(ROOT, 'work', 'preview', 'backup_msg.png'); sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST).save(out); print(out)


def build():
    d, (h0, psz, dp, hb), wk = load(); new = make(wk)
    packed = lz5.encode(bytes(new)); back, _ = lz5.decode(packed, len(new)); assert back == bytes(new), '왕복 실패'
    assert len(packed) <= psz, ('압축 크기 넘침', len(packed), psz)
    packed += bytes(psz - len(packed))
    hdr = lz5.build_header(hb, packed, bytes(new)); assert len(hdr) == dp - h0
    b = bytearray(d); b[h0:dp] = hdr; b[dp:dp + psz] = packed
    out = os.path.join(ROOT, 'work', 'build', 'TITLE_wk1.BIN'); open(out, 'wb').write(bytes(b))
    print('TITL_WK1.DT %d B → 압축 %d B(원래 %d) → %s' % (len(new), len(packed.rstrip(b'\0')), psz, out))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    {'preview': preview, 'build': build}[sys.argv[1]]()
