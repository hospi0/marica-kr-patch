# -*- coding: utf-8 -*-
r"""자막 훅 PoC 빌드 (2026-10-25): SEN.BIN 에 훅·자막(data/poc_subs.tsv) → 트랙 1(SEN.BIN 은 커져서 파일 영역 끝으로, iso_patch) → work/build/poc/
  먼저 tools/test_hook.py(시뮬레이터 검산)가 통과해야 함."""
import os, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
import disc, hook as H, iso_patch, test_hook

NAME = 'Marica - Shinjitsu no Sekai (Japan)'
SRC = os.path.dirname(disc.BIN)
OUT = os.path.join(ROOT, 'work', 'build', 'poc')


def main():
    assert test_hook.main(), '시뮬레이터 검산 실패'
    sen = open(os.path.join(ROOT, 'work', 'disc', 'SEN.BIN'), 'rb').read()
    s, lab, texts, subs = H.patch_sen(sen)
    os.makedirs(OUT, exist_ok=True)
    dst = os.path.join(OUT, NAME + ' (Track 1).bin')
    iso_patch.patch(dst, {'/SEN.BIN': s})
    shutil.copyfile(os.path.join(SRC, NAME + ' (Track 2).bin'), os.path.join(OUT, NAME + ' (Track 2).bin'))
    shutil.copyfile(os.path.join(SRC, NAME + '.cue'), os.path.join(OUT, NAME + '.cue'))
    assert disc.read('/SEN.BIN', dst) == s
    for p in ('/BOOT.BIN', '/LAST.BIN', '/FLD/M00/MAC000.DAT', '/FLD/M00/PCM0104.AIF'):
        assert disc.read(p, dst) == disc.read(p), p
    print('끝 → %s' % OUT)


if __name__ == '__main__':
    main()
