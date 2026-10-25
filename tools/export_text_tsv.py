# -*- coding: utf-8 -*-
r"""일반 텍스트(대사 창·메뉴·아이템·상점 등) 번역 TSV 뽑기 (2026-10-25)
  · 맵 스크립트 FLD/Mxx/MAC*.DAT: 명령 «0x0001 + 길이(2 B BE) + SJIS 본문» — 이어진 줄은 한 메시지로 묶어 {n} 으로 이음.
  · 그 밖(SEN/·실행 파일 TITLE·SEN·LAST·OPEN.BIN 등, DEBUG.BIN 제외): 0x00·제어 바이트로 끊긴 SJIS 문자열
    (2글자 이상이거나 가나가 섞인 것 — 데이터를 글자로 잘못 읽는 것 줄이기). SEN_DATA 는 길이 바이트 + 본문 + 0x00 + 0x1A/0x1B 꼴(⏳넣기 때 확정).
  · 같은 원문은 한 줄(쓰인 곳 수·첫 위치), 모든 위치는 _텍스트위치.tsv.
  열: 번호 · 원문 · 번역 · 위치(파일:16진) · 쓰인 곳 · 종류(대사/문자열)
  python tools/export_text_tsv.py → data/번역할것/텍스트_NN.tsv (20 KB 단위)"""
import collections, os, re, struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISC = os.path.join(ROOT, 'work', 'disc')
OUT = os.path.join(ROOT, 'data', '번역할것')
SPLIT = 20 * 1024
KANA = re.compile('[ぁ-んァ-ヶ]')
SKIP = {'DEBUG.BIN'}
TEXT_FILES = {'SEN/SEN_DATA.DAT', 'TITLE.BIN', 'SEN.BIN'}   # 맵 스크립트 밖에서 진짜 글이 있는 파일(전 파일 훑기 2026-10-25 — B*.DAT·OPEN·LAST·MAP·FACE 는 그림 바이트 우연 일치)
EXE = {'SEN.BIN'}                       # C 문자열(앞뒤 0x00)
DATA_LIKE = {'TITLE.BIN'}               # SEN_DATA 와 같은 꼴(앞 0x00·0x01·0x1A·0x1B, 뒤 00 1A/1B)
COMMON2 = re.compile('^[ぁ-んァ-ヶー一-龥０-９Ａ-Ｚａ-ｚ　、。！？「」『』（）・…～／：％＋－×Ｘ!-~ ]+$')   # TITLE.BIN — 서식 코드(：E8 등) 반각 허용
COMMON = re.compile('^[ぁ-んァ-ヶー一-龥０-９Ａ-Ｚａ-ｚ　、。！？「」『』（）・…～／：％＋－×Ｘ ]+$')


def sjis_ok(b):
    try:
        t = b.decode('cp932')
    except UnicodeDecodeError:
        return None
    if any(ord(c) < 0x20 for c in t): return None
    return t


def mac_messages(d):
    """→ [(위치, '줄{n}줄…')]"""
    out = []; p = 0; n = len(d)
    while p < n - 4:
        if d[p] == 0 and d[p + 1] == 1:
            ln = struct.unpack_from('>H', d, p + 2)[0]
            t = sjis_ok(d[p + 4:p + 4 + ln]) if 0 < ln <= 200 and ln % 2 == 0 else None
            if t and (KANA.search(t) or len(t.strip('　')) >= 2):
                start = p; lines = []
                while d[p] == 0 and d[p + 1] == 1:
                    ln = struct.unpack_from('>H', d, p + 2)[0]
                    t = sjis_ok(d[p + 4:p + 4 + ln]) if 0 < ln <= 200 else None
                    if t is None: break
                    lines.append(t); p += 4 + ln
                out.append((start, '{n}'.join(lines))); continue
        p += 2
    return out


SJ = re.compile(rb'(?:[\x81-\x9f\xe0-\xef][\x40-\x7e\x80-\xfc]|[\x20-\x7e])+')


def plain_strings(d):
    out = []
    for m in SJ.finditer(d):
        b = m.group()
        if not re.search(rb'[\x81-\x9f\xe0-\xef]', b): continue
        if m.start() and d[m.start() - 1] >= 0x80 and d[m.start() - 1] not in (0xFF,): pass
        t = sjis_ok(b)
        if not t: continue
        core = t.strip(' 　')
        jp = sum(1 for c in core if ord(c) > 0x7F)
        if not core or jp == 0: continue
        if not (KANA.search(core) or jp >= 2): continue
        out.append((m.start(), core))
    return out


def main():
    by = collections.OrderedDict(); kind = {}
    files = []
    for dp, _, fs in os.walk(DISC):
        for f in sorted(fs):
            if f.endswith('.AIF') or f.startswith('_') or f in SKIP: continue
            files.append(os.path.join(dp, f))
    files.sort(key=lambda p: (0 if '/FLD/' in p.replace(os.sep, '/') else 1, p))
    for p in files:
        rel = os.path.relpath(p, DISC).replace(os.sep, '/'); d = open(p, 'rb').read()
        if re.match(r'FLD/M../MAC.*\.DAT', rel):
            for off, s in mac_messages(d):
                by.setdefault(s, []).append('%s:%X' % (rel, off)); kind.setdefault(s, '대사')
        elif rel in TEXT_FILES:
            for off, s in plain_strings(d):
                if rel in EXE:          # 실행 파일: 코드 바이트 오인 줄이기 — 흔한 글자만 + (가나 섞임 또는 0x00 뒤 시작)
                    end = off + len(s.encode('cp932'))
                    if not COMMON.match(s) or len(s) < 2: continue
                    if not ((off == 0 or d[off - 1] == 0) and end < len(d) and d[end] == 0): continue   # 앞뒤 0x00 인 C 문자열만
                if rel in DATA_LIKE:
                    end = off + len(s.encode('cp932'))
                    if not COMMON2.match(s) or len(s) < 2 or not (off == 0 or d[off - 1] in (0, 1, 0x1A, 0x1B)): continue
                    if not (end + 1 < len(d) and d[end] == 0 and d[end + 1] in (0x1A, 0x1B)): continue   # 뒤 00 1A/1B
                    raw = d[off:end].decode('cp932')
                    if len(raw) > 1 and ord(raw[0]) < 0x80 and ord(raw[1]) > 0x7F:   # 레코드 앞 1 바이트(곡 번호 등) 떼기
                        off += 1; s = raw[1:].strip(' 　')
                by.setdefault(s, []).append('%s:%X' % (rel, off)); kind.setdefault(s, '문자열')
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.startswith('텍스트_') or f == '_텍스트위치.tsv': os.remove(os.path.join(OUT, f))
    head = '번호\t원문\t번역\t위치\t쓰인 곳\t종류\n'
    lines = ['%05d\t%s\t\t%s\t%d\t%s\n' % (n, s, locs[0], len(locs), kind[s]) for n, (s, locs) in enumerate(by.items(), 1)]
    out, cur, size = [], [], 0
    for ln in lines:
        nb = len(ln.encode('utf-8'))
        if cur and size + nb > SPLIT: out.append(cur); cur, size = [], 0
        cur.append(ln); size += nb
    if cur:
        if out and size < SPLIT // 4: out[-1] += cur
        else: out.append(cur)
    for k, ls in enumerate(out, 1):
        with open(os.path.join(OUT, '텍스트_%02d.tsv' % k), 'w', encoding='utf-8-sig', newline='\n') as w:
            w.write(head + ''.join(ls))
    with open(os.path.join(OUT, '_텍스트위치.tsv'), 'w', encoding='utf-8-sig', newline='\n') as w:
        w.write('번호\t위치\n' + ''.join('%05d\t%s\n' % (n, ' '.join(l)) for n, (s, l) in enumerate(by.items(), 1)))
    c = collections.Counter(kind[s] for s in by)
    nch = sum(len(s.replace('{n}', '')) for s in by)
    print('고유 %d줄(%s) · 글자 %d · 파일 %d → %s' % (len(by), dict(c), nch, len(out), OUT))


if __name__ == '__main__':
    main()
