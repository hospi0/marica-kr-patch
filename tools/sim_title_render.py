import sys; sys.path.insert(0,'tools'); import sh2sim as S
h=open('work/mem/garble_title/WorkRAMH.bin','rb').read(); l=open('work/mem/garble_title/WorkRAML.bin','rb').read()
def run(buf_patch=None):
    m=S.Mem(); hh=m.add(0x06000000,0x100000,h); m.add(0x00200000,0x100000,l); vv=m.add(0x05C00000,0x80000)
    m.add(0x05F00000,0x1000); m.add(0x05FE0000,0x1000); m.add(0x05D00000,0x100); m.add(0x25FE0000&0x0FFFFFFF,0x1000)
    if buf_patch:
        a,b=buf_patch; hh[a-0x06000000:a-0x06000000+len(b)]=b
    r,n=S.run(m,0x060067FC,regs=[2,0,0,0,36,2,0x060226B8,0x25C72280])
    return hh,vv
def show(hh,y0=16,y1=31,x1=64):
    st=hh[0x225ae]<<8|hh[0x225af]; a=0x1f5ac
    for y in range(y0,y1):
        row=hh[a+y*st:a+y*st+st]; print('%2d'%y,''.join('%x'%((row[x//2]>>4) if x%2==0 else row[x//2]&15) for x in range(x1)).replace('0','.'))
hh,vv=run(); print('as-is'); show(hh)
hh,vv=run((0x060226D1,bytes([0x82,0xdc]))); print('ma->ま'); show(hh)
import struct
def test(name, line):
    hh,vv=run((0x060226B8,line)); st=hh[0x225ae]<<8|hh[0x225af]; a=0x1f5ac
    row=hh[a+20*st:a+20*st+12]; print(name, row.hex())
base=bytes(h[0x226b8:0x226b8+0x50])
L1,rest=base.split(b'\x00\x1a',1); L2=rest.split(b'\x00\x1b')[0]
print(len(L1),len(L2))
test('as-is', L1+b'\x00\x1a'+L2+b'\x00\x1b')
test('L2 trimmed', L1+b'\x00\x1a'+L2[:11]+b'\x00\x1b')
test('L2 32B', L1+b'\x00\x1a'+L2[:32]+b'\x00\x1b')
test('L2 33B', L1+b'\x00\x1a'+L2[:33]+b'\x00\x1b')
test('L2 34B', L1+b'\x00\x1a'+L2[:34]+b'\x00\x1b')
test('L1 short', L1[:4]+b'\x00\x1a'+L2+b'\x00\x1b')
L1b=L1+b'\x20'*5
test('fix: pad before E8 (L1+5, L2 35)', L1b+b'\x00\x1a'+L2[:35]+b'\x00\x1b')
