# -*- coding: utf-8 -*-
r"""음성 자막 자료 (2026-10-25): work/tr/voice.tsv(tools/tr_check.py 결과) → 글꼴(1비트 16×16·너비) + 음성 파일마다 «MSUB» 덩어리.
  · 쪽: 한 줄이 300 px 넘으면 띄어쓰기에서 나눔(넘는 낱말은 글자에서). 줄 시간은 쪽 글자 수 비율로 나눔.
  · 시간(프레임 60/초): 쪽 끝 = 다음 줄 시작(1초 넘게 비면 끝+0.5초), 마지막 줄 = 끝+0.5초 — 쪽 사이 깜빡임 없게.
  · 덩어리(빅 엔디언): 'MSUB' 크기 · u16 번호 · u16 쪽 수 · [u16 시작 · 끝 · x0 · 폭 · 글자 수 · 글자 번호…]… (AIFF 짝수 맞춤)
  · AIFF 에 넣는 자리 = COMM 덩어리 바로 뒤, FORM 크기 고침."""
import collections, os, re, struct
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
FONT = r'C:\claude\utils\font\nanum-gothic\NanumGothicBold.ttf'
PX = 15; MAXW = 300; FPS = 60


def load_rows():
    rows = []
    for ln in open(os.path.join(ROOT, 'work', 'tr', 'voice.tsv'), encoding='utf-8-sig').read().split('\n')[1:]:
        c = ln.split('\t')
        if len(c) >= 5 and c[4].strip(): rows.append((c[1], float(c[2]), float(c[3]), c[4].strip()))
    return rows


def render_glyph(ch, f, fb, S=4):
    import numpy as np
    from PIL import Image, ImageDraw
    im = Image.new('L', (16 * S, 16 * S), 0)
    top = fb.getbbox('가')[1]
    ImageDraw.Draw(im).text((0, S - top), ch, font=fb, fill=255)          # 윗선 = 1행
    cov = np.array(im.resize((16, 16), Image.BOX), float) / 255
    bits = b''.join(struct.pack('>H', sum(0x8000 >> x for x in range(16) if cov[y, x] > 0.45)) for y in range(16))
    adv = max(1, min(16, int(round(f.getlength(ch)))))
    if ch == ' ': adv = 4
    return bits, adv


GALMURI = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri14.bdf'     # 2026-10-25 하스피: 나눔 1비트는 지저분·ㅇ/ㅁ 받침 구분 안 됨 → 갈무리14


def build_font(chars):
    """갈무리14 비트맵 그대로(한글 잉크 윗선 = 1행) — 갈무리에 없는 글자만 나눔고딕 1비트로"""
    import bdf
    from PIL import ImageFont
    g = bdf.Font(GALMURI)
    ys = [y for c in '가각힣맑앙' for x, y in g.draw(c)[0]]
    top, bot = min(ys), max(ys); off = 1 - top + max(0, (14 - (bot - top + 1)) // 2)
    f = ImageFont.truetype(FONT, PX); fb = ImageFont.truetype(FONT, PX * 4)
    order = sorted(chars); idx = {c: i for i, c in enumerate(order)}
    bits, advs = [], []; miss = []
    for c in order:
        if ord(c) in g.g:
            pts, w = g.draw(c); rows = [0] * 16
            for x, y in pts:
                yy = y + off
                if 0 <= yy < 16 and 0 <= x < 16: rows[yy] |= 0x8000 >> x
            bits.append(b''.join(struct.pack('>H', r) for r in rows)); advs.append(4 if c == ' ' else max(1, min(16, w)))
        else:
            b, a = render_glyph(c, f, fb); bits.append(b); advs.append(a); miss.append(c)
    if miss: print('  갈무리14 에 없는 글자(나눔으로):', ''.join(miss))
    return idx, bits, advs


def norm_text(t):
    t = t.replace('　', ' ').replace('|', ' ')
    return re.sub(' +', ' ', t).strip()


def split_pages(t, adv):
    W = lambda s: sum(adv(c) for c in s)
    words = t.split(' '); pages = []; cur = ''
    for w in words:
        cand = (cur + ' ' + w) if cur else w
        if W(cand) <= MAXW: cur = cand; continue
        if cur: pages.append(cur); cur = ''
        while W(w) > MAXW:                                  # 너무 긴 낱말 — 글자에서
            k = len(w)
            while W(w[:k]) > MAXW: k -= 1
            pages.append(w[:k]); w = w[k:]
        cur = w
    if cur: pages.append(cur)
    return pages


def build():
    rows = load_rows()
    chars = set(''.join(norm_text(r[3]) for r in rows)) | {' '}
    idx, bits, advs = build_font(chars)
    adv = lambda c: advs[idx[c]]
    byv = collections.OrderedDict()
    for v, t0, t1, t in sorted(rows, key=lambda r: (r[0], r[1])): byv.setdefault(v, []).append((t0, t1, norm_text(t)))
    chunks = {}; npage = 0; big = 0
    for v, lines in byv.items():
        num = int(re.search(r'PCM(\d+)', v).group(1))
        pages = []
        for i, (t0, t1, t) in enumerate(lines):
            nxt = lines[i + 1][0] if i + 1 < len(lines) else None
            end = nxt if nxt is not None and nxt - t1 <= 1.0 and nxt > t0 else t1 + 0.5
            ps = split_pages(t, adv); tot = sum(len(p) for p in ps); a = t0
            for p in ps:
                b = a + (end - t0) * len(p) / tot
                pages.append((int(a * FPS), int(b * FPS), p)); a = b
        body = struct.pack('>2H', num, len(pages))
        for f0, f1, p in pages:
            w = sum(adv(c) for c in p); x0 = (320 - w) // 2
            body += struct.pack('>5H', f0, max(f1, f0 + 1), x0, w, len(p)) + b''.join(struct.pack('>H', idx[c]) for c in p)
        chunks[v] = b'MSUB' + struct.pack('>I', len(body)) + body + (b'\0' if len(body) & 1 else b'')
        npage += len(pages); big = max(big, len(body))
    return idx, bits, advs, chunks, npage, big


def insert_chunk(aif, chunk):
    assert aif[:4] == b'FORM' and aif[8:12] == b'AIFF'
    p = 12
    while p < len(aif):
        tag, sz = aif[p:p + 4], struct.unpack_from('>I', aif, p + 4)[0]
        if tag == b'COMM':
            q = p + 8 + sz + (sz & 1)
            out = bytearray(aif[:q] + chunk + aif[q:])
            struct.pack_into('>I', out, 4, struct.unpack_from('>I', aif, 4)[0] + len(chunk))
            return bytes(out)
        p += 8 + sz + (sz & 1)
    raise ValueError('COMM 없음')


def parse_chunk(c):
    """검산용 → (번호, [(시작, 끝, x0, 폭, [글자 번호])])"""
    n = struct.unpack_from('>I', c, 4)[0]; b = c[8:8 + n]
    num, np_ = struct.unpack_from('>2H', b, 0); p = 4; out = []
    for _ in range(np_):
        f0, f1, x0, w, k = struct.unpack_from('>5H', b, p); g = list(struct.unpack_from('>%dH' % k, b, p + 10)); p += 10 + 2 * k
        out.append((f0, f1, x0, w, g))
    return num, out


if __name__ == '__main__':
    import sys; sys.stdout.reconfigure(encoding='utf-8')
    idx, bits, advs, chunks, npage, big = build()
    print('글자 %d · 음성 %d · 쪽 %d · 가장 큰 덩어리 %d B · 글꼴 %d B' % (len(idx), len(chunks), npage, big, 33 * len(idx)))
