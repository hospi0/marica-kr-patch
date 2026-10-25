# -*- coding: utf-8 -*-
r"""MAC*.DAT 이벤트 스크립트 해석·다시 짜기 (2026-10-25, SEN.BIN 해석기 0x06010304 판독)
  MAC 파일은 램 0x00260000 에 통째로 실리고, 스크립트 구역 = 파일 0x10000(램 0x00270000) 부터.
  구역 맨 앞 = 진입표(u32, 구역 기준 상대 위치, 0 이전까지) — 해석기: PC = 0x270000 + 표[번호]
  명령(2바이트 BE) — 모드마다 뜻이 다름:
    모드 0: 0 F(F=0 → 메시지 모드 1, 아니면 선택지 모드 2) · 4 a · 5 a · 7 a 거짓 참(u16 상대 위치, 0 = 다음) · FF(끝) · 그 밖 1워드
    모드 1(메시지): 1 길이 글(짝수 맞춤) · 3/8(창 띄움 → 모드 0) · 그 밖 → 모드 0(그 워드는 먹힘)
    모드 2(선택지): 2 길이 글 · 3/8 → 선택지 수만큼 [6 변수 값](없으면 건너뜀) + [9 값] 선택 → 모드 0
  python tools/macscript.py 파일.DAT → 걸어 보기 검산(진입점에서 닿는 명령·대사 기록 수, 미닿음 대사)"""
import struct, sys

BASE = 0x10000


def entries(d):
    out = []; p = BASE
    while True:
        v = struct.unpack_from('>I', d, p)[0]
        if v == 0 or v >= 0x10000: break
        out.append(v); p += 4
    return out


def walk(d, end=None):
    """→ {상대 위치: (모드, 명령, 길이, 점프 필드 상대 위치 목록)}"""
    end = end or len(d) - BASE
    W = lambda r: struct.unpack_from('>H', d, BASE + r)[0]
    ins = {}; todo = [(e, 0) for e in entries(d)]
    while todo:
        pc, mode = todo.pop()
        while 0 <= pc < end:
            if (pc, mode) in seen_set: break
            seen_set.add((pc, mode))
            op = W(pc)
            if mode == 0:
                if op == 0:
                    f = W(pc + 2); ins[pc] = (0, op, 4, []); pc += 4; mode = 1 if f == 0 else 2; nchoice[0] = 0; continue
                if op in (4, 5): ins[pc] = (0, op, 4, []); pc += 4; continue
                if op == 7:
                    a, y, x = W(pc + 2), W(pc + 4), W(pc + 6)
                    ins[pc] = (0, op, 8, [pc + 4, pc + 6])
                    for t in (y, x):
                        if t: todo.append((t, 0))
                    if x and y: break                                   # 두 갈래 모두 점프 — 이어지지 않음
                    pc += 8; continue
                if op == 0xFF: ins[pc] = (0, op, 2, []); break
                ins[pc] = (0, op, 2, []); pc += 2; continue
            if mode == 1:
                if op == 1:
                    ln = W(pc + 2); ins[pc] = (1, op, 4 + ln + (ln & 1), []); pc += 4 + ln + (ln & 1); continue
                ins[pc] = (1, op, 2, []); pc += 2; mode = 0; continue
            if mode == 2:
                if op == 2:
                    ln = W(pc + 2); ins[pc] = (2, op, 4 + ln + (ln & 1), []); pc += 4 + ln + (ln & 1); nchoice[0] += 1; continue
                if op in (3, 8):
                    ins[pc] = (2, op, 2, []); pc += 2
                    for _ in range(nchoice[0]):
                        if W(pc) == 6: ins[pc] = (2, 6, 6, []); pc += 6
                    if W(pc) == 9: ins[pc] = (2, 9, 4, []); pc += 4
                    mode = 0; continue
                ins[pc] = (2, op, 2, []); pc += 2; mode = 0; continue
    return ins


seen_set = set(); nchoice = [0]


def main(path):
    global seen_set
    d = open(path, 'rb').read(); seen_set = set()
    ins = walk(d)
    txt = [r for r, v in ins.items() if v[1] in (1, 2) and v[0] in (1, 2)]
    # 파일 안 «0001/0002 길이 SJIS» 기록 전부(추출기와 같은 기준) 중 걸어서 못 닿은 것
    import re
    allrec = []
    p = BASE
    while p < len(d) - 4:
        if d[p] == 0 and d[p + 1] in (1, 2):
            ln = struct.unpack_from('>H', d, p + 2)[0]
            if 0 < ln <= 200 and ln % 2 == 0:
                try: t = d[p + 4:p + 4 + ln].decode('cp932')
                except UnicodeDecodeError: t = None
                if t and re.search('[ぁ-んァ-ヶ一-龥]', t): allrec.append(p - BASE)
        p += 2
    miss = [r for r in allrec if r not in ins]
    mx = max(r + v[2] for r, v in ins.items())
    print('%s 진입 %d · 명령 %d · 글 기록 %d · 파일 속 글 기록 %d · 못 닿음 %d · 구역 끝 0x%X' % (
        path.split('/')[-1], len(entries(d)), len(ins), len(txt), len(allrec), len(miss), BASE + mx))
    return miss


if __name__ == '__main__':
    for p in sys.argv[1:]: main(p)
