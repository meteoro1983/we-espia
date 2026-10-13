"""
parchear_arbitro.py - WE9LE: arbitro mas permisivo.

Todas las faltas del juego (barrida, carga, empujon, agarron... 13 situaciones) pasan por
UNA funcion "registrar falta" (0x5FC1F0 en WE9LEK). Este parche la desvia a un code cave
que tira un numero al azar 0..99 con el RNG del propio juego (0x647B30) y, si sale menor
que PORCENTAJE, la falta NO se registra (el arbitro deja seguir). Si no, sigue normal.

uso: python parchear_arbitro.py <exe_origen> <exe_destino> <porcentaje 0-100> [we9le|we9]
"""
import sys, struct, pefile

ORIG = bytes.fromhex("8b4c240c8b442408")   # mov ecx,[esp+0xc]; mov eax,[esp+8]
# Direcciones por juego (WE9LE = WE9LEK.exe crack/K55; WE9 = we9.exe nocd, misma logica)
JUEGOS = {
    #        registrar falta  rand(n)   code cave (zona libre)
    "we9le": (0x5FC1F0,       0x647B30, 0x4760000),   # cave en .securom (ceros)
    "we9":   (0x5D4A10,       0x620400, 0xACD400),    # cola de .text (Kitserver usa 0xACDFE0, lejos)
}

src, dst, pct = sys.argv[1], sys.argv[2], int(sys.argv[3])
juego = sys.argv[4] if len(sys.argv) > 4 else "we9le"
FUNC, RAND, CAVE = JUEGOS[juego]
assert 0 <= pct <= 100
d = bytearray(open(src, "rb").read())
pe = pefile.PE(data=bytes(d), fast_load=True)
base = pe.OPTIONAL_HEADER.ImageBase
off = lambda va: pe.get_offset_from_rva(va - base)

if d[off(FUNC):off(FUNC) + len(ORIG)] != ORIG:
    sys.exit(f"El exe no tiene los bytes esperados en {FUNC:#x} (¿ya parcheado u otra version?): "
             f"{d[off(FUNC):off(FUNC)+len(ORIG)].hex()}")
if any(d[off(CAVE):off(CAVE) + 0x40]):
    sys.exit("La zona del code cave no esta vacia en este exe.")

code_va = CAVE + 0x10
c = bytearray()
c += b"\x6a\x64"                                        # push 100
c += b"\xe8" + struct.pack("<i", RAND - (code_va + len(c) + 5))   # call rand
c += b"\x83\xc4\x04"                                    # add esp,4
c += b"\x0f\xb6\x0d" + struct.pack("<I", CAVE)          # movzx ecx, byte [CAVE]
c += b"\x39\xc8"                                        # cmp eax, ecx
c += bytes([0x72, len(ORIG) + 5])                       # jb salteo (saltea originales + jmp)
c += ORIG                                               # instrucciones originales
c += b"\xe9" + struct.pack("<i", (FUNC + len(ORIG)) - (code_va + len(c) + 5))  # jmp de vuelta
c += b"\x31\xc0\xc3"                                    # salteo: xor eax,eax; ret (= "no se registro")
d[off(CAVE)] = pct
d[off(code_va):off(code_va) + len(c)] = c
d[off(FUNC):off(FUNC) + len(ORIG)] = (b"\xe9" + struct.pack("<i", code_va - (FUNC + 5))
                                      + b"\x90" * (len(ORIG) - 5))
open(dst, "wb").write(d)
print(f"OK ({juego}): {dst} -> el arbitro deja pasar ~{pct}% de las faltas (byte de ajuste en VA {CAVE:#x}, offset {off(CAVE):#x})")
