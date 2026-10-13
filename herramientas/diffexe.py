"""Diff de dos exes PE del mismo tamano: lista bloques cambiados con VA, seccion y valores."""
import sys, struct, pefile

a, b = sys.argv[1], sys.argv[2]
A, B = open(a, 'rb').read(), open(b, 'rb').read()
pe = pefile.PE(a, fast_load=True)
base = pe.OPTIONAL_HEADER.ImageBase


def va_de(off):
    for s in pe.sections:
        if s.PointerToRawData <= off < s.PointerToRawData + s.SizeOfRawData:
            return base + s.VirtualAddress + off - s.PointerToRawData, s.Name.rstrip(b'\0').decode(errors='ignore')
    return None, 'header'


runs, i, n = [], 0, min(len(A), len(B))
while i < n:
    if A[i] != B[i]:
        j = i
        while j < n and (A[j] != B[j] or (j + 1 < n and A[j + 1] != B[j + 1]) or (j + 2 < n and A[j + 2] != B[j + 2])):
            j += 1
        runs.append((i, j))
        i = j
    else:
        i += 1
print(f"{len(runs)} bloques distintos")
for i, j in runs:
    va, sec = va_de(i)
    s0, s1 = i - i % 4, j + (-j) % 4
    vals = []
    for k in range(s0, s1, 4):
        fa, fb = struct.unpack('<f', A[k:k+4])[0], struct.unpack('<f', B[k:k+4])[0]
        ia, ib = struct.unpack('<i', A[k:k+4])[0], struct.unpack('<i', B[k:k+4])[0]
        if A[k:k+4] != B[k:k+4]:
            vals.append(f"  +{k-s0}: f {fa:g} -> {fb:g} | i {ia} -> {ib}")
    vas = f"{va:#010x}" if va else '-'
    print(f"off {i:#x} VA {vas} [{sec}] len {j-i}: {A[i:j].hex(' ')[:90]} -> {B[i:j].hex(' ')[:90]}")
    for v in vals[:8]:
        print(v)
