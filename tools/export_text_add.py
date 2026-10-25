# -*- coding: utf-8 -*-
r"""텍스트 추출 보충 (2026-10-25) — 번호를 바꾸지 않고 «빠졌던 문자열»만 뒤 번호로 덧붙임(누락 검사 tools/scan_missing.py 결과).
  ① 필드 선택지: MAC*.DAT 명령 «0x0002 + 길이(2 B BE) + SJIS» (대사 0x0001 과 같은 꼴) — 처음 추출은 0x0001 만 봤다.
  ② TITLE.BIN · SEN.BIN: 누락 후보 중 글자 문자열(레코드 머리 ASCII 1바이트 떼고 앞뒤 공백 뗌, 위치도 그만큼)
     — 데이터 우연(«日は»·«Ohoooq…»)은 뺌.
  → data/번역할것/텍스트_추가NN.tsv (번호·원문·번역·위치·쓰인 곳·종류) + _텍스트위치.tsv 끝에 덧붙임
  python tools/export_text_add.py"""
import collections, glob, os, re, struct, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISC = os.path.join(ROOT, 'work', 'disc')
OUT = os.path.join(ROOT, 'data', '번역할것')
NOISE = {'日は', 'Ohoooqまりかあきらかなめ'}


def have():
    src = {}; locs = set()
    for f in glob.glob(os.path.join(OUT, '텍스트_*.tsv')):
        for ln in open(f, encoding='utf-8-sig').read().split('\n')[1:]:
            if ln: c = ln.split('\t'); src[c[1]] = c[0]
    for ln in open(os.path.join(OUT, '_텍스트위치.tsv'), encoding='utf-8-sig').read().split('\n')[1:]:
        if ln: locs.update(ln.split('\t')[1].split())
    return src, locs


def choices(d):
    out = []; p = 0
    while p < len(d) - 4:
        if d[p] == 0 and d[p + 1] == 2:
            ln = struct.unpack_from('>H', d, p + 2)[0]
            if 0 < ln <= 64 and ln % 2 == 0:
                try: t = d[p + 4:p + 4 + ln].decode('cp932')
                except UnicodeDecodeError: t = None
                if t and all(ord(c) >= 0x20 for c in t) and re.search('[ぁ-んァ-ヶ一-龥]', t):
                    out.append((p, t)); p += 4 + ln; continue
        p += 2
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    src, locs = have()
    new = collections.OrderedDict(); kind = {}
    for p in sorted(glob.glob(os.path.join(DISC, 'FLD', 'M*', 'MAC*.DAT'))):
        rel = os.path.relpath(p, DISC).replace(os.sep, '/'); d = open(p, 'rb').read()
        for off, t in choices(d):
            if '%s:%X' % (rel, off) in locs: continue
            new.setdefault(t, []).append('%s:%X' % (rel, off)); kind.setdefault(t, '선택지')
    for ln in open(os.path.join(ROOT, 'work', 'trcheck', '텍스트누락후보.tsv'), encoding='utf-8-sig').read().split('\n')[1:]:
        if not ln: continue
        f, off, _, t = ln.split('\t')
        if f not in ('TITLE.BIN', 'SEN.BIN') or t in NOISE: continue
        off = int(off, 16)
        if len(t) > 1 and ord(t[0]) < 0x80 and ord(t[1]) > 0x7F and t[0] != ' ': t = t[1:]; off += 1   # 레코드 머리 1바이트(곡 번호 등)
        lead = len(t) - len(t.lstrip(' 　')); core = t.strip(' 　')
        off += len(t[:lead].encode('cp932'))
        if not core or core in src or '%s:%X' % (f, off) in locs: continue
        new.setdefault(core, []).append('%s:%X' % (f, off)); kind.setdefault(core, '문자열')
    new = [(s, l) for s, l in new.items() if s not in src]
    if not new: print('빠진 문자열 없음'); return
    start = max(int(n) for n in src.values()) + 1
    k = 1 + sum(1 for f in os.listdir(OUT) if f.startswith('텍스트_추가'))
    with open(os.path.join(OUT, '텍스트_추가%02d.tsv' % k), 'w', encoding='utf-8-sig', newline='\n') as w:
        w.write('번호\t원문\t번역\t위치\t쓰인 곳\t종류\n')
        for i, (s, l) in enumerate(new):
            w.write('%05d\t%s\t\t%s\t%d\t%s\n' % (start + i, s, l[0], len(l), kind[s]))
    with open(os.path.join(OUT, '_텍스트위치.tsv'), 'a', encoding='utf-8', newline='\n') as w:
        for i, (s, l) in enumerate(new): w.write('%05d\t%s\n' % (start + i, ' '.join(l)))
    c = collections.Counter(kind[s] for s, _ in new)
    print('빠졌던 문자열 %d줄(%05d~, %s) · 글자 %d → 텍스트_추가%02d.tsv' % (len(new), start, dict(c), sum(len(s) for s, _ in new), k))


if __name__ == '__main__':
    main()
