# -*- coding: utf-8 -*-
r"""AIFF(8비트 모노) 음성 받아쓰기 시험 (2026-10-25) — utils/whisper-venv 로 실행.
  C:\claude\utils\whisper-venv\Scripts\python.exe tools/asr_probe.py <AIF …>"""
import struct, sys
import numpy as np


def load_aif(p):
    d = open(p, 'rb').read(); assert d[:4] == b'FORM' and d[8:12] == b'AIFF'
    i = 12; ch = bits = None; rate = None; pcm = None
    while i < len(d) - 8:
        cid = d[i:i + 4]; n = struct.unpack('>I', d[i + 4:i + 8])[0]; body = d[i + 8:i + 8 + n]
        if cid == b'COMM':
            ch, frames, bits = struct.unpack('>hIh', body[:8])
            e = struct.unpack('>H', body[8:10])[0]; m = struct.unpack('>Q', body[10:18])[0]
            rate = m * 2.0 ** (e - 16383 - 63)
        elif cid == b'SSND':
            off = struct.unpack('>I', body[:4])[0]; pcm = body[8 + off:]
        i += 8 + n + (n & 1)
    a = np.frombuffer(pcm, np.int8).astype(np.float32) / 128 if bits == 8 else np.frombuffer(pcm, '>i2').astype(np.float32) / 32768
    if ch == 2: a = a.reshape(-1, 2).mean(1)
    n16 = int(len(a) * 16000 / rate)
    return np.interp(np.linspace(0, len(a) - 1, n16), np.arange(len(a)), a).astype(np.float32), rate


if __name__ == '__main__':
    from faster_whisper import WhisperModel
    m = WhisperModel('large-v3', device='cuda', compute_type='float16')
    sys.stdout.reconfigure(encoding='utf-8')
    for p in sys.argv[1:]:
        a, r = load_aif(p)
        segs, _ = m.transcribe(a, language='ja', beam_size=5, condition_on_previous_text=False, vad_filter=False)
        print(p.split('/')[-1], '%.1fs' % (len(a) / 16000), ''.join(s.text for s in segs))
