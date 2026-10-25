# -*- coding: utf-8 -*-
r"""받아쓰기 집중 재작업 2차 (2026-10-25) — reasr.py(1차) 판정이 문장부호 차이까지 «갈림»으로 셈 → 고침.
  대상 = work/reasr/targets.json. 줄마다 위스퍼 large-v3 세 번(모두 VAD 끔·온도 0):
    A 구간 ±0.6초·빔 5·힌트(인물 이름 + 앞 줄)   B 구간 ±0.6초·빔 5·힌트 없음   C 구간 ±1.5초·빔 10·힌트(앞+뒤 줄)
  비교는 문장부호·공백 빼고. 흔한 환청 문구(ご視聴ありがとうございました 등)·빈 결과는 «무효».
  판정: 무음(구간 최대 −45 dB 아래) · 확정(유효 결과가 다 같음, 2개 이상) · 비언어(유효 결과 없음 + 소리 있음 = 웃음·비명·신음)
        · 고름(갈림 — 평균 로그확률 가장 높은 것, 사람 확인)
  → work/reasr/result2.json · work/reasr/받아쓰기_재작업.tsv(번호·음성·시작·끝·원 받아쓰기·새 받아쓰기·판정·A·B·C·dB·원 번역·메모)
  C:\claude\utils\whisper-venv\Scripts\python.exe tools/reasr2.py"""
import glob, json, os, re, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from asr_probe import load_aif

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAMES = 'マリカ、神崎まりか、金本アキラ、東堂カナメ、ゼロ、オルガ、カブラギ、FC-1、ファクト機関、バルブ、念動力、信長'
HALLU = re.compile(r'ご視聴|チャンネル登録|字幕|^ありがとうございました$|^おやすみなさい$|^[ぁ-んァ-ヶー]$')


def norm(s):
    return re.sub(r'[\s、。,.!?！？…・「」『』〜~ー\-]', '', s)


def level_db(a):
    if len(a) < 1600: return -99.0
    w = a[:len(a) // 1600 * 1600].reshape(-1, 1600)
    return float(20 * np.log10(max(np.sqrt((w ** 2).mean(1)).max(), 1e-6)))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    from faster_whisper import WhisperModel
    m = WhisperModel('large-v3', device='cuda', compute_type='float16')
    T = json.load(open(os.path.join(ROOT, 'work', 'reasr', 'targets.json'), encoding='utf-8'))
    rows = {}
    for f in sorted(glob.glob(os.path.join(ROOT, 'data', '번역', '음성자막_*.tsv'))):
        for ln in open(f, encoding='utf-8-sig').read().split('\n')[1:]:
            if ln: c = ln.split('\t'); rows[c[0]] = c
    order = sorted(rows)
    cache = {}; out = []
    for k, (c, why) in enumerate(T):
        no, voice, t0, t1, asr = c[0], c[1], float(c[2]), float(c[3]), c[4]
        if voice not in cache:
            cache.clear(); cache[voice] = load_aif(os.path.join(ROOT, 'work', 'disc', *voice.split('/')) + '.AIF')[0]
        a = cache[voice]; n = len(a)
        whole = asr.startswith('(받아쓰기 없음)')
        i = order.index(no)
        prev = rows[order[i - 1]][4] if i and rows[order[i - 1]][1] == voice else ''
        nxt = rows[order[i + 1]][4] if i + 1 < len(order) and rows[order[i + 1]][1] == voice else ''
        def cut(p): return a if whole else a[max(0, int((t0 - p) * 16000)):min(n, int((t1 + p) * 16000))]
        res = {}
        for tag, pad, beam, prompt in (('A', 0.6, 5, NAMES + '。' + prev), ('B', 0.6, 5, None), ('C', 1.5, 10, NAMES + '。' + prev + nxt)):
            segs, _ = m.transcribe(cut(pad), language='ja', beam_size=beam, temperature=0, condition_on_previous_text=False,
                                   vad_filter=False, initial_prompt=prompt[-220:] if prompt else None)
            segs = list(segs)
            txt = ''.join(s.text.strip() for s in segs)
            lp = float(np.mean([s.avg_logprob for s in segs])) if segs else -9.0
            ns = float(np.mean([s.no_speech_prob for s in segs])) if segs else 1.0
            res[tag] = (txt, round(lp, 3), round(ns, 3))
        db = level_db(a if whole else a[int(t0 * 16000):int(t1 * 16000)])
        valid = {t: v for t, v in res.items() if v[0] and not HALLU.search(v[0]) and v[2] < 0.8}
        normed = {norm(v[0]) for v in valid.values()}
        if db < -45: verdict, new = '무음', ''
        elif not valid: verdict, new = '비언어', ''
        elif len(valid) >= 2 and len(normed) == 1: verdict, new = '확정', valid.get('A', list(valid.values())[0])[0]
        else:
            best = max(valid.values(), key=lambda v: v[1]); verdict, new = '고름', best[0]
        if verdict == '확정' and norm(new) == norm(asr): verdict = '확정(원래와 같음)'
        out.append({'번호': no, '음성': voice, '시작': t0, '끝': t1, '원': asr, '새': new, '판정': verdict,
                    'A': res['A'], 'B': res['B'], 'C': res['C'], 'dB': round(db, 1), '번역': c[5], '메모': c[6] if len(c) > 6 else '',
                    '이유': why})
        if (k + 1) % 50 == 0: print(k + 1, flush=True)
    json.dump(out, open(os.path.join(ROOT, 'work', 'reasr', 'result2.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    with open(os.path.join(ROOT, 'work', 'reasr', '받아쓰기_재작업.tsv'), 'w', encoding='utf-8-sig', newline='\n') as w:
        w.write('번호\t음성\t시작\t끝\t원 받아쓰기\t새 받아쓰기\t판정\tA\tB\tC\tdB\t원 번역\t메모\n')
        for o in out:
            w.write('\t'.join(str(x) for x in (o['번호'], o['음성'], o['시작'], o['끝'], o['원'], o['새'], o['판정'],
                                                o['A'][0], o['B'][0], o['C'][0], o['dB'], o['번역'], o['메모'])) + '\n')
    from collections import Counter
    print(Counter(o['판정'] for o in out))


if __name__ == '__main__':
    main()
