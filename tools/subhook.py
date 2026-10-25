# -*- coding: utf-8 -*-
r"""마리카 음성 자막 본 훅 (2026-10-25) — hook.py(PoC, 미리 그린 그림) 를 «실행 중 글자 찍기»로 바꾼 것.
  · 자막 자료는 음성 파일마다 AIFF 덩어리 «MSUB»(COMM 바로 뒤)에 넣는다(tools/subdata.py). 디스크를 따로 읽지 않음.
      게임 PCM 라이브러리 AIFF 해석기(0x06079E00)는 덩어리를 차례로 건너뛰다 «APCM» 이름(문자열 0x0607C6EC)이면
      콜백 @0x0607C5EC 를 r4=작업, r5=덩어리 주소로 부르고 해석을 끝낸다 → 이름을 «MSUB» 로 바꾸고 콜백을 우리 cb 로:
      cb 가 덩어리를 SUBBUF 로 베끼고 PR 을 0x06079F36(다음 덩어리 계속)으로 바꿔 돌아감 → COMM·SSND 해석은 그대로.
      덩어리가 아직 다 안 실렸으면(다음 위치 @(8,r15) > 실린 양 @(60,r11)) PR = 0x06079F54(−1 = 나중에 다시 해석).
      ★해석기는 버퍼를 16비트로만 읽는다(사운드 램일 수 있음) → cb 도 mov.w 로만 읽음.
  · vwrap/vwrap2: 번호 기록·프레임 0·자료 무효 + 콜백 자리 다시 씀 → 원래 재생 함수.
  · vbo(VBlank-OUT) → sub: 재생 중이면 프레임 +1, SUBBUF 에서 쪽(시작 ≤ 프레임 < 끝) 찾기 → 바뀌면 render → TEX 복사.
      render: COMP(320×24 4비트) 지우고 띠(색 1, 글자 폭 ±6, 행 1~22) → 글자마다 1비트 16×16 글꼴(FONT)을 그림자(색 3, +1,+1, 띠 위에만)·흰 글자(색 2)로.
  · 색·VDP1 명령표 연결(END 점프 → OWN)은 PoC(hook.py)와 같음.
  SUBBUF 꼴(빅 엔디언 u16): 번호 · 쪽 수 · [시작 프레임 · 끝 프레임 · x0 · 폭 · 글자 수 · 글자 번호…]…"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
from sh2asm import A
import hook as P

BLOCK = P.BLOCK
VAR = BLOCK + 0x10                      # 0 cur · 4 frames · 8 shown · 12 patched · 16 valid · 0x20 견본 64 B
CODE = BLOCK + 0x80
PLAY, READY, VOICE, VOICE2, VBO = P.PLAY, P.READY, P.VOICE, P.VOICE2, P.VBO
TAG_AT = 0x0607C6EC                     # «APCM» → «MSUB»
CB_AT = 0x0607C5EC                      # APCM 콜백 자리(실행 중 0x06079DEC)
CONT, RETRY = 0x06079F36, 0x06079F54
LIST, TEX, TEXA, OWN, OWNL, CRAM, COLR = P.LIST, P.TEX, P.TEXA, P.OWN, P.OWNL, P.CRAM, P.COLR
W_, H_ = 320, 24; ROWB = W_ // 2; BMPSZ = ROWB * H_
YA = P.YA; GY = 4                       # 글자 윗줄(24 줄 띠 안 4~19)
SUBMAX = 0xC00                          # 가장 큰 덩어리 2,922 B(+8)
GR0, GROWS = 1, 14                      # 글꼴 칸은 16행 중 1~14행만 저장(28 B) — 갈무리14 잉크 행 1~14
FONT_B = 2 * GROWS
RAM_END = 0x0608D000                    # ★SEN.BIN 0x0600FA48: 얼굴(?) 파일을 0x0608D000 + 번호×0x11000 에 실음 → 블록은 이 아래만(2026-10-25 실기 거리 장면에서 글꼴 덮임)


# ───────── SH-2 니모닉(쓰는 것만) ─────────
class S(A):
    """A + 중간 리터럴 풀(ltorg) — mov.l @(d,PC) 는 1 KB 안이라 긴 코드는 풀을 나눠 둔다"""
    def __init__(s, base): super().__init__(base); s.pools = []; s.cur = []
    def ld(s, rn, val): s.fix.append((len(s.c), 'lit', (rn, val, len(s.pools)))); s.c.append(0); s.cur.append(val)
    def ltorg(s):
        """여기에 지금까지 쓴 리터럴을 둠 — 바로 앞이 무조건 분기·rts(지연 칸 포함) 뒤여야 함"""
        if (s.base + 2 * len(s.c)) % 4: s.c.append(0x0009)
        vals = list(dict.fromkeys(s.cur)); s.pools.append((len(s.c), vals)); s.c.extend([0, 0] * len(vals)); s.cur = []
    def build(s):
        if s.cur: s.ltorg()
        def val(v): return s.lab[v] if isinstance(v, str) else v
        for k, (at, vals) in enumerate(s.pools):
            for j, v in enumerate(vals):
                x = val(v) & 0xFFFFFFFF; s.c[at + 2 * j] = x >> 16; s.c[at + 2 * j + 1] = x & 0xFFFF
        for i, op, a in s.fix:
            pc = s.base + 2 * i
            if op == 'lit':
                rn, v, pk = a; at, vals = s.pools[pk]
                la = s.base + 2 * at + 4 * vals.index(v)
                d = la - ((pc & ~3) + 4); assert d >= 0 and d % 4 == 0 and d // 4 < 256, (hex(pc), d); s.c[i] = 0xD000 | (rn << 8) | d // 4
            else:
                d = (s.lab[a] - (pc + 4)) // 2
                if op in ('bra', 'bsr'): assert -2048 <= d < 2048; s.c[i] = (0xA000 if op == 'bra' else 0xB000) | (d & 0xFFF)
                else: assert -128 <= d < 128, (op, a, d); s.c[i] = {'bt': 0x8900, 'bf': 0x8B00, 'bts': 0x8D00, 'bfs': 0x8F00}[op] | (d & 0xFF)
        return b''.join(struct.pack('>H', x) for x in s.c)

    def mov(s, m, n): s.w(0x6003 | n << 8 | m << 4)
    def movi(s, i, n): s.w(0xE000 | n << 8 | (i & 0xFF))
    def addi(s, i, n): s.w(0x7000 | n << 8 | (i & 0xFF))
    def add(s, m, n): s.w(0x300C | n << 8 | m << 4)
    def sub(s, m, n): s.w(0x3008 | n << 8 | m << 4)
    def ldb(s, m, n): s.w(0x6000 | n << 8 | m << 4)          # mov.b @Rm,Rn
    def ldw(s, m, n): s.w(0x6001 | n << 8 | m << 4)
    def ldl(s, m, n): s.w(0x6002 | n << 8 | m << 4)
    def ldwp(s, m, n): s.w(0x6005 | n << 8 | m << 4)         # mov.w @Rm+,Rn
    def stb(s, m, n): s.w(0x2000 | n << 8 | m << 4)          # mov.b Rm,@Rn
    def stw(s, m, n): s.w(0x2001 | n << 8 | m << 4)
    def stl(s, m, n): s.w(0x2002 | n << 8 | m << 4)
    def ldld(s, d, m, n): assert d % 4 == 0; s.w(0x5000 | n << 8 | m << 4 | d // 4)     # mov.l @(d,Rm),Rn
    def stld(s, m, d, n): assert d % 4 == 0; s.w(0x1000 | n << 8 | m << 4 | d // 4)     # mov.l Rm,@(d,Rn)
    def ldwd(s, d, m): assert d % 2 == 0; s.w(0x8500 | m << 4 | d // 2)                # mov.w @(d,Rm),R0
    def extb(s, m, n): s.w(0x600C | n << 8 | m << 4)
    def extw(s, m, n): s.w(0x600D | n << 8 | m << 4)
    def cmpeq(s, m, n): s.w(0x3000 | n << 8 | m << 4)        # T = Rn == Rm
    def cmphs(s, m, n): s.w(0x3002 | n << 8 | m << 4)        # T = Rn >= Rm (부호 없음)
    def cmphi(s, m, n): s.w(0x3006 | n << 8 | m << 4)        # T = Rn > Rm (부호 없음)
    def cmpgt(s, m, n): s.w(0x3007 | n << 8 | m << 4)        # T = Rn > Rm (부호)
    def cmpge(s, m, n): s.w(0x3003 | n << 8 | m << 4)
    def tst(s, m, n): s.w(0x2008 | n << 8 | m << 4)
    def and_(s, m, n): s.w(0x2009 | n << 8 | m << 4)
    def or_(s, m, n): s.w(0x200B | n << 8 | m << 4)
    def andi(s, i): s.w(0xC900 | i)                          # and #i,R0
    def tsti(s, i): s.w(0xC800 | i)
    def cmpeqi(s, i): s.w(0x8800 | (i & 0xFF))
    def shll(s, n): s.w(0x4000 | n << 8)
    def shlr(s, n): s.w(0x4001 | n << 8)
    def shll2(s, n): s.w(0x4008 | n << 8)
    def shlr2(s, n): s.w(0x4009 | n << 8)
    def shll8(s, n): s.w(0x4018 | n << 8)
    def shll16(s, n): s.w(0x4028 | n << 8)
    def shlr8(s, n): s.w(0x4019 | n << 8)
    def dt(s, n): s.w(0x4010 | n << 8)
    def push(s, n): s.w(0x2F06 | n << 4)                     # mov.l Rn,@-r15
    def pop(s, n): s.w(0x60F6 | n << 8)                      # mov.l @r15+,Rn
    def pushpr(s): s.w(0x4F22)
    def poppr(s): s.w(0x4F26)
    def ldspr(s, m): s.w(0x402A | m << 8)
    def jsr(s, m): s.w(0x400B | m << 8)
    def jmp(s, m): s.w(0x402B | m << 8)
    def rts(s): s.w(0x000B)
    def nop(s): s.w(0x0009)


def code(lay):
    a = S(CODE)
    # ── vwrap / vwrap2: 번호·프레임 0·무효, 콜백 자리 → 원래 함수
    for nm, tgt in (('vwrap', VOICE), ('vwrap2', VOICE2)):
        a.L(nm); a.ld(1, VAR); a.stl(4, 1); a.movi(0, 0); a.stld(0, 4, 1); a.stld(0, 16, 1)
        a.ld(2, CB_AT); a.ld(0, 'cb'); a.stl(0, 2)
        a.ld(0, tgt); a.jmp(0); a.nop()
    a.ltorg()
    # ── cb(r5 = 덩어리, r15·r11 = 해석기 것): 다 실렸나 → 번호 맞으면 SUBBUF 로 베낌 → 해석 계속
    a.L('cb')
    a.ldld(8, 15, 0); a.ldld(60, 11, 1); a.cmphi(1, 0); a.br('bt', 'cb_retry')
    a.ldwd(8, 5); a.extw(0, 0); a.ld(1, VAR); a.ldl(1, 2); a.cmpeq(2, 0); a.br('bf', 'cb_cont')     # 번호 다르면 안 베낌
    a.ldwd(4, 5); a.extw(0, 3); a.shll16(3); a.ldwd(6, 5); a.extw(0, 0); a.or_(0, 3)                # r3 = 덩어리 크기
    a.ld(2, SUBMAX); a.cmphi(2, 3); a.br('bt', 'cb_cont')                                           # 너무 크면 버림
    a.addi(1, 3); a.shlr(3)                                                                          # 낱말 수
    a.mov(5, 4); a.addi(8, 4); a.ld(2, lay['SUBBUF'])
    a.L('cb_cp'); a.ldwp(4, 0); a.stw(0, 2); a.addi(2, 2); a.dt(3); a.br('bf', 'cb_cp')
    a.ld(1, VAR); a.movi(1, 0); a.stld(0, 16, 1); a.movi(-1, 0); a.stld(0, 8, 1)                  # valid = 1 · shown = 없음
    a.movi(0, 0); a.stld(0, 4, 1)                                                                    # 프레임 0 — 재생 함수 호출부터 세면 CD 읽기 지연(~0.7초)만큼 앞 쪽이 지나가 버림(2026-10-25 실기 «마리카» 순식간)
    a.L('cb_cont'); a.ld(0, CONT); a.ldspr(0); a.rts(); a.nop()
    a.L('cb_retry'); a.ld(0, RETRY); a.ldspr(0); a.rts(); a.nop()
    a.ltorg()
    # ── vbo
    a.L('vbo'); a.pushpr(); a.br('bsr', 'sub'); a.nop(); a.ld(0, VBO); a.jsr(0); a.nop(); a.poppr(); a.rts(); a.nop()
    # ── sub
    a.L('sub'); a.ld(6, VAR)
    a.ld(2, CB_AT); a.ld(0, 'cb'); a.stl(0, 2)                                                       # 콜백 자리 늘 우리 것
    a.ld(1, PLAY); a.ldb(1, 0); a.tsti(0xFF); a.br('bt', 'off')
    a.ldld(4, 6, 3); a.addi(1, 3); a.stld(3, 4, 6)                                                    # r3 = 프레임 +1
    a.ldld(16, 6, 0); a.tst(0, 0); a.br('bt', 'off')
    a.ld(1, lay['SUBBUF']); a.ldwd(0, 1); a.extw(0, 0); a.ldl(6, 2); a.cmpeq(2, 0); a.br('bf', 'off')
    a.ldwd(2, 1); a.extw(0, 5); a.addi(4, 1); a.movi(0, 4)                                            # r5 = 쪽 수, r1 = 첫 쪽, r4 = 쪽 번호
    a.L('pl'); a.cmphs(5, 4); a.br('bt', 'off')
    a.ldwd(0, 1); a.extw(0, 2); a.cmphs(2, 3); a.br('bf', 'pn')                                      # 프레임 >= 시작
    a.ldwd(2, 1); a.extw(0, 2); a.cmphs(2, 3); a.br('bf', 'show')                                    # 프레임 < 끝 → 이 쪽
    a.L('pn'); a.ldwd(8, 1); a.extw(0, 0); a.shll(0); a.addi(10, 1); a.add(0, 1); a.addi(1, 4); a.br('bra', 'pl'); a.nop()
    a.L('show'); a.ldld(8, 6, 0); a.cmpeq(4, 0); a.br('bt', 'crm')
    a.stld(4, 8, 6)
    a.pushpr(); a.mov(1, 4); a.br('bsr', 'render'); a.nop(); a.poppr(); a.ld(6, VAR)
    a.ld(1, lay['COMP']); a.ld(2, TEX); a.ld(5, BMPSZ // 4)
    a.L('cp'); a.ldl(1, 0); a.stl(0, 2); a.addi(4, 1); a.addi(4, 2); a.dt(5); a.br('bf', 'cp')
    a.L('crm'); a.ld(2, CRAM); a.ld(0, 0x0000); a.w(0x8121); a.ld(0, 0x7FFF); a.w(0x8122); a.ld(0, 0x4A52); a.w(0x8123)
    # 명령표 연결(PoC 그대로)
    W = a.w
    a.L('link'); a.ld(1, READY); W(0x6012, 0x2008); a.br('bt', 'ret')
    a.ld(1, LIST); W(0xE700); a.ld(5, 3000)
    a.L('wl'); W(0x6011, 0x4011); a.br('bf', 'isend')
    # 명령 코드가 3·0xB 이상(없는 명령) = 게임이 END 없이 남긴 묵은 칸 → 여기를 끝으로 봄
    # (2026-10-25 실기 «리바이벌 도그» 장면: 0xE0 = 0x217B(jp2 호출→0번) — VDP1 은 0번부터 되풀이하다 프레임 바뀜, 훅은 END 를 못 찾아 자막 포기)
    W(0x6303, 0xC90F, 0x8803); a.br('bt', 'isend')
    W(0xE20B, 0x3022); a.br('bt', 'isend'); W(0x6033)
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
    a.ltorg()

    # ── render(r4 = 쪽): r8~r14 보존
    a.L('render')
    for n in (8, 9, 10, 11, 12, 13, 14): a.push(n)
    a.pushpr()
    a.mov(4, 14)
    a.ld(1, lay['COMP']); a.ld(2, BMPSZ // 4); a.movi(0, 0)                                          # 지움
    a.L('rc'); a.stl(0, 1); a.addi(4, 1); a.dt(2); a.br('bf', 'rc')
    # 띠: bx0 = max(0, x0-6)>>1 · bx1 = (min(320, x0+w+6)+1)>>1, 행 1..22 = 0x11
    a.ldwd(4, 14); a.extw(0, 8); a.ldwd(6, 14); a.extw(0, 9)                                       # r8 = x0, r9 = 폭
    a.mov(8, 10); a.addi(-6, 10); a.movi(0, 0); a.cmpgt(10, 0); a.br('bf', 'b0ok'); a.movi(0, 10)
    a.L('b0ok'); a.shlr(10)
    a.mov(8, 11); a.add(9, 11); a.addi(6, 11); a.ld(0, W_); a.cmpgt(0, 11); a.br('bf', 'b1ok'); a.mov(0, 11)
    a.L('b1ok'); a.addi(1, 11); a.shlr(11)
    a.ld(12, lay['COMP'] + ROWB); a.movi(22, 13); a.ld(3, 0x11)
    a.L('brow'); a.mov(12, 1); a.add(10, 1); a.mov(11, 2); a.sub(10, 2)
    a.L('bcol'); a.stb(3, 1); a.addi(1, 1); a.dt(2); a.br('bf', 'bcol')
    a.ld(0, ROWB); a.add(0, 12); a.dt(13); a.br('bf', 'brow')
    # 글자들: r8 = x, r13 = 남은 글자, r12 = 글자 번호 자리
    a.ldwd(8, 14); a.extw(0, 13); a.mov(14, 12); a.addi(10, 12)
    a.tst(13, 13); a.br('bt', 'rdone')
    a.L('gl'); a.ldwp(12, 0); a.extw(0, 0)
    a.ld(1, lay['ADV']); a.add(0, 1); a.ldb(1, 11); a.extb(11, 11)                                  # r11 = 너비
    a.mov(0, 1); a.shll2(1); a.shll2(0); a.shll2(0); a.shll(0); a.sub(1, 0)                          # r0 = 번호×28
    a.ld(10, lay['FONT']); a.add(0, 10)                                                              # r10 = 그림(28 B = 1~14행)
    a.movi(GY + GR0, 9)                                                                              # r9 = y
    a.L('grow'); a.ldwp(10, 14); a.extw(14, 14); a.tst(14, 14); a.br('bt', 'gnext')
    a.shll16(14); a.mov(8, 4)                                                                        # r4 = 화소 x
    a.L('gcol'); a.shll(14); a.br('bf', 'gskip')
    a.mov(4, 0); a.push(0); a.addi(1, 4); a.mov(9, 5); a.addi(1, 5); a.movi(3, 6); a.movi(1, 7); a.br('bsr', 'pix'); a.nop()
    a.pop(4); a.mov(9, 5); a.movi(2, 6); a.movi(0, 7); a.br('bsr', 'pix'); a.nop()
    a.L('gskip'); a.addi(1, 4); a.tst(14, 14); a.br('bf', 'gcol')
    a.L('gnext'); a.addi(1, 9); a.mov(9, 0); a.cmpeqi(GY + GR0 + GROWS); a.br('bf', 'grow')
    a.add(11, 8); a.dt(13); a.br('bf', 'gl')
    a.L('rdone'); a.poppr()
    for n in (14, 13, 12, 11, 10, 9, 8): a.pop(n)
    a.rts(); a.nop()
    a.ltorg()
    # ── pix(r4 = x, r5 = y, r6 = 색, r7 = 1 이면 띠(1) 위에만) — r0~r3 씀
    a.L('pix'); a.ld(0, W_); a.cmphs(0, 4); a.br('bt', 'pret'); a.movi(H_, 0); a.cmphs(0, 5); a.br('bt', 'pret')
    a.mov(5, 1); a.shll2(1); a.shll2(1); a.shll(1); a.mov(1, 0); a.shll2(0); a.add(1, 0)              # y*32 · y*128 → y*160
    a.mov(4, 1); a.shlr(1); a.add(1, 0); a.ld(2, lay['COMP']); a.add(0, 2)                          # r2 = 바이트 자리
    a.ldb(2, 1); a.extb(1, 1); a.mov(4, 0); a.tsti(1); a.br('bf', 'podd')
    a.mov(1, 3); a.shlr2(3); a.shlr2(3)                                                              # 짝수 = 윗 4비트
    a.tst(7, 7); a.br('bt', 'pe1'); a.movi(1, 0); a.cmpeq(0, 3); a.br('bf', 'pret')
    a.L('pe1'); a.mov(1, 0); a.andi(0x0F); a.mov(6, 3); a.shll2(3); a.shll2(3); a.or_(3, 0); a.stb(0, 2); a.rts(); a.nop()
    a.L('podd'); a.mov(1, 0); a.andi(0x0F); a.mov(0, 3)
    a.tst(7, 7); a.br('bt', 'po1'); a.movi(1, 0); a.cmpeq(0, 3); a.br('bf', 'pret')
    a.L('po1'); a.mov(1, 0); a.andi(0xF0); a.or_(6, 0); a.stb(0, 2)
    a.L('pret'); a.rts(); a.nop()
    return a


def layout(nfont):
    """BLOCK 안 자리 — 코드 크기 재고 정함"""
    tmp = {'SUBBUF': 0x0A0B0C00, 'COMP': 0x0A0B0D00, 'FONT': 0x0A0B0E00, 'ADV': 0x0A0B0F00}
    n0 = len(code(tmp).build())
    lay = {}
    p = (CODE + n0 + 15) & ~15
    lay['SUBBUF'] = p; p += SUBMAX
    lay['COMP'] = p; p += BMPSZ
    lay['FONT'] = p; p += FONT_B * nfont
    lay['ADV'] = p; p += nfont
    lay['END'] = (p + 15) & ~15
    a = code(lay); c = a.build(); assert len(c) == n0
    return lay, a, c


def block(font_bits, advs):
    """font_bits: [32 B]…, advs: [폭]… → (블록 바이트, 라벨, 자리)"""
    lay, a, c = layout(len(advs))
    blk = bytearray(lay['END'] - BLOCK)
    blk[0:4] = b'MSB2'
    struct.pack_into('>5I', blk, VAR - BLOCK, 0, 0, 0xFFFFFFFF, 0, 0)
    tpl = struct.pack('>16H', 0x0000, 0, 0x0080, COLR, TEXA, (W_ // 8) << 8 | H_, 0, YA, 0, 0, 0, 0, 0, 0, 0, 0) + struct.pack('>16H', 0x8000, *[0] * 15)
    blk[VAR - BLOCK + 0x20:VAR - BLOCK + 0x60] = tpl
    blk[CODE - BLOCK:CODE - BLOCK + len(c)] = c
    f = lay['FONT'] - BLOCK
    for i, g in enumerate(font_bits): blk[f + FONT_B * i:f + FONT_B * (i + 1)] = g[2 * GR0:2 * (GR0 + GROWS)]
    blk[lay['ADV'] - BLOCK:lay['ADV'] - BLOCK + len(advs)] = bytes(advs)
    return bytes(blk), a.lab, lay


def patch_sen(sen, font_bits, advs):
    blk, lab, lay = block(font_bits, advs)
    s = bytearray(sen)
    for lit in P.VOICE_LITS:
        assert struct.unpack_from('>I', s, lit - P.SEN_BASE)[0] == VOICE; struct.pack_into('>I', s, lit - P.SEN_BASE, lab['vwrap'])
    for lit in P.VOICE2_LITS:
        assert struct.unpack_from('>I', s, lit - P.SEN_BASE)[0] == VOICE2; struct.pack_into('>I', s, lit - P.SEN_BASE, lab['vwrap2'])
    assert struct.unpack_from('>I', s, P.VBO_LIT - P.SEN_BASE)[0] == VBO; struct.pack_into('>I', s, P.VBO_LIT - P.SEN_BASE, lab['vbo'])
    assert s[TAG_AT - P.SEN_BASE:TAG_AT - P.SEN_BASE + 4] == b'APCM'; s[TAG_AT - P.SEN_BASE:TAG_AT - P.SEN_BASE + 4] = b'MSUB'
    assert len(s) <= BLOCK - P.SEN_BASE
    s += bytes(BLOCK - P.SEN_BASE - len(s)); s += blk
    assert BLOCK + len(blk) <= RAM_END, ('자막 블록이 얼굴 버퍼(0x0608D000)를 넘음', hex(BLOCK + len(blk)))
    return bytes(s), lab, lay


def ref_render(page, font_bits, advs):
    """render 와 같은 셈(검산용) → 3840 B"""
    st, en, x0, w, glyphs = page
    px = [[0] * W_ for _ in range(H_)]
    b0 = max(0, x0 - 6) >> 1; b1 = (min(W_, x0 + w + 6) + 1) >> 1
    for y in range(1, 23):
        for b in range(b0, b1): px[y][2 * b] = px[y][2 * b + 1] = 1
    x = x0
    for g in glyphs:
        bits = font_bits[g]
        for r in range(GR0, GR0 + GROWS):
            v = bits[2 * r] << 8 | bits[2 * r + 1]
            for c in range(16):
                if v & (0x8000 >> c):
                    xx, yy = x + c, GY + r
                    if xx + 1 < W_ and yy + 1 < H_ and px[yy + 1][xx + 1] == 1: px[yy + 1][xx + 1] = 3
                    if xx < W_ and yy < H_: px[yy][xx] = 2
        x += advs[g]
    return bytes(px[y][x] << 4 | px[y][x + 1] for y in range(H_) for x in range(0, W_, 2))
