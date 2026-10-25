# -*- coding: utf-8 -*-
r"""한글판 디스크 빌드(2026-10-25): tools/build_text.py 결과(work/build/files/ — 글꼴·MAC 대사·SEN_DATA·TITLE·SEN.BIN)
  + 음성 자막 본 훅(subhook.patch_sen — 실행 중 글자 찍기) + 음성 AIFF 마다 «MSUB» 덩어리(subdata) → 트랙 1(iso_patch) → work/build/kr/
  (2026-10-25 PoC 훅 hook.patch_sen 에서 바꿈 — 예전 판 work/build_kr_poc_bak.py)
  python tools/build_kr.py   (먼저 tools/build_text.py)"""
import os, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
import disc, subhook as SH, subdata as SD, iso_patch, test_sub

NAME = 'Marica - Shinjitsu no Sekai (Japan)'
SRC = os.path.dirname(disc.BIN)
FILES = os.path.join(ROOT, 'work', 'build', 'files')
OUT = os.path.join(ROOT, 'work', 'build', 'kr')


def main():
    assert test_sub.main(preview=False), '시뮬레이터 검산 실패'
    files = {}
    for dp, _, fs in os.walk(FILES):
        for f in fs:
            p = os.path.join(dp, f); files['/' + os.path.relpath(p, FILES).replace(os.sep, '/')] = open(p, 'rb').read()
    sen = files.get('/SEN.BIN') or open(os.path.join(ROOT, 'work', 'disc', 'SEN.BIN'), 'rb').read()
    idx, bits, advs, chunks, npage, big = SD.build()
    files['/SEN.BIN'], lab, lay = SH.patch_sen(sen, bits, advs)
    assert big + 8 <= SH.SUBMAX, ('자막 덩어리가 SUBBUF 보다 큼', big)
    nv = 0
    for v, ch in chunks.items():
        p = '/' + v + '.AIF'
        files[p] = SD.insert_chunk(disc.read(p), ch); nv += 1
    print('자막: 음성 %d · 쪽 %d · 글자 %d · 가장 큰 덩어리 %d B · 블록 끝 0x%08X' % (nv, npage, len(idx), big, lay['END']))
    os.makedirs(OUT, exist_ok=True)
    dst = os.path.join(OUT, NAME + ' (Track 1).bin')
    iso_patch.patch(dst, files)
    for ext in (' (Track 2).bin', '.cue'): shutil.copyfile(os.path.join(SRC, NAME + ext), os.path.join(OUT, NAME + ext))
    for p, b in files.items(): assert disc.read(p, dst) == b, ('다시 읽기 다름', p)
    for p in ('/BOOT.BIN', '/LAST.BIN', '/OPEN.BIN'):
        assert disc.read(p, dst) == disc.read(p), p
    print('파일 %d개 바꿈·검산 → %s' % (len(files), OUT))


if __name__ == '__main__':
    main()
