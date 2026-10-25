# -*- coding: utf-8 -*-
r"""트랙 1 파일 바꿔 넣기(2026-10-10) — 마리카 배치에 맞춤(다이노 아일랜드 iso.py 를 옮김).
  원본: 파일들이 LBA 순으로 이어지고 마지막 진짜 파일(D_PART/CASE077.SP)이 LBA 260771 에서 끝, 그 뒤 150섹터 = 뒷간격(0 데이터), 트랙 1 = 260,921섹터.
        ★/DIN_TRY(LBA 261071, 4.6 MB)는 트랙 2(오디오) 자리를 가리키는 기록 → 트랙 1 이 늘면 같은 만큼 옮긴다.
        PVD 볼륨 크기 = 263,326(= DIN_TRY 끝) → 같이 늘린다.
  규칙: 새 파일이 원래 섹터 수 안이면 제자리(남는 곳 0), 넘치면 파일 영역 끝(260771 부터)에 차례로 붙이고 그 뒤 뒷간격 150섹터.
        디렉터리 기록 LBA·크기(양 엔디안), 쓴 섹터는 헤더·EDC/ECC 새로(유나 리믹스 iso.sector).
  from iso import patch; patch(dst, {'/BLDANIM.BIN': bytes, '/A_PART/S00100.ST2': bytes})
"""
import importlib.util, os, shutil, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import disc

_sp = importlib.util.spec_from_file_location('yuna_iso', r'C:\claude\project\yunaremix-kr-patch\tools\iso.py')
_y = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(_y)
sector = _y.sector
FILES_END = 273234; GAP = 150; TRACK = 273384          # 마리카(2026-10-25): 마지막 파일 FLD042.BIN 끝 273234, 뒷간격 150, /WAING = 트랙 2 가리킴


def records(f):
    """(경로, 디렉터리 섹터 LBA, 기록 자리) — 하위 폴더까지"""
    pvd = disc.sec(f, 16); out = []
    def walk(lba, size, pre):
        for k in range((size + 2047) // 2048):
            d = disc.sec(f, lba + k); i = 0
            while i < 2048 and d[i]:
                L = d[i]; nm = d[i + 33:i + 33 + d[i + 32]]
                if nm not in (b'\0', b'\1'):
                    n = nm.decode('latin1').split(';')[0]
                    l2, s2 = struct.unpack_from('<I', d, i + 2)[0], struct.unpack_from('<I', d, i + 10)[0]
                    if d[i + 25] & 2: walk(l2, s2, pre + n + '/')
                    else: out.append((pre + n, lba + k, i, l2, s2))
                i += L
    walk(struct.unpack_from('<I', pvd, 158)[0], struct.unpack_from('<I', pvd, 166)[0], '/')
    return out


def patch(dst, files, log=print):
    src = disc.BIN
    f = open(src, 'rb'); recs = {r[0]: r for r in records(f)}
    assert os.path.getsize(src) == TRACK * 2352
    plan = {}; cur = FILES_END
    for name, data in files.items():
        _, dl, di, lba, size = recs[name]
        if (len(data) + 2047) // 2048 <= (size + 2047) // 2048:
            plan[name] = lba
        else:
            plan[name] = cur; cur += (len(data) + 2047) // 2048
    grow = cur - FILES_END
    newsec = TRACK + grow
    with open(dst, 'wb') as o:
        f.seek(0)
        left = FILES_END * 2352
        while left:
            b = f.read(min(left, 1 << 24)); o.write(b); left -= len(b)
        for lba in range(FILES_END, newsec):                   # 새 자리 + 뒷간격(0, 헤더 새로)
            o.write(sector(lba, bytes(2048)))
    with open(dst, 'r+b') as o:
        for name, data in files.items():
            lba = plan[name]; _, dl, di, olba, osize = recs[name]
            n = max((len(data) + 2047) // 2048, (osize + 2047) // 2048 if lba == olba else 0)
            for k in range(n):
                o.seek((lba + k) * 2352); o.write(sector(lba + k, data[k * 2048:(k + 1) * 2048].ljust(2048, b'\0')))
        dirs = {}
        def setrec(name, lba, size):
            _, dl, di, _, _ = recs[name]
            if dl not in dirs:
                o.seek(dl * 2352 + 16); dirs[dl] = bytearray(o.read(2048))
            d = dirs[dl]
            struct.pack_into('<I', d, di + 2, lba); struct.pack_into('>I', d, di + 6, lba)
            struct.pack_into('<I', d, di + 10, size); struct.pack_into('>I', d, di + 14, size)
        for name, data in files.items(): setrec(name, plan[name], len(data))
        if grow:
            _, _, _, tl, ts = recs['/WAING']; setrec('/WAING', tl + grow, ts)
        for dl, d in dirs.items():
            o.seek(dl * 2352); o.write(sector(dl, bytes(d)))
        if grow:
            o.seek(16 * 2352 + 16); p = bytearray(o.read(2048))
            v = struct.unpack_from('<I', p, 80)[0] + grow
            struct.pack_into('<I', p, 80, v); struct.pack_into('>I', p, 84, v)
            o.seek(16 * 2352); o.write(sector(16, bytes(p)))
    # 검산
    for name, data in files.items():
        assert disc.read(name, dst) == data, name
    log('트랙 1: %d → %d섹터(+%d) · %s' % (TRACK, newsec, grow, ', '.join('%s@%d' % (n, plan[n]) for n in files)))
    return grow


def relayout(dst, files, log=print):
    """전체 재배치 — 모든 파일을 원래 LBA 순서대로 빈틈없이 다시 잇는다(바뀐 파일은 새 크기로).
       디렉터리·경로표 섹터(첫 파일 앞)는 자리 그대로, 기록의 LBA·크기만 고침. 마지막 파일 뒤 뒷간격 150섹터.
       DIN_TRY(트랙 2 가리킴)는 늘어난 섹터만큼 옮기고 PVD 볼륨 크기도 같이."""
    src = disc.BIN
    f = open(src, 'rb'); recs = records(f)
    real = sorted((r for r in recs if r[0] != '/WAING'), key=lambda r: r[3])
    first = real[0][3]
    cur = first; place = {}
    for name, dl, di, lba, size in real:
        data = files.get(name)
        n = (len(data if data is not None else b'') + 2047) // 2048 if data is not None else (size + 2047) // 2048
        place[name] = cur; cur += max(n, 1)
    end = cur; grow = end - FILES_END; newsec = end + GAP
    with open(dst, 'wb') as o:
        f.seek(0); o.write(f.read(first * 2352))
        for name, dl, di, lba, size in real:
            data = files.get(name)
            if data is None and place[name] == lba:
                f.seek(lba * 2352); o.write(f.read(((size + 2047) // 2048 or 1) * 2352)); continue
            if data is None:                                    # 내용 그대로, 자리만 옮김 → 헤더 새로
                f.seek(lba * 2352); n = (size + 2047) // 2048 or 1
                for k in range(n):
                    raw = f.read(2352); o.write(sector(place[name] + k, raw[16:16 + 2048]))
                continue
            n = (len(data) + 2047) // 2048 or 1
            for k in range(n):
                o.write(sector(place[name] + k, data[k * 2048:(k + 1) * 2048].ljust(2048, b'\0')))
        for lba in range(end, newsec):
            o.write(sector(lba, bytes(2048)))
    with open(dst, 'r+b') as o:
        dirs = {}
        def setrec(dl, di, lba, size):
            if dl not in dirs:
                o.seek(dl * 2352 + 16); dirs[dl] = bytearray(o.read(2048))
            d = dirs[dl]
            struct.pack_into('<I', d, di + 2, lba); struct.pack_into('>I', d, di + 6, lba)
            struct.pack_into('<I', d, di + 10, size); struct.pack_into('>I', d, di + 14, size)
        for name, dl, di, lba, size in real:
            setrec(dl, di, place[name], len(files[name]) if name in files else size)
        for name, dl, di, lba, size in recs:
            if name == '/WAING': setrec(dl, di, lba + grow, size)
        for dl, d in dirs.items():
            o.seek(dl * 2352); o.write(sector(dl, bytes(d)))
        o.seek(16 * 2352 + 16); p = bytearray(o.read(2048))
        v = struct.unpack_from('<I', p, 80)[0] + grow
        struct.pack_into('<I', p, 80, v); struct.pack_into('>I', p, 84, v)
        o.seek(16 * 2352); o.write(sector(16, bytes(p)))
    for name, data in files.items():
        assert disc.read(name, dst) == data, name
    log('트랙 1: %d → %d섹터(+%d) · 바뀐 파일 %d' % (TRACK, newsec, grow, len(files)))
    return grow
