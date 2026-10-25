# -*- coding: utf-8 -*-
r"""음성 전체 다시 받아쓰기 — 등장인물·용어 초기 프롬프트판 (2026-10-25, 하스피 «받아쓰기 개판»)
  tools/asr_all.py 와 같고 initial_prompt 에 고유명사 목록만 더함(«ケイコ»를 «稽古»로 적는 등 동음 오인식 줄이기).
  → work/asr2/<폴더>_<파일>.json (이어 돌리기 가능). 비교·수정안 = tools/asr_diff.py
  C:\claude\utils\whisper-venv\Scripts\python.exe tools/asr_prompt.py"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from asr_probe import load_aif

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'work', 'asr2')
PROMPT = ('神崎まりか、マリカ、金本あきら、アキラ、東堂かなめ、カナメ、ハイジマケイコ、ケイコ、蕪木、カブラギ、八巻信長、'
          'オルガ、ガリーナ、ムハマド、ロネット、フランソワーズ、真実の人、真実の徒、サイキ、超能力、獣人、装甲姉妹、'
          '冬木堂、フルメタルカフェ、茨博士、キラーゼロ、トゥルーマン、ソロモン、ハーミオン、賢人同盟、時計男、'
          '加妻新島、南千住、錦糸町、渋谷、代々木、西馬込。')


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
        segs, _ = m.transcribe(a, language='ja', beam_size=5, condition_on_previous_text=False, vad_filter=False, initial_prompt=PROMPT)
        segs = [[round(s.start, 2), round(s.end, 2), s.text.strip()] for s in segs]
        json.dump({'file': rel, 'sec': round(len(a) / 16000, 2), 'segs': segs}, open(dst, 'w', encoding='utf-8'), ensure_ascii=False)
        done += 1
        if done % 20 == 0:
            print('%d/%d %.0fs' % (k + 1, len(files), time.time() - t0), flush=True)
    print('끝 %d개 %.0fs' % (done, time.time() - t0), flush=True)


if __name__ == '__main__':
    main()
