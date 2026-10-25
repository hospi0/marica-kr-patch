# -*- coding: utf-8 -*-
r"""LHA -lz5- (LArc 방식 LZSS) 풀기·묶기 + 0단계 머리 (2026-10-25, TITLE.BIN 안 «TITL_WK.DT» 등)
  고리 버퍼 4096, 시작 위치 4096−18, 초기값 = 0..255 각 13번 · 0..255 · 255..0 · 0×128 · 공백×110 (lha slide.c decode_start_lz5).
  깃발 바이트 아래 비트부터: 1 = 날 바이트 / 0 = 두 바이트 (위치 = b1 | (b2 & 0xF0) << 4, 길이 = (b2 & 0x0F) + 3) — 위치는 고리 절대 번지.
  머리(0단계): [크기 h][합][-lz5-][압축 크기 4 LE][원래 크기 4 LE][시각 4][속성 1][단계 0][이름 길이][이름][CRC16 2] — 전체 h+2 바이트.
  python tools/lz5.py 파일 → 안의 -lz5- 묶음 목록 + 풀어서 검산(CRC)"""
import struct, sys

N, F = 4096, 18


def _init():
    t = bytearray()
    for i in range(256): t += bytes([i]) * 13
    t += bytes(range(256)) + bytes(range(255, -1, -1)) + bytes(128) + b' ' * (128 - F)
    assert len(t) == N - F
    return t + bytes(F)


def decode(src, size):
    text = _init(); r = N - F; out = bytearray(); p = 0; flags = 0; nb = 0
    while len(out) < size:
        if nb == 0: flags = src[p]; p += 1; nb = 8
        bit = flags & 1; flags >>= 1; nb -= 1
        if bit:
            c = src[p]; p += 1; out.append(c); text[r] = c; r = (r + 1) % N
        else:
            b1, b2 = src[p], src[p + 1]; p += 2
            pos = b1 | ((b2 & 0xF0) << 4); ln = (b2 & 0x0F) + 3
            for k in range(ln):
                c = text[(pos + k) % N]; out.append(c); text[r] = c; r = (r + 1) % N
    return bytes(out[:size]), p


def encode(data, cands=512, safe=True):
    """LZSS 묶기 — 고리 버퍼 흉내 + 해시 후보(최근 cands 개) + 지연 일치(한 칸 뒤가 더 길면 날 바이트 하나 먼저).
       safe(기본): 데이터로 한 번도 안 쓴 고리 자리(초기값)는 참조 안 함 — 게임 해제기의 초기값이 lha 와 달라
       (2026-10-25 마리카 OP_07 이름표: 0 바이트 줄이 0x20 으로 풀려 점무늬) 해제기 초기값과 상관없이 같게.
       출력은 decode 로 왕복 검산할 것."""
    text = bytearray(_init()); r = N - F
    written = bytearray(N)
    heads = {}
    if not safe:
        written[:] = b'' * N
        for i in range(N - F - 2): heads.setdefault(bytes(text[i:i + 3]), []).append(i)
    n = len(data)

    def longest(p, r0):
        """data[p:] 를 고리(현재 상태 text, 쓰기 위치 r0)에서 찾음 → (길이, 위치)"""
        if p + 3 > n: return 0, 0
        best = (0, 0)
        for pos in reversed(heads.get(data[p:p + 3], [])[-cands:]):
            ln = 0; tmp = {}
            while ln < F and p + ln < n:
                a2 = (pos + ln) % N
                if a2 not in tmp and not written[a2]: break
                c = tmp[a2] if a2 in tmp else text[a2]
                if c != data[p + ln]: break
                tmp[(r0 + ln) % N] = data[p + ln]; ln += 1
            if ln > best[0]:
                best = (ln, pos)
                if ln == F: break
        return best

    def put(b):
        nonlocal r
        text[r] = b; written[r] = 1
        s0 = (r - 2) % N
        if written[s0] and written[(s0 + 1) % N]:
            heads.setdefault(bytes(text[(s0 + j) % N] for j in range(3)), []).append(s0)
        r = (r + 1) % N

    out = bytearray(); grp = bytearray(); flags = 0; nb = 0; p = 0
    def flush():
        nonlocal flags, nb, grp
        if nb == 8: out.append(flags); out.extend(grp); grp = bytearray(); flags = 0; nb = 0
    while p < n:
        ln, pos = longest(p, r)
        if ln >= 3 and ln < F and p + 1 < n:
            # 지연: 날 바이트 하나 뒤의 일치가 더 길면 지금은 날 바이트
            saved = text[r]; put_r = r
            text[r] = data[p]
            ln2, _ = longest(p + 1, (r + 1) % N)
            text[r] = saved
            if ln2 > ln + 1: ln = 0
        if ln >= 3:
            flags |= 0 << nb; nb += 1; grp += bytes([pos & 0xFF, ((pos >> 4) & 0xF0) | (ln - 3)])
            for k in range(ln): put(data[p + k])
            p += ln
        else:
            flags |= 1 << nb; nb += 1; grp.append(data[p]); put(data[p]); p += 1
        flush()
    if nb: out.append(flags); out += grp
    return bytes(out)


def crc16(d):
    c = 0
    for b in d:
        c ^= b
        for _ in range(8): c = (c >> 1) ^ 0xA001 if c & 1 else c >> 1
    return c


def find(d):
    """→ [(머리 위치, 이름, 압축 크기, 원래 크기, 데이터 위치, 머리 바이트)]"""
    out = []; i = d.find(b'-lz5-')
    while i >= 0:
        h0 = i - 2; h = d[h0]
        psz, osz = struct.unpack_from('<II', d, i + 5)
        nl = d[i + 19]; name = d[i + 20:i + 20 + nl].decode('latin1')
        out.append((h0, name, psz, osz, h0 + h + 2, bytes(d[h0:h0 + h + 2])))
        i = d.find(b'-lz5-', i + 1)
    return out


def build_header(old, packed, orig):
    """옛 머리를 바탕으로 크기·CRC·합을 새로"""
    h = bytearray(old)
    struct.pack_into('<II', h, 7, len(packed), len(orig))
    nl = h[21]; struct.pack_into('<H', h, 22 + nl, crc16(orig))
    h[1] = sum(h[2:]) & 0xFF
    return bytes(h)


if __name__ == '__main__':
    d = open(sys.argv[1], 'rb').read()
    for h0, name, psz, osz, dp, hb in find(d):
        nl = hb[21]; crc = struct.unpack_from('<H', hb, 22 + nl)[0]
        out, used = decode(d[dp:dp + psz], osz)
        print('%06X %-12s 압축 %d 원래 %d 쓴 %d CRC %s 합 %s' % (h0, name, psz, osz, used, crc16(out) == crc, (sum(hb[2:]) & 0xFF) == hb[1]))
