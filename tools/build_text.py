# -*- coding: utf-8 -*-
r"""텍스트 빌더 (2026-10-25) — work/tr/text.tsv(tools/tr_check.py 결과) → work/build/files/ (바뀐 파일만) + work/build/text_report.tsv
  ① 글꼴: SJIS 정렬 표(SEN.BIN 0x630E8 · TITLE.BIN 0x82BC, 1,377자)의 가나·한자 칸을 한글 자원으로 — 번역에 쓰인 한글을
     칸에 배정(한자 칸 먼저)하고 갈무리11 을 16×14 칸의 12×12 자리(행 1~12, 열 1~12 = 원본 잉크 범위)에 그림.
     글꼴 = SEN_DATA.DAT 0xD000(반각 8×14 ×) · 0xE000(전각 16×14, 28 B) — TITLE.BIN 0x67800 에 같은 사본(둘 다 씀).
     번역문은 한글 → 그 칸의 SJIS 코드로 적음(게임은 SJIS 를 표에서 찾아 칸 번호로 그림).
  ② 대사·선택지 MAC*.DAT: tools/macscript.py 로 스크립트 구역(0x10000~0x20000)을 명령 단위로 걸어,
     대사 메시지(명령 1 줄들)·선택지(명령 2)를 새 줄로 바꿔 다시 잇고 진입표(u32)·명령 7 점프(u16)를 새 위치로. 파일 크기 그대로.
  ③ SEN_DATA.DAT 아이템 기록 등(문자열 뒤 00 1B + 0 여백): 칸 = 끝 표시 뒤 0 여백까지 — 그 안이면 다시 씀.
     길이 바이트 문자열(앞 바이트 = 길이+2)·그 밖 촘촘한 목록·TITLE/SEN.BIN 문자열: 원래 바이트 안이면 공백으로 채워 제자리.
     넘치는 것은 원본 그대로 두고 보고(⏳읽는 방식 확인 또는 줄임).
  python tools/build_text.py"""
import collections, glob, os, re, struct, sys
sys.path.insert(0, os.path.dirname(__file__))
import bdf, macscript as M

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISC = os.path.join(ROOT, 'work', 'disc')
OUT = os.path.join(ROOT, 'work', 'build', 'files')
GALMURI = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri11.bdf'
TAB_SEN, TAB_TITLE, NTAB = 0x630E8, 0x82BC, 1377
NAME_TAB = 0x654B4                                 # SEN.BIN 기본 이름 표 «まりかあきらかなめ»
FONT_DATA, FONT_TITLE = 0xD000, 0x67800
SP = '　'


def read(rel): return open(os.path.join(DISC, rel), 'rb').read()


def load_text():
    R = {}
    for l in open(os.path.join(ROOT, 'work', 'tr', 'text.tsv'), encoding='utf-8-sig').read().split('\n')[1:]:
        if l: n, s, t = l.split('\t'); R[n] = (s, t)
    loc = {}
    for l in open(os.path.join(ROOT, 'data', '번역할것', '_텍스트위치.tsv'), encoding='utf-8-sig').read().split('\n')[1:]:
        if l: n, ls = l.split('\t'); loc[n] = ls.split()
    return R, loc


# ───────── ① 글꼴 ─────────
def glyph_map(R):
    sen = read('SEN.BIN')
    T = [struct.unpack_from('>H', sen, TAB_SEN + 2 * i)[0] for i in range(NTAB)]
    chars = [bytes([c >> 8, c & 255]).decode('cp932', 'replace') for c in T]
    need = sorted({c for s, t in R.values() for c in t if '가' <= c <= '힣'})
    kanji = [i for i, c in enumerate(chars) if '一' <= c <= '龥' or c == '々']
    kana = [i for i, c in enumerate(chars) if 'ぁ' <= c <= 'ん' or 'ァ' <= c <= 'ヶ']
    slots = kanji + kana
    assert len(need) <= len(slots), ('글꼴 칸 모자람', len(need), len(slots))
    return {h: (slots[k], T[slots[k]]) for k, h in enumerate(need)}, T


def draw_glyphs(font_bytes, base, gmap):
    fnt = bdf.Font(GALMURI)
    b = bytearray(font_bytes)
    for h, (idx, code) in gmap.items():
        pts, _ = fnt.draw(h)
        rows = [0] * 14
        for x, y in pts:
            yy, xx = y - 2, x + 1                                   # 갈무리11 한글 잉크 행 3~13·열 0~10 → 칸 행 1~11·열 1~11(원본 잉크 1~12)
            assert 0 <= yy < 14 and 0 <= xx < 16, (h, x, y)
            rows[yy] |= 0x8000 >> xx
        p = base + 0x1000 + idx * 28
        b[p:p + 28] = b''.join(r.to_bytes(2, 'big') for r in rows)
    return bytes(b)


def encoder(gmap):
    rev = {h: code for h, (i, code) in gmap.items()}
    def enc(s):
        s = s.replace('·', '・')
        out = bytearray()
        for c in s:
            if c in rev: out += rev[c].to_bytes(2, 'big')
            else: out += c.encode('cp932')                       # 반각 ASCII·전각 부호(원본 글꼴) — 없으면 예외
        return bytes(out)
    return enc


# ───────── ② MAC ─────────
def rebuild_mac(d, edits, enc):
    """edits: {상대 위치(메시지 첫 기록): 번역 문자열} → 새 파일 바이트"""
    M.seen_set = set()
    ins = M.walk(d)
    W = lambda r: struct.unpack_from('>H', d, M.BASE + r)[0]
    starts = sorted(ins)
    end = max(r + v[2] for r, v in ins.items())
    # 바꿀 덩어리: (시작, 끝, 새 바이트)
    chunks = []; dcount = 0                                            # 명령 수 증감(메시지 줄 수 변화)
    for r, t in edits.items():
        mode, op, ln, _ = ins[r]
        if op == 1:                                                 # 메시지 = 이어진 명령 1 기록들
            q = r
            while q in ins and ins[q][1] == 1 and ins[q][0] == 1: q += ins[q][2]
            lines = t.split('{n}')
            nold = 0; qq = r
            while qq < q: nold += 1; qq += ins[qq][2]
            dcount += len(lines) - nold
            nb = b''
            for L in lines:
                bb = enc(L); nb += struct.pack('>HH', 1, len(bb)) + bb + (b'\0' if len(bb) & 1 else b'')
            chunks.append((r, q, nb))
        else:                                                       # 선택지 기록 하나
            bb = enc(t.replace('{n}', ''))
            chunks.append((r, r + ln, struct.pack('>HH', 2, len(bb)) + bb + (b'\0' if len(bb) & 1 else b'')))
    chunks.sort()
    for a, b in zip(chunks, chunks[1:]): assert a[1] <= b[0], '겹침'
    sec = d[M.BASE:M.BASE + end]
    new = bytearray(); shift = []                                    # (옛 위치, 늘어난 양 누적)
    p = 0; acc = 0
    for a, b, nb in chunks:
        new += sec[p:a]; new += nb; acc += len(nb) - (b - a); shift.append((b, acc)); p = b
    new += sec[p:]
    def newpos(old):
        add = 0
        for b, s in shift:
            if old >= b: add = s
            else: break
        return old + add
    assert len(new) <= 0x10000, ('스크립트 구역 64 KB 넘음', len(new))
    out = bytearray(d)
    out[M.BASE:M.BASE + 0x10000] = bytes(new) + bytes(0x10000 - len(new))
    # 진입표
    for k, e in enumerate(M.entries(d)):
        struct.pack_into('>I', out, M.BASE + 4 * k, newpos(e))
    # 명령 7 점프
    for r, (mode, op, ln, jf) in ins.items():
        for f in jf:
            v = W(f)
            if v: struct.pack_into('>H', out, M.BASE + newpos(f), newpos(v))
    # 검산: 새 파일을 다시 걸어 대사·선택지 글이 번역과 같은지
    M.seen_set = set()
    ins2 = M.walk(bytes(out))
    got = {}
    for r, (mode, op, ln, _) in ins2.items():
        if op in (1, 2) and mode in (1, 2):
            L = struct.unpack_from('>H', out, M.BASE + r + 2)[0]; got[r] = bytes(out[M.BASE + r + 4:M.BASE + r + 4 + L])
    for r, t in edits.items():
        q = newpos(r); lines = t.split('{n}') if ins[r][1] == 1 else [t.replace('{n}', '')]
        for L in lines:
            assert got.get(q) == enc(L), ('검산 실패', hex(r), L)
            q += 4 + len(enc(L)) + (len(enc(L)) & 1)
    assert len(ins2) == len(ins) + dcount, ('명령 수 달라짐', len(ins2), len(ins), dcount)
    return bytes(out)


# ───────── ③ 그 밖 문자열 ─────────
def is_ptr(d, p):
    """정렬 워드가 포인터(VDP1 0x25Cxxxxx · 하이 램 0x060xxxxx · 로 램 0x002xxxxx)인가 — 실행 파일 C 문자열 끝에 00 이 없을 때 뒤 표를 먹지 않게(SEN.BIN 0x63DC0 칸 주소 표)"""
    if p & 3 or p + 4 > len(d): return False
    return struct.unpack_from('>I', d, p)[0] >> 20 in (0x25C, 0x060, 0x002)


def seg_end(d, off, cstr):
    e = off
    while e < len(d) - 1:
        if d[e] == 0 and (cstr or d[e + 1] in (0x1A, 0x1B)): break
        if cstr and e > off and is_ptr(d, e): break
        e += 2 if d[e] >= 0x80 else 1
    return e


PAD = (b' ', b'\x81\x40')


def src_span(d, off, e, s):
    """원문 실제 자리: (앞 공백 바이트 수, 원문 끝, 뒤 공백까지 끝) — 위치가 앞 공백부터 잡히고 원문 열은 공백을 뺀 줄이 많음(«　　装　備　　»).
    원문을 못 찾으면 None(예전처럼 e 까지)."""
    sb = s.replace('{n}', '').encode('cp932', 'replace')
    p = off
    while p < e and d[p:p + len(sb)] != sb:
        if d[p:p + 1] == b' ': p += 1
        elif d[p:p + 2] == b'\x81\x40': p += 2
        else: return None
    if p >= e or not sb: return None
    se = min(p + len(sb), e)
    q = se
    while q < e:                                                    # 뒤 공백 채움까지(그 뒤 둘째 칸 글자·이진 자료는 안 먹음)
        if d[q:q + 1] == b' ': q += 1
        elif d[q:q + 2] == b'\x81\x40' and q + 2 <= e: q += 2
        else: break
    return p - off, se, q


def pad_bytes(n):
    return b'\x81\x40' * (n // 2) + b' ' * (n & 1)


BGM_FIELD = (0x66B75, 0x67110)                                      # TITLE BGM 이름: 22 B 칸 오른쪽 맞춤(«01 XX 00 7C» 머리 뒤)


MOVE_MENU = (0x41F8, 0x42F4)                                        # SEN_DATA 묶음 2 = 이동 메뉴 지명(12 B 고정, 원문 가운데 맞춤) — 0x42F4 «移動しますか» 는 빼고


def patch_strings(d, items, enc, cstr, report, fname):
    """items: [(위치, 원문, 번역)] — 제자리(원래 바이트, 남으면 공백) · 아이템 칸은 끝 뒤 0 여백까지"""
    b = bytearray(d)
    fields = collections.defaultdict(list)
    for off, s, t in items:
        e = seg_end(d, off, cstr)
        # 칸 끝: 이 문자열을 품은 «00 1B» 뒤 0 여백(아이템 기록 꼴) — 길이 바이트 문자열·촘촘한 목록은 0 여백 없음
        q = e
        while q < len(d) - 1 and not (d[q] == 0 and d[q + 1] == 0x1B): q += 2 if d[q] >= 0x80 else 1
        z = q + 2
        while z < len(d) and d[z] == 0: z += 1
        lp = d[off - 1] == e - off + 2 if off else False
        fields[(q, z if (z - q - 2) >= 2 and not lp and not cstr else q + 2)].append((off, e, s, t))
    for (q, cap), segs in fields.items():
        segs.sort()
        start = segs[0][0]
        if cap > q + 2:                                             # 아이템 칸 — 끝 뒤 0 여백까지 다시 짬
            body = bytearray(); p = start
            for off, e, s, t in segs:
                body += d[p:off] + enc(t); p = e
            body += d[p:q + 2]
            if start + len(body) <= cap:
                b[start:cap] = bytes(body) + bytes(cap - start - len(body)); continue
            report.append((fname, '%X' % start, '아이템 칸 넘침 %d>%d B' % (len(body), cap - start), segs[0][2], segs[0][3]))
            continue
        for off, e, s, t in segs:                                   # 제자리
            sp = src_span(d, off, e, s)
            lead = trail = 0
            if sp:                                                  # 칸 = 원문 + 뒤 공백까지(2026-10-25 실기: 끝 00 없는 문자열이 뒤 칸 주소 표를 덮어 저장 화면 깨짐)
                lead, se, e2 = sp; trail = e2 - se
                if s.endswith('%') and t.endswith('%'): t = t[:-1].rstrip(' ')   # 02255: 원문 열에 뒤 표 첫 바이트(%)가 섞여 뽑힘
                e = e2
            nb = enc(t)
            room = e - off
            p0 = off                                                # 오른쪽 맞춤 목록(TITLE BGM 이름 «7C 　　…이름»): 앞 전각 공백 채움을 줄여 씀
            if fname == 'TITLE.BIN':
                while d[p0 - 2:p0] == b'\x81\x40': p0 -= 2
            if len(nb) <= room and fname == 'SEN/SEN_DATA.DAT' and MOVE_MENU[0] <= off < MOVE_MENU[1]:
                k = (room - len(nb)) // 2                            # 이동 메뉴 지명: 원문처럼 12 B 칸 가운데(반각 공백, 2026-10-25 하스피)
                b[off:e] = b' ' * k + nb + b' ' * (room - len(nb) - k)
            elif len(nb) <= room and fname == 'TITLE.BIN' and BGM_FIELD[0] <= off < BGM_FIELD[1] and room == 22:
                b[off:e] = pad_bytes(room - len(nb)) + nb           # BGM 이름: 늘 오른쪽 맞춤
            elif len(nb) <= room and lead:                          # 원문 앞 공백 있음: 양쪽 공백 = 가운데, 앞만 = 원문 가운데 자리 유지
                k = (room - len(nb)) // 2 if trail else min(room - len(nb), lead + (room - lead - len(nb)) // 2)
                b[off:e] = pad_bytes(k) + nb + b' ' * (room - len(nb) - k)
            elif len(nb) <= room and fname == 'TITLE.BIN' and re.search(rb'E\d$', nb):
                b[off:e] = nb[:-2] + b' ' * (room - len(nb)) + nb[-2:]    # 끝 끼우기 코드(E8 = 장소 이름 등) 뒤 채움 공백은 다음 줄에 붙어 상자 폭을 넘김(2026-10-25 실기 «마» 지워짐) → 코드 앞에
            elif len(nb) <= room:
                b[off:e] = nb + b' ' * (room - len(nb))
            elif len(nb) <= e - p0:
                pad = e - p0 - len(nb)
                b[p0:e] = b'\x81\x40' * (pad // 2) + b' ' * (pad & 1) + nb
            else:
                report.append((fname, '%X' % off, '제자리 넘침 %d>%d B' % (len(nb), room), s, t))
    return bytes(b)


REGIONS = [   # SEN_DATA 촘촘한 목록 구역: (시작, 다시 쓸 수 있는 끝, 표 종류, 표 위치, 표 기준, 표 개수 또는 None)
    # 메뉴 구역(0x4080~)은 길이 바이트 목록(~0x41F8) 뒤에 00 1B 목록(지명)이 이어지고 0x4800·0x4B00 은 코드가 바로 가리킴 — 읽는 방식 미확인이라 제자리만
    (0x6400, 0x8000, 'u32', 0x6000, 0x6000, None),      # 힌트: u32 표(0x6000, 기준 0x6000, FF 까지)
    (0x8800, 0xA000, 'u16', 0x8800, 0x8800, None),      # 전투 메시지: u16 그룹 표(0x8800, 개수 = 첫 값/2)
]


def repack_regions(d, items, enc, report):
    """items: [(위치, 원문, 번역)] 중 구역 안 것 → 구역을 다시 이어 붙이고 표·길이 바이트 고침. 남은 것 돌려줌."""
    b = bytearray(d); left = []
    byreg = collections.defaultdict(list)
    for it in items:
        for k, (a, cap, kind, tp, tb, tn) in enumerate(REGIONS):
            if a <= it[0] < cap: byreg[k].append(it); break
        else: left.append(it)
    for k, its in byreg.items():
        a, cap, kind, tp, tb, tn = REGIONS[k]
        # 구역 실제 끝(원래 자료 끝)
        if kind == 'len':
            q = a
            while d[q] not in (0, 0xFF): q += 1 + d[q]
            end = q
        else:
            q = cap
            while d[q - 1] == 0: q -= 1
            end = q
        chunks = []
        for off, s, t in sorted(its):
            e = seg_end(d, off, False); nb = enc(t)
            chunks.append((off, e, nb))
            if kind == 'len':
                assert d[off - 1] == e - off + 2, ('길이 바이트 아님', hex(off))
        new = bytearray(); shift = []; p = a; acc = 0
        for off, e, nb in chunks:
            new += d[p:off]; new += nb; acc += len(nb) - (e - off); shift.append((e, acc)); p = e
            if kind == 'len': new[len(new) - len(nb) - 1] = len(nb) + 2
        new += d[p:end]
        def newpos(old):
            add = 0
            for e, s_ in shift:
                if old >= e: add = s_
                else: break
            return old + add
        if a + len(new) > cap:
            report.append(('SEN/SEN_DATA.DAT', '%X' % a, '구역 넘침 %d>%d B' % (len(new), cap - a), '', '')); left += its; continue
        b[a:cap] = bytes(new) + bytes(cap - a - len(new))
        if kind == 'u32':
            i = tp
            while struct.unpack_from('>I', d, i)[0] != 0xFFFFFFFF:
                v = struct.unpack_from('>I', d, i)[0]
                if v and a <= tb + v < end: struct.pack_into('>I', b, i, newpos(tb + v) - tb)
                i += 4
        elif kind == 'u16':
            n = struct.unpack_from('>H', d, tp)[0] // 2
            for i in range(n):
                v = struct.unpack_from('>H', d, tp + 2 * i)[0]
                if a <= tb + v < end: struct.pack_into('>H', b, tp + 2 * i, newpos(tb + v) - tb)
    return bytes(b), left


# TITLE.BIN 저장 장소 이름(불러오기 화면 «セーブポイント：…»): 머리 u16 표(0x66800, 칸 2 = 0x66804)가 묶음 시작을 가리키고
# 0x06006928 이 «00 1B» 를 세어 건너뛴 뒤 줄 버퍼(0x060226B8, 160 B)로 베낌 → 묶음째 파일 안 0 여백(0x671B1‥글꼴 0x67800, 스테이트 4개 램도 0)으로 옮기고 머리만 고침
T_HDR, T_GRP, T_GRP_END, T_NEW, T_NEW_END = 0x66804, 0x6690D, 0x66B51, 0x671C0, 0x67800


def move_title_places(d, items, enc):
    b = bytearray(d); mine = sorted(it for it in items if T_GRP <= it[0] < T_GRP_END)
    new = bytearray(); p = T_GRP
    for off, s, t in mine:
        e = seg_end(d, off, True); new += d[p:off] + enc(t); p = e
    new += d[p:T_GRP_END]
    assert T_NEW + len(new) <= T_NEW_END and not any(d[T_NEW:T_NEW_END]), ('TITLE 장소 이름 자리 모자람', len(new))
    b[T_NEW:T_NEW + len(new)] = new
    assert struct.unpack_from('>H', d, T_HDR)[0] == T_GRP - 0x66800
    struct.pack_into('>H', b, T_HDR, T_NEW - 0x66800)
    return bytes(b), [it for it in items if not T_GRP <= it[0] < T_GRP_END]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    R, loc = load_text()
    gmap, T = glyph_map(R)
    enc = encoder(gmap)
    report = []; out = {}
    # 위치별 정리
    per = collections.defaultdict(list)
    for n, (s, t) in R.items():
        if not t: continue
        for L in loc[n]:
            f, off = L.rsplit(':', 1); per[f].append((int(off, 16), s, t, n))
    # MAC
    nmac = 0
    for f, lst in sorted(per.items()):
        if not re.match(r'FLD/M../MAC', f): continue
        d = read(f)
        edits = {off - M.BASE: t for off, s, t, n in lst}
        try:
            out[f] = rebuild_mac(d, edits, enc); nmac += len(edits)
        except (AssertionError, UnicodeEncodeError) as e:
            report.append((f, '', 'MAC 다시 짜기 실패: %s' % (e,), '', ''))
    # SEN_DATA · TITLE · SEN.BIN
    for f, cstr in (('SEN/SEN_DATA.DAT', False), ('TITLE.BIN', True), ('SEN.BIN', True)):
        d = out.get(f) or read(f)
        items = [(off, s, t) for off, s, t, n in per.get(f, [])]
        if f == 'SEN/SEN_DATA.DAT':
            d, items = repack_regions(d, items, enc, report)
        if f == 'TITLE.BIN':
            d, items = move_title_places(d, items, enc)
        try: d = patch_strings(d, items, enc, cstr, report, f)
        except UnicodeEncodeError as e: report.append((f, '', '글자 변환 실패 %s' % e, '', ''))
        if f == 'SEN.BIN':                                                # 기본 이름 표(3명 × 6 B, 끝 00 없음 — 추출 안 됨) → 새 게임 때 RAM 0x06063CE4 등으로 복사, 전투 메시지 «まりかは…»(2026-10-25 하스피)
            src, new = 'まりかあきらかなめ'.encode('cp932'), enc('마리카아키라카나메')
            assert d[NAME_TAB:NAME_TAB + len(src)] == src and len(new) == len(src)
            d = d[:NAME_TAB] + new + d[NAME_TAB + len(src):]
        out[f] = d
    # 글꼴(SEN_DATA·TITLE 사본) + 타이틀 로고
    sd = bytearray(out['SEN/SEN_DATA.DAT']); sd[FONT_DATA:FONT_DATA + 0x1000 + NTAB * 28] = draw_glyphs(bytes(sd[FONT_DATA:FONT_DATA + 0x1000 + NTAB * 28]), 0, gmap)
    out['SEN/SEN_DATA.DAT'] = bytes(sd)
    tt = bytearray(out['TITLE.BIN']); orig = read('TITLE.BIN')
    for nm in ('TITLE.BIN', 'TITLE_wk1.BIN'):                          # tools/title_logo.py build(로고) · tools/backup_msg.py build(백업 램 안내 그림) 결과 — 바뀐 바이트만
        logo = os.path.join(ROOT, 'work', 'build', nm)
        if os.path.exists(logo):
            lb = open(logo, 'rb').read()
            for i in range(len(tt)):
                if lb[i] != orig[i]: tt[i] = lb[i]
    tt[FONT_TITLE:FONT_TITLE + 0x1000 + NTAB * 28] = draw_glyphs(bytes(tt[FONT_TITLE:FONT_TITLE + 0x1000 + NTAB * 28]), 0, gmap)
    out['TITLE.BIN'] = bytes(tt)
    # 쓰기(바뀐 파일만)
    nchg = 0
    for f, b in out.items():
        if b == read(f): continue
        p = os.path.join(OUT, *f.split('/')); os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'wb').write(b); nchg += 1
    with open(os.path.join(ROOT, 'work', 'build', 'text_report.tsv'), 'w', encoding='utf-8-sig', newline='\n') as w:
        w.write('파일\t위치\t내용\t원문\t번역\n' + ''.join('\t'.join(r) + '\n' for r in report))
    c = collections.Counter(re.sub(r'[\d>]+ B|\d+', 'N', r[2]) for r in report)
    print('한글 %d자 → 글꼴 칸 · MAC 대사/선택지 %d곳 · 바뀐 파일 %d · 못 넣은 것 %d %s → work/build/files/'
          % (len(gmap), nmac, nchg, len(report), dict(c)))
    for r in report[:15]: print('  ', r[0], r[1], r[2], '|', r[3][:20], '|', r[4][:24])


if __name__ == '__main__':
    main()
