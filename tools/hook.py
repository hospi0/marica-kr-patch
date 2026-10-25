# -*- coding: utf-8 -*-
r"""마리카 음성 자막 훅 PoC (2026-10-25) — SBL 게임, VDP1 스프라이트 자막.
  · 음성 시작: 재생 함수 0x06003BE4(r4 = 번호)를 부르는 리터럴 2곳(0x060217B0·0x0602BC24) → vwrap(번호 기록·프레임 0) → 원래 함수.
  · 매 프레임: VBlank-OUT 등록 리터럴 0x06002318(원래 0x060020F8) → vbo(sub → 원래 처리기).
      SBL VDP1: 게임이 한 프레임 동안 명령표를 다 쓰고 «준비됨»(0x0607A5CC ≠ 0)을 켜면, VBlank-OUT 처리기(0x0606A7EA)가 FBCR 로 전환을 건다
      → 원래 처리기 «앞»에서, 준비됨일 때만 명령표를 고친다(완성됐고 아직 안 그림).
  · sub: 재생 중(0x0604D480 ≠ 0)이면 프레임 +1 → 표(번호·시작·끝 프레임·그림 번호)에서 쪽 → 바뀌면 4비트 그림(320×24)을 VDP1 0x76800 에 복사,
      CRAM 0x3F1‥0x3F3(검정·흰·회색 — 스테이트 15개 모두 빈 16색 묶음 63) → 명령표를 점프 따라 END 까지 가서 그 칸을 «건너뛰고 점프(0x5000) → OWN»,
      OWN(0x77FC0) = 우리 스프라이트 + END. 안 맞으면(재생 끝·쪽 없음) 고친 칸이 아직 우리 점프면 END 로 되돌림.
  · 스프라이트: 보통 스프라이트 PMOD 0x0080(4비트 색 뱅크·끝 코드 끔) · COLR 0x60F0(종류 3 우선순위 번호 3 = PRISB 위 7, 색 = 0x300+0xF0+화소) · 화면 320×240(지역 0,0).
  · 자리: 코드·자료 BLOCK = 0x06083C00(스테이트 15개 모두 0, MAC·MAP 은 Low RAM) — SEN.BIN(0x06002000, BOOT 가 크기 −1 로 통째 읽음) 뒤에 0 채워 붙임."""
import json, os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
from sh2asm import A

SEN_BASE = 0x06002000
BLOCK = 0x06083C00
VAR = BLOCK + 0x10                      # 0 cur · 4 frames · 8 shown · 12 patched · 0x20 견본 64 B
CODE = BLOCK + 0x80
PLAY = 0x0604D480; READY = 0x0607A5CC
VOICE = 0x06003BE4; VOICE_LITS = (0x060217B0, 0x0602BC24)
VOICE2 = 0x06003E2C; VOICE2_LITS = (0x06006A20,)      # ★두 번째 재생 함수(재생 중이면 멈추고 새로 엶, 0x060069EC 가 부름) — 첫 PoC 실기 «자막 안 뜸» = 이 경로(번호 0 그대로)
VBO = 0x060020F8; VBO_LIT = 0x06002318
LIST = 0x25C00000
TEX = 0x25C76800; TEXA = (TEX & 0x7FFFF) >> 3
OWN = 0x25C77FC0; OWNL = (OWN & 0x7FFFF) >> 3
CRAM = 0x25F00000 + 0x3F0 * 2
W_, H_ = 320, 24; BMPSZ = W_ * H_ // 2
COLR = 0x60F0; YA = 240 - H_ - 6


def code(table_at, bmps_at):
    a = A(CODE); W = a.w
    # vwrap
    a.L('vwrap'); a.ld(1, VAR); W(0x2142, 0xE000, 0x1101); a.ld(0, VOICE); W(0x402B, 0x0009)
    a.L('vwrap2'); a.ld(1, VAR); W(0x2142, 0xE000, 0x1101); a.ld(0, VOICE2); W(0x402B, 0x0009)
    # vbo
    a.L('vbo'); W(0x4F22); a.br('bsr', 'sub'); W(0x0009); a.ld(0, VBO); W(0x400B, 0x0009, 0x4F26, 0x000B, 0x0009)
    # sub
    a.L('sub'); a.ld(6, VAR)
    a.ld(1, PLAY); W(0x6010, 0x2008); a.br('bt', 'off')
    W(0x5361, 0x7301, 0x1631, 0x6262)                       # frames += 1 → r3, r2 = cur
    a.ld(1, table_at)
    a.L('tl'); W(0x6011, 0x600D); a.ld(5, 0xFFFF); W(0x3050); a.br('bt', 'off')
    W(0x3020); a.br('bf', 'tn')
    W(0x8511, 0x600D, 0x3302); a.br('bf', 'tn')            # frames >= 시작
    W(0x8512, 0x600D, 0x3302); a.br('bt', 'tn')            # frames >= 끝 → 다음
    W(0x8513, 0x640D); a.br('bra', 'show'); W(0x0009)
    a.L('tn'); W(0x7108); a.br('bra', 'tl'); W(0x0009)
    a.L('show'); W(0x5062, 0x3040); a.br('bt', 'crm')
    a.ld(1, BMPSZ); W(0x214E, 0x011A); a.ld(0, bmps_at); W(0x310C)
    a.ld(2, TEX); a.ld(5, BMPSZ // 2)
    a.L('cp'); W(0x6015, 0x2201, 0x7202, 0x4510); a.br('bf', 'cp')
    W(0x1642)
    # ★색은 매 프레임(PoC 2차 실기 «빈 검은 띠» = 게임이 포트레이트 바꿀 때 CRAM 을 다시 써 흰 글자 칸이 0 이 됨)
    a.L('crm'); a.ld(2, CRAM); a.ld(0, 0x0000); W(0x8121); a.ld(0, 0x7FFF); W(0x8122); a.ld(0, 0x4A52); W(0x8123)
    a.L('link'); a.ld(1, READY); W(0x6012, 0x2008); a.br('bt', 'ret')
    a.ld(1, LIST); W(0xE700); a.ld(5, 3000)
    a.L('wl'); W(0x6011, 0x4011); a.br('bf', 'isend')
    W(0x4019, 0x4009, 0x4009, 0xC903)
    W(0x8801); a.br('bt', 'jmp')
    W(0x8802); a.br('bt', 'call')
    W(0x8803); a.br('bt', 'retn')
    W(0x7120); a.br('bra', 'wn'); W(0x0009)
    a.L('call'); W(0x6713, 0x7720)
    a.L('jmp'); W(0x8511, 0x600D, 0x4008, 0x4000); a.ld(1, LIST); W(0x310C); a.br('bra', 'wn'); W(0x0009)
    a.L('retn'); W(0x6173)
    a.L('wn'); W(0x4510); a.br('bf', 'wl'); a.br('bra', 'ret'); W(0x0009)
    a.L('isend'); a.ld(2, OWN + 32); W(0x3120); a.br('bt', 'ret')
    W(0x6263, 0x7220); a.ld(3, OWN); W(0xE520)
    a.L('tc'); W(0x6025, 0x2301, 0x7302, 0x4510); a.br('bf', 'tc')
    a.ld(0, 0x5000); W(0x2101); a.ld(0, OWNL); W(0x8111); W(0x1613)
    a.L('ret'); W(0x000B, 0x0009)
    a.L('off'); W(0x5163, 0x2118); a.br('bt', 'off2')
    W(0x6011, 0x600D); a.ld(2, 0x5000); W(0x3020); a.br('bf', 'off1')
    W(0x8511, 0x600D); a.ld(2, OWNL); W(0x3020); a.br('bf', 'off1')
    a.ld(0, 0x8000); W(0x2101)
    a.L('off1'); W(0xE000, 0x1603)
    a.L('off2'); W(0xE0FF, 0x1602, 0x000B, 0x0009)
    return a


def render(text):
    """한 줄 → 4비트 그림(1 검정 띠 · 2 흰 글자 · 3 회색 가장자리, 0 투명)"""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype(r'C:\claude\utils\font\nanum-gothic\NanumGothicBold.ttf', 15)
    S = 4; fb = ImageFont.truetype(r'C:\claude\utils\font\nanum-gothic\NanumGothicBold.ttf', 15 * S)
    w = int(fb.getlength(text) / S) + 1
    assert w <= W_ - 12, (text, w)
    im = Image.new('L', (W_ * S, H_ * S), 0); bb = fb.getbbox('가')
    ImageDraw.Draw(im).text(((W_ - w) // 2 * S, (H_ * S - (bb[3] - bb[1])) // 2 - bb[1]), text, font=fb, fill=255)
    cov = np.array(im.resize((W_, H_), Image.BOX), float) / 255
    px = np.zeros((H_, W_), np.uint8)
    x0 = max(0, (W_ - w) // 2 - 6); x1 = min(W_, (W_ + w) // 2 + 6)
    px[1:H_ - 1, x0:x1] = 1
    px[(cov > 0.25) & (px == 1)] = 3; px[(cov > 0.55) & (px > 0)] = 2
    flat = px.ravel()
    return bytes((flat[i] << 4) | flat[i + 1] for i in range(0, len(flat), 2)), px


def load_subs():
    """data/poc_subs.tsv: 음성 번호 · 시작초 · 끝초 · 한글 — 쪽은 다음 쪽 시작까지 이어 보여 줌(깜빡임 없게), 마지막은 끝+0.5초"""
    rows = []
    for ln in open(os.path.join(ROOT, 'data', 'poc_subs.tsv'), encoding='utf-8').read().split('\n')[1:]:
        if ln.strip():
            v, t0, t1, k = ln.split('\t'); rows.append((int(v), float(t0), float(t1), k))
    out = []
    for i, (v, t0, t1, k) in enumerate(rows):
        nxt = rows[i + 1] if i + 1 < len(rows) and rows[i + 1][0] == v else None
        end = nxt[1] if nxt else t1 + 0.5
        out.append((v, int(t0 * 60), int(end * 60), k))
    return out


def block():
    subs = load_subs()
    texts = []; table = bytearray()
    for v, f0, f1, k in subs:
        if k not in texts: texts.append(k)
        table += struct.pack('>4H', v, f0, f1, texts.index(k))
    table += b'\xFF\xFF' + bytes(6)
    a0 = code(0x0A0B0C00, 0x0D0E0F00); n0 = len(a0.build())  # 크기 재기(다른 리터럴과 안 겹치는 임시값)
    table_at = CODE + ((n0 + 3) & ~3)
    bmps_at = (table_at + len(table) + 15) & ~15
    a = code(table_at, bmps_at); c = a.build(); assert len(c) == n0
    blk = bytearray(bmps_at - BLOCK)
    blk[0:4] = b'MSUB'
    struct.pack_into('>4I', blk, VAR - BLOCK, 0, 0, 0xFFFFFFFF, 0)
    tpl = struct.pack('>16H', 0x0000, 0, 0x0080, COLR, TEXA, (W_ // 8) << 8 | H_, 0, YA, 0, 0, 0, 0, 0, 0, 0, 0) + struct.pack('>16H', 0x8000, *[0] * 15)
    blk[VAR - BLOCK + 0x20:VAR - BLOCK + 0x60] = tpl
    blk[CODE - BLOCK:CODE - BLOCK + len(c)] = c
    blk[table_at - BLOCK:table_at - BLOCK + len(table)] = table
    for k in texts: blk += render(k)[0]
    return bytes(blk), a.lab, texts, subs


def patch_sen(sen):
    blk, lab, texts, subs = block()
    s = bytearray(sen)
    for lit in VOICE_LITS:
        assert struct.unpack_from('>I', s, lit - SEN_BASE)[0] == VOICE; struct.pack_into('>I', s, lit - SEN_BASE, lab['vwrap'])
    for lit in VOICE2_LITS:
        assert struct.unpack_from('>I', s, lit - SEN_BASE)[0] == VOICE2; struct.pack_into('>I', s, lit - SEN_BASE, lab['vwrap2'])
    assert struct.unpack_from('>I', s, VBO_LIT - SEN_BASE)[0] == VBO; struct.pack_into('>I', s, VBO_LIT - SEN_BASE, lab['vbo'])
    assert len(s) <= BLOCK - SEN_BASE
    s += bytes(BLOCK - SEN_BASE - len(s)); s += blk
    assert BLOCK + len(blk) <= 0x0609E000, hex(BLOCK + len(blk))     # 빈 구간 0x06083C00‥0x0609E000 안
    return bytes(s), lab, texts, subs


if __name__ == '__main__':
    sen = open(os.path.join(ROOT, 'work', 'disc', 'SEN.BIN'), 'rb').read()
    s, lab, texts, subs = patch_sen(sen)
    print('SEN.BIN %d → %d B · 자막 %d쪽(그림 %d) · 코드 %s' % (len(sen), len(s), len(subs), len(texts), ' '.join('%s=%08X' % kv for kv in lab.items() if kv[0] in ('vwrap', 'vbo', 'sub'))))
