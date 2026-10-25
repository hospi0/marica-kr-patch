# -*- coding: utf-8 -*-
r"""텍스트 추출 누락 검사 (2026-10-25, 건블레이즈 tools/scan_missing.py 방식) — work/disc 의 모든 파일(AIF·DEBUG.BIN 제외)을
  모든 바이트 위치에서 SJIS 로 훑어 글자 줄(2바이트 글자 2개 이상, 가나·한자 2개 이상)을 찾고,
  추출(data/번역할것/_텍스트위치.tsv) 범위 밖인 것만 → 원문 말뭉치 두 글자 짝 70% 이상인 것(무작위 데이터 거름).
  python tools/scan_missing.py → work/trcheck/텍스트누락후보.tsv(파일·위치·앞 바이트·내용) + 파일별 합계"""
import collections, glob, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISC = os.path.join(ROOT, 'work', 'disc')
JP = re.compile('[ぁ-んァ-ヶ一-龥々ー]')


def corpus():
    bg = set(); cov = collections.defaultdict(list)
    good = set()                                                    # 번역자가 비워 둔 줄(데이터 오인 «怯擶»류)은 말뭉치에서 뺌
    for f in glob.glob(os.path.join(ROOT, 'data', '번역', '텍스트_*.tsv')):
        for ln in open(f, encoding='utf-8-sig').read().split('\n')[1:]:
            c = ln.split('\t')
            if len(c) > 2 and c[2].strip(): good.add(c[1])
    for s in good:
        t = re.sub(r'\{[^{}]*\}|#[01]', '', s)
        bg.update(t[i:i + 2] for i in range(len(t) - 1))
    for f in glob.glob(os.path.join(ROOT, 'data', '번역할것', '음성자막_*.tsv')):
        for ln in open(f, encoding='utf-8-sig').read().split('\n')[1:]:
            if ln:
                t = ln.split('\t')[4]; bg.update(t[i:i + 2] for i in range(len(t) - 1))
    srcs = {}
    for f in glob.glob(os.path.join(ROOT, 'data', '번역할것', '텍스트_*.tsv')) + glob.glob(os.path.join(ROOT, 'data', '번역', '텍스트_추가*.tsv')):
        for ln in open(f, encoding='utf-8-sig').read().split('\n')[1:]:
            if ln: c = ln.split('\t'); srcs.setdefault(c[0], c[1])          # 보충 번역(텍스트_추가*) 원문도 — 02226~ 는 여기만 있음
    for ln in open(os.path.join(ROOT, 'data', '번역할것', '_텍스트위치.tsv'), encoding='utf-8-sig').read().split('\n')[1:]:
        if not ln: continue
        n, locs = ln.split('\t')
        blen = sum(len(x.encode('cp932')) for x in re.split(r'\{n\}', srcs[n])) + 8 * srcs[n].count('{n}')
        for x in locs.split():
            fn, off = x.rsplit(':', 1); off = int(off, 16)
            cov[fn].append((off, off + blen + 8))
    return bg, cov


SJ = re.compile(rb'(?:[\x81-\x9f\xe0-\xef][\x40-\x7e\x80-\xfc]|[\x20-\x7e])+')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    bg, cov = corpus()
    rows = []
    for dp, _, fs in os.walk(DISC):
        for f in sorted(fs):
            if f.upper().endswith('.AIF') or f.startswith('_') or f == 'DEBUG.BIN': continue
            p = os.path.join(dp, f); rel = os.path.relpath(p, DISC).replace(os.sep, '/')
            d = open(p, 'rb').read(); cv = sorted(cov.get(rel, []))
            for start in range(2):                                     # 홀수·짝수 정렬 둘 다
                for m in SJ.finditer(d, start):
                    a, b = m.start(), m.end()
                    try: t = m.group().decode('cp932')
                    except UnicodeDecodeError: continue
                    core = t.strip(' 　')
                    if len([c for c in core if ord(c) > 0x7F]) < 2 or len(JP.findall(core)) < 2: continue
                    pairs = [core[i:i + 2] for i in range(len(core) - 1)]
                    if sum(x in bg for x in pairs) < 0.7 * len(pairs): continue
                    if any(s < b and a < e for s, e in cv): continue          # 추출 범위와 겹치면 추출됨(앞뒤 공백·레코드 머리 바이트 차이)
                    rows.append((rel, a, d[max(0, a - 4):a].hex(' '), t))
    seen = set(); uniq = []
    for r in rows:
        if (r[0], r[1]) in seen: continue
        seen.add((r[0], r[1])); uniq.append(r)
    os.makedirs(os.path.join(ROOT, 'work', 'trcheck'), exist_ok=True)
    with open(os.path.join(ROOT, 'work', 'trcheck', '텍스트누락후보.tsv'), 'w', encoding='utf-8-sig', newline='\n') as w:
        w.write('파일\t위치\t앞 바이트\t내용\n' + ''.join('%s\t%X\t%s\t%s\n' % r for r in uniq))
    c = collections.Counter(r[0] for r in uniq)
    print('누락 후보 %d줄' % len(uniq))
    for k, v in c.most_common(40): print('  %s: %d' % (k, v))


if __name__ == '__main__':
    main()
