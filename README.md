# 마리카 \~진실의 세계\~ (Marica - Shinjitsu no Sekai, 세가 새턴 일본판) 한글 패치

배포: [Releases](../../releases) 의 `Marica_KR_v0.9.zip` — 트랙 1 xdelta + 적용 bat + readme.

- 원본 트랙 1 md5 `A7F2AED45CC7DDB017FA60258560B119` → 패치 후 `B96AC96F5417D0778D410A66EF3B94D2`
- 필드 대사·선택지·메뉴·아이템·전투·장소·저장 화면 한글화
- 음성 대사 한글 자막(실행 중 글자 찍기 훅, 갈무리14) — 음성 AIFF 마다 자막 덩어리
- 타이틀 부제, 오프닝 인물 소개·스태프 크레딧, 두 번째 타이틀, 백업 램 안내 화면 그림

## 빌드

1. `python tools/extract.py` — 원본 트랙 1 에서 파일 추출(work/disc)
2. `python tools/tr_check.py` — 번역(data/번역) 검사·용어(data/용어.tsv)·고침(data/고침.tsv) → work/tr
3. `python tools/title_logo.py build` · `python tools/backup_msg.py build` — TITLE.BIN 그림
4. `python tools/build_text.py` — 글꼴·대사·메뉴 → work/build/files
5. `python tools/opening.py build` — 오프닝 그림(LAST/O01.D)
6. `python tools/build_kr.py` — 자막 훅(tools/subhook.py·subdata.py, 시뮬 검사 test_sub.py) + 트랙 1 → work/build/kr
7. `python tools/make_dist.py` — 배포 묶음

자세한 구조·이력은 `docs/00_초기조사.md`, `docs/00_이어하기.md`, `docs/01_버그판독_20261025.md`.
