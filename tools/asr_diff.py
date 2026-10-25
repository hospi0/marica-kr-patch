# -*- coding: utf-8 -*-
r"""받아쓰기 비교 (2026-10-25) — work/asr(처음) vs work/asr2(용어 프롬프트판, tools/asr_prompt.py)
  자막 줄(data/번역/음성자막_*.tsv: 번호·음성·시작·끝·받아쓰기·번역)마다 같은 시간대의 새 문장을 모아 옛 받아쓰기와 견줌.
  · 이름 줄: 새 쪽에만 고유명사(PROMPT 낱말)가 있는 줄 — 동음 오인식(ケイコ→稽古 등) 후보, 맨 앞
  · 다름 줄: 글자 비슷도 < 0.6
  · 지어냄 의심: 새 문장에 프롬프트 낱말이 3개 넘게 나열됨(무음 구간 환각) → 버림
  python tools/asr_diff.py → work/reasr/받아쓰기_비교2.tsv (구분·번호·음성·시작·끝·옛 받아쓰기·새 받아쓰기·지금 자막)"""
import difflib, glob, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
from asr_prompt import PROMPT

TERMS = [t for t in re.split('[、。]', PROMPT) if t]
NORM = re.compile(r'[\s、。,.!?！？…・「」『』\-ー~〜]')
HIRA = str.maketrans({chr(c): chr(c - 0x60) for c in range(0x30A1, 0x30F7)})    # 가타카나 → 히라가나(マリカ/まりか 같은 표기 차이는 같다고 봄)
JUNK = ('ご視聴', 'ありがとうございました', 'チャンネル登録')
KO = {'神崎まりか': '마리카', 'マリカ': '마리카', '金本あきら': '아키라', 'アキラ': '아키라', '東堂かなめ': '카나메', 'カナメ': '카나메',
      'ハイジマケイコ': '케이코', 'ケイコ': '케이코', '蕪木': '카부라기', 'カブラギ': '카부라기', '八巻信長': '노부나가', 'オルガ': '올가',
      'ガリーナ': '갈리나', 'ムハマド': '무하마드', 'ロネット': '로네트', 'フランソワーズ': '프랑소와즈', '真実の人': '진실의 사람',
      '真実の徒': '진실의 무리', 'サイキ': '사이키', '超能力': '초능력', '獣人': '수인', '装甲姉妹': '장갑', '冬木堂': '후유키도',
      'フルメタルカフェ': '풀 메탈|풀메탈', '茨博士': '이바라', 'キラーゼロ': '킬러 제로|킬러제로', 'トゥルーマン': '트루먼', 'ソロモン': '솔로몬',
      'ハーミオン': '하미온|허마이오니', '賢人同盟': '현인', '時計男': '시계남|시계 남', '加妻新島': '가쓰마', '南千住': '미나미센주',
      '錦糸町': '긴시초', '渋谷': '시부야', '代々木': '요요기', '西馬込': '니시마고메'}


def load(d):
    out = {}
    for f in glob.glob(os.path.join(ROOT, 'work', d, '*.json')):
        j = json.load(open(f, encoding='utf-8')); out[j['file'][:-4].replace('_', '/', 2)] = j['segs']
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    new = load('asr2')
    cur = {}
    for l in open(os.path.join(ROOT, 'work', 'tr', 'voice.tsv'), encoding='utf-8-sig').read().split('\n')[1:]:
        if l: c = l.split('\t'); cur[c[0]] = c[4]
    rows = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'data', '번역', '음성자막_*.tsv'))):
        L = open(f, encoding='utf-8-sig').read().split('\n')
        for l in L[1:]:
            c = l.split('\t')
            if len(c) < 6: continue
            n, v, t0, t1, old = c[0], c[1], float(c[2]), float(c[3]), c[4]
            segs = new.get(v)
            if segs is None: continue
            got = ''.join(s[2] for s in segs if s[0] < t1 - 0.15 and s[1] > t0 + 0.15)
            if sum(t in got for t in TERMS) > 3: continue                       # 프롬프트 환각
            if not got.strip() or any(j in got for j in JUNK):                # 새 쪽 환청·빈 줄 = 말소리 없는 자리일 가능성 → 옛 받아쓰기도 환청 의심
                if cur.get(n, '').strip(): rows.append(('환청?', n, v, c[2], c[3], old, got, cur.get(n, '')))
                continue
            a, b = NORM.sub('', old).translate(HIRA), NORM.sub('', got).translate(HIRA)
            if a and b:                                                         # 새 쪽은 문장을 길게 묶음 → 옛 받아쓰기와 맞는 구간만 잘라 견줌
                bl = [m for m in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks() if m.size]
                if bl:
                    s0 = max(0, bl[0].b - bl[0].a); e0 = min(len(b), bl[-1].b + bl[-1].size + (len(a) - bl[-1].a - bl[-1].size))
                    b = b[s0:e0]
            got = b
            if a == b: continue
            names = [t for t in TERMS if t.translate(HIRA) in b and t.translate(HIRA) not in a
                     and not any(k in cur.get(n, '') for k in KO.get(t, '').split('|') if k)]   # 자막에 이미 그 이름이 있으면 고칠 것 없음
            sim = difflib.SequenceMatcher(None, a, b).ratio()
            if names: kind = '이름:' + '·'.join(names)
            elif sim < 0.6: kind = '다름 %.2f' % sim
            else: continue
            rows.append((kind, n, v, c[2], c[3], old, got, cur.get(n, '')))
    rows.sort(key=lambda r: (0 if r[0].startswith('이름') else 1 if r[0].startswith('환청') else 2, r[1]))   # 이름 → 환청? → 다름
    os.makedirs(os.path.join(ROOT, 'work', 'reasr'), exist_ok=True)
    out = os.path.join(ROOT, 'work', 'reasr', '받아쓰기_비교2.tsv')
    with open(out, 'w', encoding='utf-8-sig', newline='\n') as w:
        w.write('구분\t번호\t음성\t시작\t끝\t옛 받아쓰기\t새 받아쓰기\t지금 자막\n' + ''.join('\t'.join(r) + '\n' for r in rows))
    print('이름 %d · 다름 %d → %s' % (sum(r[0].startswith('이름') for r in rows), sum(r[0].startswith('다름') for r in rows), out))


if __name__ == '__main__':
    main()
