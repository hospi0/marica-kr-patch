# -*- coding: utf-8 -*-
r"""음성 전체 받아쓰기 (2026-10-25) — utils/whisper-venv 로 실행, 이어 돌리기 가능.
  work/disc 아래 AIF 전부 → work/asr/<폴더>_<파일>.json  {"file","sec","segs":[[시작,끝,문장],…]}
  위스퍼 large-v3, 일본어, VAD 끔(짧은 외침을 버리지 않게), 문장별 시각.
  C:\claude\utils\whisper-venv\Scripts\python.exe tools/asr_all.py"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from asr_probe import load_aif

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'work', 'asr')


def main():
    from faster_whisper import WhisperModel
    m = WhisperModel('large-v3', device='cuda', compute_type='float16')
    os.makedirs(OUT, exist_ok=True)
    files = []
    for dp, _, fs in os.walk(os.path.join(ROOT, 'work', 'disc')):
        for f in sorted(fs):
            if f.upper().endswith('.AIF'): files.append(os.path.join(dp, f))
    files.sort()
    t0 = time.time(); done = 0
    for k, p in enumerate(files):
        rel = os.path.relpath(p, os.path.join(ROOT, 'work', 'disc')).replace(os.sep, '_')
        dst = os.path.join(OUT, rel[:-4] + '.json')
        if os.path.exists(dst): continue
        a, r = load_aif(p)
        segs, _ = m.transcribe(a, language='ja', beam_size=5, condition_on_previous_text=False, vad_filter=False)
        segs = [[round(s.start, 2), round(s.end, 2), s.text.strip()] for s in segs]
        json.dump({'file': rel, 'sec': round(len(a) / 16000, 2), 'segs': segs}, open(dst, 'w', encoding='utf-8'), ensure_ascii=False)
        done += 1
        if done % 20 == 0:
            print('%d/%d %.0fs' % (k + 1, len(files), time.time() - t0), flush=True)
    print('끝 %d개 %.0fs' % (done, time.time() - t0), flush=True)


if __name__ == '__main__':
    main()
