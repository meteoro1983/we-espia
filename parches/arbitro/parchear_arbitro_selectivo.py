"""
parchear_arbitro_selectivo.py - WE9 / WE9LE: menos faltas "simples", se mantienen las importantes.

Dentro de "registrar falta" el juego calcula la GRAVEDAD (1 = falta simple sin tarjeta,
2-4 = amarilla / roja). Justo ahi se engancha este parche:
  - gravedad >= 2 (tarjeta)                      -> se cobra siempre
  - pelota en el area o cerca (zona ampliada)    -> se cobra siempre (penales, tiros libres peligrosos)
  - falta simple lejos del area                  -> el arbitro la deja pasar el PORCENTAJE de las veces
Para "dejarla pasar" se borra la falta pendiente (contador de ventaja = 0x7FFF, "nada pendiente").

uso: python parchear_arbitro_selectivo.py <exe_origen> <exe_destino> <porcentaje> [we9le|we9]
     [--largo M] [--ancho M]   zona "cerca del area": |x| > largo y |y| < ancho, en metros desde el centro
                               (por defecto 31 m y 25 m; el area real es 36,1 m y 20,2 m)
"""
import sys, struct, argparse, pefile

JUEGOS = {
    #        registrar falta  rand(n)   code cave
    "we9le": (0x5FC1F0,       0x647B30, 0x4760000),   # .securom (ceros)
    "we9":   (0x5D4A10,       0x620400, 0xACD400),    # cola de .text (Kitserver usa 0xACDFE0)
}
UNIDAD = 256.0  # 256 unidades = 1 metro

p = argparse.ArgumentParser()
p.add_argument("origen"); p.add_argument("destino"); p.add_argument("porcentaje", type=int)
p.add_argument("juego", nargs="?", default="we9le", choices=JUEGOS)
p.add_argument("--largo", type=float, default=31.0)
p.add_argument("--ancho", type=float, default=25.0)
a = p.parse_args()
assert 0 <= a.porcentaje <= 100
FUNC, RAND, CAVE = JUEGOS[a.juego]

d = bytearray(open(a.origen, "rb").read())
pe = pefile.PE(data=bytes(d), fast_load=True)
base = pe.OPTIONAL_HEADER.ImageBase
img = pe.get_memory_mapped_image()
off = lambda va: pe.get_offset_from_rva(va - base)

# punto de enganche: "mov cl,[esp+0x34]; mov [gravedad],cl" dentro de registrar falta
blk = img[FUNC - base:FUNC - base + 0x600]
i = blk.find(b"\x8a\x4c\x24\x34\x88\x0d")
if i < 0 or d[off(FUNC):off(FUNC) + 8] != bytes.fromhex("8b4c240c8b442408"):
    sys.exit("No reconozco la funcion 'registrar falta' en este exe (¿ya parcheado u otra version?).")
SITIO = FUNC + i
GRAV = struct.unpack("<I", blk[i + 6:i + 10])[0]   # 0x3B17341 en WE9LE
TIMER = GRAV + 3                                   # 0x3B17344: falta pendiente (0x7FFF = nada)
# puntero a la pelota: la funcion de puntaje (justo antes) hace "mov esi,[PELOTA]; fld [esi+0x10]"
pre = img[FUNC - base - 0xD0:FUNC - base]
k = pre.find(b"\x8b\x35")
PELOTA = struct.unpack("<I", pre[k + 2:k + 6])[0]
assert pre[k + 6:k + 9] == b"\xd9\x46\x10", "no encontre el puntero a la pelota"
if any(d[off(CAVE):off(CAVE) + 0x80]):
    sys.exit("La zona del code cave no esta vacia en este exe.")

f32 = lambda m: struct.unpack("<I", struct.pack("<f", m * UNIDAD))[0]
code_va = CAVE + 0x10
c = bytearray()
def rel(dest):  # rel32 para una instruccion de 5 bytes que empieza ahora
    return struct.pack("<i", dest - (code_va + len(c) + 5))
c += b"\x8a\x4c\x24\x34"                          # mov cl,[esp+0x34]   (original)
c += b"\x88\x0d" + struct.pack("<I", GRAV)        # mov [gravedad],cl   (original)
c += b"\x80\xf9\x01"                              # cmp cl,1
j_back = len(c); c += b"\x75\x00"                 # jne volver (tarjeta -> normal)
c += b"\x50\x52\x51"                              # push eax/edx/ecx
c += b"\x8b\x15" + struct.pack("<I", PELOTA)      # mov edx,[pelota]
c += b"\x8b\x42\x10"                              # mov eax,[edx+0x10]  (x)
c += b"\x25\xff\xff\xff\x7f"                      # and eax,7fffffff    (|x|)
c += b"\x3d" + struct.pack("<I", f32(a.largo))    # cmp eax, largo
j_lejos = len(c); c += b"\x72\x00"                # jb lejos
c += b"\x8b\x42\x18"                              # mov eax,[edx+0x18]  (y)
c += b"\x25\xff\xff\xff\x7f"
c += b"\x3d" + struct.pack("<I", f32(a.ancho))    # cmp eax, ancho
j_cerca = len(c); c += b"\x72\x00"                # jb restaurar (cerca del area -> se cobra)
lejos = len(c)
c += b"\x6a\x64"                                  # push 100
c += b"\xe8" + rel(RAND)                          # call rand
c += b"\x83\xc4\x04"                              # add esp,4
c += b"\x0f\xb6\x0d" + struct.pack("<I", CAVE)    # movzx ecx, byte [porcentaje]
c += b"\x39\xc8"                                  # cmp eax,ecx
j_cobra = len(c); c += b"\x73\x00"                # jae restaurar (sale cobrar)
c += b"\xc7\x05" + struct.pack("<I", TIMER) + struct.pack("<I", 0x7FFF)  # borrar falta pendiente
restaurar = len(c)
c += b"\x59\x5a\x58"                              # pop ecx/edx/eax
volver = len(c)
c += b"\xe9" + rel(SITIO + 10)                    # volver al juego
for pos, dest in ((j_back, volver), (j_lejos, lejos), (j_cerca, restaurar), (j_cobra, restaurar)):
    c[pos + 1] = dest - (pos + 2)

d[off(CAVE)] = a.porcentaje
d[off(code_va):off(code_va) + len(c)] = c
d[off(SITIO):off(SITIO) + 10] = b"\xe9" + struct.pack("<i", code_va - (SITIO + 5)) + b"\x90" * 5
open(a.destino, "wb").write(d)
print(f"OK ({a.juego}): {a.destino}\n  faltas simples lejos del area: se dejan pasar ~{a.porcentaje}%\n"
      f"  siempre se cobra: tarjetas y zona |x|>{a.largo} m, |y|<{a.ancho} m\n"
      f"  enganche {SITIO:#x}, gravedad {GRAV:#x}, pendiente {TIMER:#x}, pelota [{PELOTA:#x}], cave {CAVE:#x}")
