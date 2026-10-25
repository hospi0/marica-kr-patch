# -*- coding: utf-8 -*-
r"""마리카 배포 묶음 — dist/Marica_KR_<VER>/ : 트랙 1 xdelta + xdelta.exe + readme.txt(CP949) + 한글패치_적용.bat(CP949)
  (건블레이즈 tools/make_dist.py 를 옮김) 바뀌는 트랙: 트랙 1 만(트랙 2 = 오디오, cue 그대로) · 트랙 1 은 음성 자막 덩어리로 커짐.
  검증: 원본 트랙 1 → xdelta 적용 → md5 = 빌드(work/build/kr) 트랙 1 md5.
  python tools/make_dist.py   (먼저 python tools/build_text.py · tools/opening.py build · tools/build_kr.py)
"""
import hashlib, os, shutil, subprocess, sys, zipfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)

VER = 'v0.9'
XDELTA = r'C:\claude\utils\xdelta.exe'
SRC = r'C:\claude\roms\ss\Marica - Shinjitsu no Sekai (Japan)'
OUT = os.path.join(ROOT, 'work', 'build', 'kr')
ROM = 'Marica - Shinjitsu no Sekai (Japan)'
NAME = 'Marica_KR_' + VER
TITLE = '마리카 ~진실의 세계~ (Marica - Shinjitsu no Sekai, 세가 새턴 일본판) 한글 패치 ' + VER


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest().upper()


README = """{title}
{line}

2개의 트랙으로 이루어진 {rom} 의
트랙 1번에 패치하시면 됩니다.

원본md5 : {o}
패치md5 : {d}

입니다.


[ 적용 방법 ]

  1) 원본 트랙 1 파일을 이 폴더에 복사
       "{bin}"
  2) 한글패치_적용.bat 실행 → 이름 끝에 [KR] 이 붙은 파일이 만들어집니다
  3) 만든 파일 이름을 원본 트랙 1 이름으로 바꿔 넣고, 트랙 2(오디오)와 cue 는 원본 그대로 쓰세요
     (패치한 트랙 1 은 원본보다 약 {grow} MB 커집니다 - 음성 자막 자료 때문이며 정상입니다)

  직접 적용:
    xdelta.exe -d -s "원본 트랙 1" "{patch}" "결과 파일"
  (Delta Patcher 같은 xdelta3 GUI 도구로 적용해도 됩니다. 원본이 다르면 xdelta 가 적용을 거부합니다.)


[ 바뀌는 것 ]

  - 필드 대사·선택지 전체, 메뉴, 아이템·장비 이름과 설명, 전투 메시지, 장소 이름, 저장·불러오기 화면
  - 음성 대사에 한글 자막(음성만 나오는 장면 포함) - 화면 아래에 표시됩니다
  - 타이틀 로고 부제 "~진실의 세계~", 오프닝 인물 소개·스태프 크레딧, 백업 램 안내 화면
  - 옵션 화면(BGM 테스트 곡 이름 포함)


[ 알려진 점 ]

  - 음성 자막은 음성을 받아쓰기한 뒤 번역했습니다. 일부 짧은 외침·뭉개진 대사는
    원문과 조금 다르거나 자막이 없을 수 있습니다.
  - 자막 표시 시점이 소리와 약간 어긋나는 곳이 있을 수 있습니다.
  - 칸이 고정된 일부 메뉴는 짧은 말로 줄였습니다(장비 "방어" 등).
  - 음성은 원본 일본어 그대로입니다.
"""

BAT = r"""@echo off
chcp 949 >nul
set "XD=%~dp0xdelta.exe"
if not exist "%~dp0{bin}" (
  echo   [오류] 원본 트랙 1 파일을 이 폴더에 넣어 주세요 - readme 참고.
  pause & exit /b 1
)
"%XD%" -d -f -s "%~dp0{bin}" "%~dp0{patch}" "%~dp0{kbin}"
if errorlevel 1 (
  echo   [오류] 패치 실패 - 원본이 다를 수 있습니다 - readme 의 원본md5 확인.
  pause & exit /b 1
)
echo   완료: "{kbin}"
pause
"""


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    d = os.path.join(ROOT, 'dist', NAME)
    if os.path.isdir(d):
        shutil.rmtree(d)
    os.makedirs(d)
    b = '%s (Track 1).bin' % ROM
    src, out = os.path.join(SRC, b), os.path.join(OUT, b)
    patch = NAME + '_Track1.xdelta'; pp = os.path.join(d, patch)
    subprocess.run([XDELTA, '-e', '-9', '-B', '536870912', '-f', '-s', src, out, pp], check=True)
    chk = os.path.join(d, '_check.bin')
    subprocess.run([XDELTA, '-d', '-f', '-s', src, pp, chk], check=True)
    o, want, got = md5(src), md5(out), md5(chk)
    os.remove(chk)
    assert got == want, ('패치 적용 결과가 빌드와 다름', got, want)
    grow = round((os.path.getsize(out) - os.path.getsize(src)) / 1048576)
    print('트랙 1 원본md5 %s → 패치md5 %s · %s %d B' % (o, want, patch, os.path.getsize(pp)))
    shutil.copy2(XDELTA, os.path.join(d, 'xdelta.exe'))
    kbin = '%s (Track 1) [KR].bin' % ROM
    readme = README.format(title=TITLE, line='=' * 60, rom=ROM, o=o, d=want, bin=b, patch=patch, grow=grow)
    open(os.path.join(d, 'readme.txt'), 'wb').write(readme.replace('\n', '\r\n').encode('cp949'))
    open(os.path.join(d, '한글패치_적용.bat'), 'wb').write(BAT.format(bin=b, patch=patch, kbin=kbin).replace('\n', '\r\n').encode('cp949'))
    z = os.path.join(ROOT, 'dist', NAME + '.zip')
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(os.listdir(d)):
            zf.write(os.path.join(d, f), NAME + '/' + f)
    print('✅', d)
    for f in sorted(os.listdir(d)):
        print('  %-56s %12d' % (f, os.path.getsize(os.path.join(d, f))))
    print('  zip %s %d B · md5 %s' % (os.path.basename(z), os.path.getsize(z), md5(z)))


if __name__ == '__main__':
    main()
