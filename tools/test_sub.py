# -*- coding: utf-8 -*-
"""자막 본 훅 검산(2026-10-25): 패치 SEN.BIN 을 흉내기 램에 올리고
   ① vwrap(번호·콜백 자리) ② 해석기 흉내로 cb 호출(다 안 실림 → RETRY, 다 실림 → 베낌·CONT, 번호 다름 → 안 베낌)
   ③ 프레임 돌려 쪽 고르기 · render 결과 = ref_render · TEX 복사 · 쪽 바뀜 · 재생 끝 되돌림 + 미리보기 그림."""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
import sh2sim as S, subdata as D, subhook as H


def main(voice='FLD/M00/PCM0502', preview=True):
    sys.stdout.reconfigure(encoding='utf-8')
    idx, bits, advs, chunks, npage, big = D.build()
    sen = open(os.path.join(ROOT, 'work', 'disc', 'SEN.BIN'), 'rb').read()
    s, lab, lay = H.patch_sen(sen, bits, advs)
    m = S.Mem(); ram = m.add(0x06000000, 0x100000); m.add(0x05C00000, 0x80000); m.add(0x05F00000, 0x1000); snd = m.add(0x05A00000, 0x80000)
    ram[0x2000:0x2000 + len(s)] = s
    ok = True
    ch = chunks[voice]; num, pages = D.parse_chunk(ch)
    # ① vwrap
    S.run(m, lab['vwrap'], regs=[0, 0, 0, 0, num], calls={H.VOICE: lambda r, mm: None})
    c1 = m.r32(H.VAR) == num and m.r32(H.VAR + 16) == 0 and m.r32(H.CB_AT) == lab['cb']
    print('vwrap 번호·무효·콜백 자리', c1); ok &= c1
    # ② cb — 덩어리를 사운드 램 0x25A78100 에, 해석기 스택 흉내(r15: @(8) = 다음 위치, r11: @(60) = 실린 양)
    base = 0x25A78100; snd[0x78100:0x78100 + len(ch)] = ch
    stk = 0x060FE000; st11 = 0x060FD000
    def call_cb(loaded, nextofs):
        m.w32(stk + 8, nextofs); m.w32(st11 + 60, loaded)
        regs = [0] * 16; regs[5] = base; regs[11] = st11; regs[15] = stk
        class Hit(Exception): pass
        def go(to):                                                    # CONT/RETRY 는 JMP 로 감 — 돌아올 곳(PR)이 stop 이 아니라 예외로 빠져나옴
            def f(r, mm): raise Hit(to)
            return f
        try: S.run(m, lab['cb'], regs=regs, calls={H.CONT: go('CONT'), H.RETRY: go('RETRY')}, stop=0xDEAD0000)
        except Hit as e: return e.args[0]
        return None
    c2 = call_cb(100, 100 + len(ch)) == 'RETRY' and m.r32(H.VAR + 16) == 0
    print('덜 실림 → 나중에 다시(RETRY)', c2); ok &= c2
    m.w32(H.VAR + 4, 77)
    c3 = call_cb(100 + len(ch), 100 + len(ch)) == 'CONT' and m.r32(H.VAR + 16) == 1 and m.r32(H.VAR + 4) == 0 and bytes(m.r8(lay['SUBBUF'] + i) for i in range(len(ch) - 8)) == ch[8:]
    print('다 실림 → 베끼고 프레임 0·계속(CONT)', c3); ok &= c3
    m.w32(H.VAR + 16, 0); m.w32(H.VAR, num + 1)
    c4 = call_cb(100 + len(ch), 100 + len(ch)) == 'CONT' and m.r32(H.VAR + 16) == 0
    print('번호 다른 덩어리 → 안 베끼고 계속', c4); ok &= c4
    m.w32(H.VAR, num); call_cb(100 + len(ch), 100 + len(ch))
    # ③ 프레임
    L = H.LIST
    for i, (ctrl, link) in enumerate([(0x0009, 0), (0x0000, 0), (0x8000, 0)]): m.w16(L + 32 * i, ctrl); m.w16(L + 32 * i + 2, link)
    END = L + 64
    m.w8(H.PLAY, 1); m.w32(H.READY, 1)
    def frame(): S.run(m, lab['vbo'], calls={H.VBO: lambda r, mm: None})
    seen = []; shots = []
    last = pages[-1][1] + 5
    for f in range(1, min(last, 4000)):
        frame()
        sh = m.r32(H.VAR + 8)
        if sh != 0xFFFFFFFF and (not seen or seen[-1] != sh):
            seen.append(sh)
            tex = bytes(m.r8(H.TEX + i) for i in range(H.BMPSZ)); ref = H.ref_render(pages[sh], bits, advs)
            good = tex == ref and m.r16(END) == 0x5000
            if not good: print('  ✗ 쪽 %d 그림 다름' % sh); ok = False
            if len(shots) < 4: shots.append(tex)
    want = [i for i, p in enumerate(pages) if p[0] < min(last, 4000) - 1]
    c5 = seen == want[:len(seen)] and len(seen) >= min(3, len(pages))
    print('쪽 차례대로 %d개 · 그림 = 참조(파이썬) %s' % (len(seen), c5)); ok &= c5
    m.w8(H.PLAY, 0); frame(); c6 = m.r16(END) == 0x8000 and m.r32(H.VAR + 8) == 0xFFFFFFFF
    print('재생 끝 → END 되돌림', c6); ok &= c6
    # END 없이 묵은 칸(없는 명령 0x217B, jp2 호출→0번)이 있는 명령표(«리바이벌 도그» 장면) → 그 칸을 끝으로 보고 연결
    for i, (ctrl, link) in enumerate([(0x0009, 0), (0x0002, 0), (0x217B, 0)]): m.w16(L + 32 * i, ctrl); m.w16(L + 32 * i + 2, link)
    m.w8(H.PLAY, 1); m.w32(H.VAR + 4, pages[0][0]); m.w32(H.VAR + 8, 0xFFFFFFFF)
    for _ in range(3): frame()
    c7 = m.r16(L + 64) == 0x5000 and m.r16(L + 66) == H.OWNL
    m.w8(H.PLAY, 0); frame(); c7 &= m.r16(L + 64) == 0x8000
    print('END 없는 명령표(없는 명령 칸) → 그 칸에 연결·끝나면 END', c7); ok &= c7
    if preview and shots:
        from PIL import Image
        pal = {0: (40, 60, 90), 1: (0, 0, 0), 2: (255, 255, 255), 3: (82, 82, 148)}
        im = Image.new('RGB', (320, 26 * len(shots)), (40, 60, 90))
        for k, t in enumerate(shots):
            for y in range(24):
                for x in range(320):
                    b = t[y * 160 + x // 2]; v = b >> 4 if x % 2 == 0 else b & 15
                    if v: im.putpixel((x, 26 * k + y), pal[v])
        out = os.path.join(ROOT, 'work', 'preview', 'sub_runtime.png'); im.resize((960, 78 * len(shots)), Image.NEAREST).save(out); print('미리보기', out)
    print('✅ 모두 통과' if ok else '❌ 실패'); return ok


if __name__ == '__main__':
    sys.exit(0 if main(*sys.argv[1:2]) else 1)
