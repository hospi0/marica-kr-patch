# -*- coding: utf-8 -*-
r"""애매한 줄 받아쓰기 집중 재작업 (2026-10-25) — work/reasr/targets.json(메모 달린 줄·번역 빈칸·환청 의심 문구) 대상.
  줄마다 [시작−0.6, 끝+0.6] 구간을 잘라(«받아쓰기 없음»은 음성 통째) 위스퍼 large-v3 두 번:
    A = 빔 5·온도 0·VAD 끔·앞 줄 받아쓰기+인물 이름을 힌트(initial_prompt)
    B = 빔 5·온도 0·힌트 없음(힌트가 끌고 가는 환청 견제)
  + 구간 소리 크기(RMS dBFS, 0.1초 창 최대) → −45 dB 아래면 «무음».
  → work/reasr/result.json [{번호, 음성, 시작, 끝, 원 받아쓰기, A, B, 소리 dB, 판정}]
  C:\claude\utils\whisper-venv\Scripts\python.exe tools/reasr.py"""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from asr_probe import load_aif

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAMES = 'マリカ、神崎マリカ、ゼロ、オルガ、カナメ、カブラギ、FC-1、バルブ、念動力'


def level_db(a):
    if len(a) < 1600: return -99.0
    w = a[:len(a) // 1600 * 1600].reshape(-1, 1600)
    r = np.sqrt((w ** 2).mean(1)).max()
    return float(20 * np.log10(max(r, 1e-6)))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    from faster_whisper import WhisperModel
    m = WhisperModel('large-v3', device='cuda', compute_type='float16')
    T = json.load(open(os.path.join(ROOT, 'work', 'reasr', 'targets.json'), encoding='utf-8'))
    allrows = {}
    import glob
    for f in sorted(glob.glob(os.path.join(ROOT, 'data', '번역', '음성자막_*.tsv'))):
        for ln in open(f, encoding='utf-8-sig').read().split('\n')[1:]:
            if ln: c = ln.split('\t'); allrows[c[0]] = c
    order = sorted(allrows)
    cache = {}; out = []
    for k, (c, why) in enumerate(T):
        no, voice, t0, t1, asr = c[0], c[1], float(c[2]), float(c[3]), c[4]
        if voice not in cache:
            cache.clear(); cache[voice] = load_aif(os.path.join(ROOT, 'work', 'disc', *voice.split('/')) + '.AIF')[0]
        a = cache[voice]
        whole = asr.startswith('(받아쓰기 없음)')
        s0 = 0 if whole else max(0, int((t0 - 0.6) * 16000)); s1 = len(a) if whole else min(len(a), int((t1 + 0.6) * 16000))
        seg = a[s0:s1]
        i = order.index(no); prev = allrows[order[i - 1]][4] if i and allrows[order[i - 1]][1] == voice else ''
        res = {}
        for tag, prompt in (('A', (NAMES + '。' + prev)[-200:]), ('B', None)):
            segs, _ = m.transcribe(seg, language='ja', beam_size=5, temperature=0, condition_on_previous_text=False,
                                   vad_filter=False, initial_prompt=prompt)
            res[tag] = ''.join(s.text.strip() for s in segs)
        db = level_db(a[int(t0 * 16000):int(t1 * 16000)] if not whole else seg)
        if db < -45: verdict = '무음'
        elif res['A'] == res['B'] and res['A'] == asr: verdict = '같음'
        elif res['A'] == res['B']: verdict = '새 받아쓰기(두 번 일치)'
        else: verdict = '갈림'
        out.append({'번호': no, '음성': voice, '시작': t0, '끝': t1, '원': asr, 'A': res['A'], 'B': res['B'], 'dB': round(db, 1),
                    '판정': verdict, '이유': why, '메모': c[6] if len(c) > 6 else '', '번역': c[5]})
        if (k + 1) % 50 == 0: print(k + 1, flush=True)
    json.dump(out, open(os.path.join(ROOT, 'work', 'reasr', 'result.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    from collections import Counter
    print(Counter(o['판정'] for o in out))


if __name__ == '__main__':
    main()
