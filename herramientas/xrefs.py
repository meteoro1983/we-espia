"""Busca en el codigo de un exe x86 todas las instrucciones que referencian ciertas VAs.
uso: python xrefs.py <exe> <va_hex> [<va_hex> ...]   (rango: va o va+N con --rango N)"""
import sys, struct, pefile, capstone

exe = sys.argv[1]
args = [a for a in sys.argv[2:] if not a.startswith('--')]
rango = 4
for a in sys.argv[2:]:
    if a.startswith('--rango='):
        rango = int(a.split('=')[1])
objetivos = [int(a, 16) for a in args]

pe = pefile.PE(exe, fast_load=True)
base = pe.OPTIONAL_HEADER.ImageBase
print(f"ImageBase {base:#x}")
for s in pe.sections:
    print(f"  {s.Name.rstrip(b'0').decode(errors='ignore'):10} VA {base+s.VirtualAddress:#010x} vsize {s.Misc_VirtualSize:#x} raw {s.SizeOfRawData:#x} flags {s.Characteristics:#x}")

# Busqueda bruta de los 4 bytes de cada direccion en secciones ejecutables (rapido), luego desensamblar alrededor
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
for s in pe.sections:
    if not (s.Characteristics & 0x20000000):
        continue
    data = s.get_data()
    sva = base + s.VirtualAddress
    for t in objetivos:
        for off in range(rango):
            pat = struct.pack('<I', t + off)
            i = data.find(pat)
            while i != -1:
                # probar arranques de instruccion hasta 8 bytes antes
                hit = None
                for back in range(8, 0, -1):
                    st = i - back
                    if st < 0:
                        continue
                    ins = next(md.disasm(data[st:st+16], sva + st), None)
                    if ins and st + ins.size >= i + 4 and f"[{t+off:#x}]" in ins.op_str:
                        hit = ins
                if hit is None:
                    for back in range(1, 9):
                        st = i - back
                        ins = next(md.disasm(data[max(st,0):st+16], sva + st), None) if st >= 0 else None
                        if ins and st + ins.size >= i + 4:
                            hit = ins; break
                if hit:
                    print(f"{t:#x}+{off}: {hit.address:#010x}  {hit.mnemonic} {hit.op_str}")
                i = data.find(pat, i + 1)
