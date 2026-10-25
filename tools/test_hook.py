# -*- coding: utf-8 -*-
"""자막 훅 검산(2026-10-25): 패치한 SEN.BIN 을 램에 올리고 vwrap → vbo 를 프레임마다 돌려
   쪽 고르기·그림 복사·CRAM·END 점프·중복 없음·게임이 명령표 다시 쓸 때·꺼질 때 되돌림·점프/호출 섞인 명령표를 본다."""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
import hook as H, sh2sim as S


def setup():
    sen = open(os.path.join(ROOT, 'work', 'disc', 'SEN.BIN'), 'rb').read()
    s, lab, texts, subs = H.patch_sen(sen)
    m = S.Mem(); ram = m.add(0x06000000, 0x100000); m.add(0x05C00000, 0x80000); m.add(0x05F00000, 0x1000)
    ram[0x2000:0x2000 + len(s)] = s
    return m, lab, texts, subs


def frame(m, lab):
    S.run(m, lab['vbo'], calls={H.VBO: lambda r, mm: None})


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    m, lab, texts, subs = setup(); ok = True
    L = H.LIST
    def setlist(cmds):
        for i, (ctrl, link) in enumerate(cmds):
            m.w16(L + 32 * i, ctrl); m.w16(L + 32 * i + 2, link)
    setlist([(0x0009, 0), (0x000A, 0), (0x0000, 0), (0x0000, 0), (0x8000, 0)]); END = L + 32 * 4
    m.w8(H.PLAY, 1); m.w32(H.READY, 1)
    S.run(m, lab['vwrap'], regs=[0, 0, 0, 0, 104], calls={H.VOICE: lambda r, mm: None})
    assert m.r32(H.VAR) == 104 and m.r32(H.VAR + 4) == 0
    want = [p for p in subs if p[0] == 104]
    for f in range(1, 200 + 1): frame(m, lab)
    fr = m.r32(H.VAR + 4); page = [p for p in want if p[1] <= fr < p[2]][0]; idx = texts.index(page[3])
    tex = bytes(m.r8(H.TEX + i) for i in range(H.BMPSZ)); ref = H.render(page[3])[0]
    c1 = tex == ref and m.r32(H.VAR + 8) == idx
    c2 = m.r16(END) == 0x5000 and m.r16(END + 2) == H.OWNL and m.r16(H.OWN) == 0 and m.r16(H.OWN + 4) == 0x0080 and m.r16(H.OWN + 6) == H.COLR \
        and m.r16(H.OWN + 8) == H.TEXA and m.r16(H.OWN + 10) == 0x2818 and m.r16(H.OWN + 32) == 0x8000
    c3 = m.r16(H.CRAM + 2) == 0 and m.r16(H.CRAM + 4) == 0x7FFF
    print('프레임 %d 쪽 «%s» 그림 %s · END 점프 %s · CRAM %s' % (fr, page[3], c1, c2, c3)); ok &= c1 and c2 and c3
    frame(m, lab); c4 = m.r16(END) == 0x5000 and m.r32(H.VAR + 12) == END
    print('다음 프레임 그대로', c4); ok &= c4
    m.w16(H.CRAM + 4, 0); frame(m, lab); c4b = m.r16(H.CRAM + 4) == 0x7FFF
    print('게임이 CRAM 지워도 다음 프레임에 색 다시', c4b); ok &= c4b
    m.w16(END, 0x8000); m.w16(END + 2, 0); frame(m, lab); c5 = m.r16(END) == 0x5000
    print('게임이 END 다시 써도 다시 연결', c5); ok &= c5
    m.w32(H.READY, 0); m.w16(END, 0x8000); frame(m, lab); c6 = m.r16(END) == 0x8000
    print('준비됨 아닐 때는 안 건드림', c6); ok &= c6
    m.w32(H.READY, 1); frame(m, lab)
    m.w8(H.PLAY, 0); frame(m, lab); c7 = m.r16(END) == 0x8000 and m.r32(H.VAR + 8) == 0xFFFFFFFF and m.r32(H.VAR + 12) == 0
    print('재생 끝 → END 되돌림', c7); ok &= c7
    # 점프·호출 섞인 명령표
    m.w8(H.PLAY, 1); m.w32(H.VAR + 8, 0xFFFFFFFF)
    for i in range(40): m.w16(L + 32 * i, 0x8000)
    setlist([(0x0009, 0), (0x1000, (0x400 >> 3)), (0x0000, 0)])          # 0 → 칸1 점프 0x400
    m.w16(L + 0x400, 0x2000); m.w16(L + 0x402, 0x800 >> 3)                 # 0x400: 호출 0x800
    m.w16(L + 0x420, 0x0000); m.w16(L + 0x440, 0x8000)                    # 돌아와서 0x420 보통 → 0x440 END
    m.w16(L + 0x800, 0x0000); m.w16(L + 0x820, 0x3000)                    # 0x800 보통, 0x820 돌아가기
    frame(m, lab); c8 = m.r16(L + 0x440) == 0x5000 and m.r16(L + 0x442) == H.OWNL
    print('점프·호출 명령표에서 진짜 END', c8); ok &= c8
    # 쪽 사이 빈틈 없음(다음 쪽 시작까지 이어짐) · 다른 번호는 안 띄움
    m.w8(H.PLAY, 1); S.run(m, lab['vwrap'], regs=[0, 0, 0, 0, 999], calls={H.VOICE: lambda r, mm: None}); frame(m, lab)
    c9 = m.r32(H.VAR + 8) == 0xFFFFFFFF and m.r16(L + 0x440) == 0x8000
    print('자막 없는 음성 → 안 띄우고 되돌림', c9); ok &= c9
    # 두 번째 재생 함수 경로(0x06003E2C)
    hit = []
    m.w32(H.VAR, 0); m.w32(H.VAR + 4, 55)
    S.run(m, lab['vwrap2'], regs=[0, 0, 0, 0, 105], calls={H.VOICE2: lambda r, mm: hit.append(r[4])})
    c10 = m.r32(H.VAR) == 105 and m.r32(H.VAR + 4) == 0 and hit == [105]
    print('두 번째 재생 함수 감싸개(번호 기록·원래 함수로)', c10); ok &= c10
    print('✅ 모두 통과' if ok else '❌ 실패'); return ok


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
