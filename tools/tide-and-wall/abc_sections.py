"""從 YuE2 回傳 JSON 的 abc 推算各段落起始秒數（依 Vocal 聲部小節長度與 Q、M 變化）。"""
import json, re, sys
from fractions import Fraction


def sections(abc):
    L = Fraction(1, 32); Q = 120; M = Fraction(4, 4)
    for m in re.finditer(r'^L:\s*(\d+)/(\d+)', abc, re.M): L = Fraction(int(m[1]), int(m[2])); break
    q = re.search(r'^Q:\s*1/4=(\d+)', abc, re.M); Q = int(q[1]) if q else Q
    t = 0.0; cur = 'start'; out = []; voice = None
    for line in abc.splitlines():
        line = line.strip()
        if line.startswith('%'):
            cur = line[1:].strip(); out.append((cur, t)); continue
        if line.startswith('V:'):
            voice = line[2:].strip().split()[0]; continue
        mm = re.match(r'M:\s*(\d+)/(\d+)', line)
        if mm: M = Fraction(int(mm[1]), int(mm[2])); continue
        if voice != 'Vocal' or not line or re.match(r'^[A-Z]:', line): continue
        bars = [b for b in line.split('|') if b.strip()]
        for b in bars:
            b = re.sub(r'"[^"]*"', '', b)
            z = re.fullmatch(r'\s*Z(\d*)\s*', b)
            n = int(z[1] or 1) if z else 1
            t += float(n * M / Fraction(1, 4) * Fraction(60, Q))
    return out, t


if __name__ == '__main__':
    for f in sys.argv[1:]:
        abc = json.load(open(f, encoding='utf-8'))['abc']
        s, tot = sections(abc)
        print(f.split('/')[-1], f'{tot:.0f}s', ' '.join(f'{n}@{int(x//60)}:{int(x%60):02d}' for n, x in s))
