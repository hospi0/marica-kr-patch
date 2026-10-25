# -*- coding: utf-8 -*-
r"""받은 번역 정리·검사 (2026-10-25) — data/번역/(사용자 번역 사본, my files 는 안 건드림) → work/tr/
  ① 용어(data/용어.tsv: 원어 «*»=모든 줄 | «A|B»= 원문에 그중 하나 있는 줄만, 틀린꼴→바른꼴, 뒤 조사 받침 맞춤)
  ② 고침(data/고침.tsv: 종류(음성/텍스트)·번호·번역 통째 — 받아쓰기 재작업 반영 등)
  ③ 검사 — 막음: 텍스트 토큰({n}·#1/#0·「」『』) 개수 다름 · 가나/한자 남음 · 실개행/탭
            경고: 음성 자막 한 쪽이 화면 폭(나눔고딕 굵게 15px, 308px) 넘음 → 자동 쪽 나눔 대상(낱말 하나가 넘으면 막음)
                  텍스트 줄이 원문 같은 줄보다 김(창 폭 미조사 — 실기 확인)
  → work/tr/voice.tsv(번호·음성·시작·끝·자막) · work/tr/text.tsv(번호·원문·번역) · work/tr/report.tsv
  python tools/tr_check.py"""
import collections, glob, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOK = re.compile(r'\{[^{}]*\}|#[01]')
JP = re.compile('[ぁ-んァ-ヶ一-龥々〆]')
JOSA = [('라는', '이라는'), ('라고', '이라고'), ('였던', '이었던'), ('였다', '이었다'), ('였', '이었'), ('라면', '이라면'), ('랑', '이랑'),
        ('는', '은'), ('가', '이'), ('를', '을'), ('와', '과'), ('로', '으로'), ('야', '아'), ('여', '이여'), ('라', '이라'), ('다', '이다')]
FONT = r'C:\claude\utils\font\nanum-gothic\NanumGothicBold.ttf'
MAXW = 308


def has_batchim(w):
    c = w[-1]
    return '가' <= c <= '힣' and (ord(c) - 0xAC00) % 28 != 0


def replace_josa(t, a, b):
    """a → b, 받침이 달라지면 바로 뒤 조사도 맞춤(건블레이즈 load_tr.replace_josa 와 같음)"""
    if has_batchim(a) == has_batchim(b): return t.replace(a, b)
    out = []; p = 0
    for m in re.finditer(re.escape(a), t):
        out.append(t[p:m.start()]); out.append(b); p = m.end()
        for x, y in JOSA:
            nb, wb = (x, y) if not has_batchim(a) else (y, x)
            if t.startswith(nb, p): out.append(wb); p += len(nb); break
    out.append(t[p:])
    return ''.join(out)


MAC_W, MAC_L, DESC_W = 20, 3, 17                # 대사 창 20칸(2026-10-25 스샷 실측: 칸 74px·공백 반 칸, «모른다» 다 잘림 — 예전 21 은 틀림)
SP = '　'


def cw(s):
    """화면 칸 수: 전각 1 · 반각(ASCII·반각 가나) 0.5 · 색 코드 #0/#1 0"""
    s = re.sub(r'#[01]', '', s)
    return sum(0.5 if ord(c) < 0x80 or 0xFF61 <= ord(c) <= 0xFF9F else 1 for c in s)


def realign(src, tr):
    """줄 끝 «#1X…» 표시를 원문과 같은 칸에 — 표시 앞 공백을 다시 셈(전각 공백 + 반 칸이면 반각 공백 하나)"""
    i = tr.rindex('#1'); body = tr[:i].rstrip(' ' + SP); suf = tr[i:]
    pad = cw(src) - cw(body) - cw(suf)
    if not body: return (tr, None) if cw(tr) <= cw(src) else (tr, '줄 끝 표시가 원문보다 김')
    if pad < 0.5: return tr, '줄 끝 표시 칸에 안 들어감(본문 %.1f칸) — 같은 뜻 짧은 말로' % cw(body)
    return body + SP * int(pad) + (' ' if pad % 1 else '') + suf, None


def rewrap(src, tr, W):
    """필드 대사: W 칸 넘는 줄만 띄어쓰기에서 다시 나눔. 이름「 꼴이면 이어지는 줄은 원문처럼 «이름「» 폭만큼 들여씀"""
    lines = tr.split('{n}')
    if max(cw(x) for x in lines) <= W and len(lines) <= MAC_L: return tr, None
    m = re.match(r'^([^「『]{1,8}[「『])', tr)
    ind = SP * int(cw(m.group(1))) if m else ''
    words = ' '.join(x.strip(' ' + SP) for x in lines).split(' ')
    out = []; cur = ''
    for w in words:
        if not w: continue
        cand = (cur + ' ' + w) if cur.strip(SP) else (cur + w)
        if cur and cw(cand) > W: out.append(cur); cur = ind + w
        else: cur = cand
    out.append(cur)
    if any(cw(x) > W for x in out): return '{n}'.join(out), '낱말 하나가 대사 창 %d칸보다 김' % W
    if len(out) > MAC_L: return '{n}'.join(out), '대사 창 %d줄 넘음(%d줄) — 같은 뜻 짧은 말로' % (MAC_L, len(out))
    return '{n}'.join(out), None


def load(kind):
    rows = collections.OrderedDict()
    for f in sorted(glob.glob(os.path.join(ROOT, 'data', '번역', kind + '_*.tsv'))):
        L = open(f, encoding='utf-8-sig').read().split('\n'); h = L[0].split('\t')
        for k, ln in enumerate(L[1:], 2):
            if not ln: continue
            c = ln.split('\t')
            d = dict(zip(h, c)); d['_where'] = '%s:%d' % (os.path.basename(f), k)
            rows[c[0]] = d
    return rows


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    from PIL import ImageFont
    font = ImageFont.truetype(FONT, 15)
    rules = []
    for ln in open(os.path.join(ROOT, 'data', '용어.tsv'), encoding='utf-8-sig').read().split('\n')[1:]:
        c = ln.split('\t')
        if len(c) >= 3 and c[1]: rules.append((c[0], c[1], c[2]))
    fixes = {}
    fp = os.path.join(ROOT, 'data', '고침.tsv')
    if os.path.exists(fp):
        for ln in open(fp, encoding='utf-8-sig').read().split('\n')[1:]:
            c = ln.split('\t')
            if len(c) >= 3 and c[0]: fixes[(c[0], c[1])] = c[2]
    V, T = load('음성자막'), load('텍스트')
    probs, warns = [], []; nterm = 0
    def terms(src, t):
        for k, a, b in rules:
            if k == '*' or any(x in src for x in k.split('|')): t = replace_josa(t, a, b)
        return t
    out_v = []
    for n, d in V.items():
        src, t = d['받아쓰기'], d['번역']
        t2 = terms(src, t)
        t2 = re.sub(r'\(([一-龥々]+)\)', '', t2)                           # 한자 병기 «비(非)» → 자막엔 한자 안 남김
        t2 = re.sub(r'(.)\1{15,}', lambda m: m.group(1) * 15, t2)        # 같은 글자 16번 넘게(비명) → 15번(한 쪽에 들어가게)
        t2 = re.sub(r'ー{2,}', '~', t2)                                    # 가나 장음 «ーーー» 남은 것 → ~
        t2 = fixes.get(('음성', n), t2)
        if t2 != t: nterm += 1
        if '\n' in t2 or '\t' in t2: probs.append((d['_where'], n, '실개행·탭', src, t2))
        if JP.search(t2): probs.append((d['_where'], n, '가나·한자 남음', src, t2))
        for page in [p.strip() for p in t2.split('|')]:
            w = font.getlength(page)
            if w > MAXW:
                big = max(page.split(' '), key=font.getlength)
                if font.getlength(big) > MAXW: probs.append((d['_where'], n, '낱말 하나가 자막 폭보다 김', src, t2))
                else: warns.append((d['_where'], n, '자막 폭 넘음 %dpx → 자동 쪽 나눔' % w, src, t2))
        out_v.append((n, d['음성'], d['시작'], d['끝'], t2))
    out_t = []
    for n, d in T.items():
        src, t = d['원문'], d['번역']
        if not t.strip(): out_t.append((n, src, '')); continue          # 빈 번역 = 데이터 오인(글자 아님) 줄 — 원문 그대로 둠
        t2 = terms(src, t)
        if '#1' in t2:                                                     # 장비 가능 인물 머리글자·대상 표시(#1ま　あ　か　５８ / #1全·#1単) → 한글 한 글자
            i = t2.rindex('#1'); t2 = t2[:i] + t2[i:].translate(str.maketrans({'ま': '마', 'あ': '아', 'か': '카', '全': '전', '単': '단'}))
        t2 = fixes.get(('텍스트', n), t2)
        t2 = t2.replace('~', '〜')                                         # 반각 ~(0x7E)는 대사 엔진 특수 코드 — 거기서 찍기가 멈춰 앞 대사 잔상(2026-10-25 실기 «심심해~») → 전각 〜(0x8160, 원본 글꼴)
        if t2 != t: nterm += 1
        cs = collections.Counter(TOK.findall(src)); ct = collections.Counter(TOK.findall(t2))
        for k in set(cs) | set(ct):
            if cs[k] != ct[k]: probs.append((d['_where'], n, '토큰 %s 원문 %d ≠ 번역 %d' % (k, cs[k], ct[k]), src, t2))
        for ch in '「」『』':
            if t2.count(ch) < src.count(ch): probs.append((d['_where'], n, '괄호 %s 부족' % ch, src, t2))
        if JP.search(TOK.sub('', t2)): probs.append((d['_where'], n, '가나·한자 남음', src, t2))
        if '\n' in t2 or '\t' in t2: probs.append((d['_where'], n, '실개행·탭', src, t2))
        # 창 폭(2026-10-25 스샷 my files/할일 실측): 필드 대사 창 20칸×3줄(이름「 뒤 들여쓰기) · 아이템 설명 17칸(줄 끝 #1X 는 원문 폭에 맞춘 칸)
        where = d.get('위치', '')
        if 'MAC' in where:
            t2, bad = rewrap(src, t2, MAC_W)
            if bad: probs.append((d['_where'], n, bad, src, t2))
        elif 'SEN_DATA' in where:
            if '#1' in src and '#0' not in src[src.rindex('#1'):] and '#1' in t2:
                t2, bad = realign(src, t2)
                if bad: probs.append((d['_where'], n, bad, src, t2))
            elif max(cw(x) for x in t2.split('{n}')) > max(DESC_W, max(cw(x) for x in src.split('{n}'))):
                probs.append((d['_where'], n, '설명 창 %d칸 넘음 %.1f칸 — 같은 뜻 짧은 말로' % (DESC_W, max(cw(x) for x in t2.split('{n}'))), src, t2))
        out_t.append((n, src, t2))
    os.makedirs(os.path.join(ROOT, 'work', 'tr'), exist_ok=True)
    with open(os.path.join(ROOT, 'work', 'tr', 'voice.tsv'), 'w', encoding='utf-8-sig', newline='\n') as w:
        w.write('번호\t음성\t시작\t끝\t자막\n' + ''.join('\t'.join(r) + '\n' for r in out_v))
    with open(os.path.join(ROOT, 'work', 'tr', 'text.tsv'), 'w', encoding='utf-8-sig', newline='\n') as w:
        w.write('번호\t원문\t번역\n' + ''.join('\t'.join(r) + '\n' for r in out_t))
    with open(os.path.join(ROOT, 'work', 'tr', 'report.tsv'), 'w', encoding='utf-8-sig', newline='\n') as w:
        w.write('구분\t위치\t번호\t내용\t원문\t번역\n')
        for kind, L in (('막음', probs), ('경고', warns)):
            for r in L: w.write('%s\t%s\n' % (kind, '\t'.join(r)))
    cwarn = collections.Counter(re.sub(r'\d+', 'N', x[2]) for x in warns)
    print('음성 %d · 텍스트 %d(빈 번역 %d) · 용어/고침 바뀐 줄 %d · 막음 %d · 경고 %s'
          % (len(V), len(T), sum(1 for r in out_t if not r[2]), nterm, len(probs), dict(cwarn)))
    for r in probs[:25]: print('  ✗', r[0], r[1], r[2], '|', r[3][:30], '|', r[4][:40])
    return not probs


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
