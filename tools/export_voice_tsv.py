# -*- coding: utf-8 -*-
"""음성 자막 번역 TSV 뽑기 (2026-10-25): work/asr/*.json(위스퍼 받아쓰기) → data/번역할것/음성자막_NN.tsv (20 KB 단위)
  열: 번호 · 음성(폴더/파일) · 시작(초) · 끝(초) · 받아쓰기 · 번역 · 메모
  · 한 음성 안 문장은 시간 순 — 같은 PCM 번호가 폴더마다 다른 음성(FLD/M00/PCM0101 ≠ SEN/P01/PCM0101)이라 폴더까지 씀.
  · 받아쓰기가 빈 음성은 «(받아쓰기 없음)» 한 줄 — 외침·효과음일 수 있음, 들어 보고 채우거나 비워 두면 자막 없음.
  · 자막 한 줄은 화면 폭 기준 약 20자. 길면 «|» 로 쪽(화면)을 나눔 — 나눈 쪽은 그 문장 시간 안에서 글자 수 비율로 넘어감.
  python tools/export_voice_tsv.py"""
import glob, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', '번역할것')
SPLIT = 20 * 1024


def main():
    rows = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'work', 'asr', '*.json'))):
        j = json.load(open(f, encoding='utf-8'))
        voice = j['file'][:-4].replace('_', '/')
        segs = [s for s in j['segs'] if s[2].strip()]
        if not segs:
            rows.append((voice, 0.0, j['sec'], '(받아쓰기 없음)', '들어 보고 채우기'))
        for a, b, t in segs:
            rows.append((voice, a, b, t.strip(), ''))
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.startswith('음성자막_'): os.remove(os.path.join(OUT, f))
    head = '번호\t음성\t시작\t끝\t받아쓰기\t번역\t메모\n'
    lines = ['%05d\t%s\t%.2f\t%.2f\t%s\t\t%s\n' % (n, v, a, b, t, memo) for n, (v, a, b, t, memo) in enumerate(rows, 1)]
    files, cur, size = [], [], 0
    for ln in lines:
        nb = len(ln.encode('utf-8'))
        if cur and size + nb > SPLIT: files.append(cur); cur, size = [], 0
        cur.append(ln); size += nb
    if cur:
        if files and size < SPLIT // 4: files[-1] += cur
        else: files.append(cur)
    for k, ls in enumerate(files, 1):
        with open(os.path.join(OUT, '음성자막_%02d.tsv' % k), 'w', encoding='utf-8-sig', newline='\n') as w:
            w.write(head + ''.join(ls))
    print('음성 %d개 · 줄 %d · 글자 %d · 파일 %d → %s' % (len({r[0] for r in rows}), len(rows), sum(len(r[3]) for r in rows), len(files), OUT))


if __name__ == '__main__':
    main()
