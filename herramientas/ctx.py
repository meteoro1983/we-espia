"""Desensambla alrededor de una VA (o la funcion entera que la contiene).
uso: python ctx.py <exe> <va_hex> [antes=0x80] [despues=0x80]"""
import sys, struct, pefile, capstone

exe, va = sys.argv[1], int(sys.argv[2], 16)
antes = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x80
despues = int(sys.argv[4], 16) if len(sys.argv) > 4 else 0x80
pe = pefile.PE(exe, fast_load=True)
base = pe.OPTIONAL_HEADER.ImageBase
img = pe.get_memory_mapped_image()
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)

# inicio de funcion: retroceder hasta relleno CC/90 de alineacion
st = va - base
lim = st - antes
k = st
while k > lim:
    if img[k-1] in (0xCC, 0x90, 0xC3) and img[k] in (0x55, 0x83, 0x81, 0x56, 0x53, 0x57, 0x51, 0x6A, 0xD9, 0x8B, 0xA1) and k % 16 == 0:
        break
    k -= 1
inicio = k if k > lim else lim
print(f"; desde {base+inicio:#x}")


def flt(op):
    # anota constantes float de memoria directa
    import re
    m = re.search(r'dword ptr \[(0x[0-9a-f]+)\]', op)
    if m:
        a = int(m.group(1), 16) - base
        if 0 < a < len(img) - 4:
            return f"   ; [{m.group(1)}] = {struct.unpack('<f', img[a:a+4])[0]:g}"
    m = re.search(r'qword ptr \[(0x[0-9a-f]+)\]', op)
    if m:
        a = int(m.group(1), 16) - base
        if 0 < a < len(img) - 8:
            return f"   ; [{m.group(1)}] = {struct.unpack('<d', img[a:a+8])[0]:g} (dbl)"
    return ''


for ins in md.disasm(bytes(img[inicio:st + despues]), base + inicio):
    mark = '>>' if ins.address <= va < ins.address + ins.size else '  '
    print(f"{mark} {ins.address:#010x}  {ins.mnemonic:7} {ins.op_str}{flt(ins.op_str)}")
