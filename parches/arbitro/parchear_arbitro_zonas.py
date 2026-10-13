"""
parchear_arbitro_zonas.py - WE9 / WE9LE: arbitro que "deja seguir" segun la ZONA de la cancha
(pedido de Matias 2026-10-09; reemplaza a la version selectiva).

Dentro de "registrar falta" el juego calcula la GRAVEDAD (1 = falta simple sin tarjeta, 2-4 = amarilla / roja).
Engancho ahi, miro donde esta la pelota y decido:
  - gravedad >= 2 (tarjeta)                                   -> se cobra siempre (vanilla)
  - ZONA AREA: |x| > largo y |y| < ancho (a ~22 m del arco)    -> vanilla (se cobra siempre)
  - ZONA LEJOS: a mas de --lejos m del arco (40 m por defecto) -> deja pasar pct_lejos %  (70)
  - ZONA MEDIA: el resto (entre 40 m y el area, y las bandas
    cerca del fondo)                                           -> deja pasar pct_medio %  (20)
"Del arco" = desde la linea de fondo mas cercana (media cancha = 52,6 m).
Para "dejarla pasar" se borra la falta pendiente (contador de ventaja = 0x7FFF, "nada pendiente").

uso: python parchear_arbitro_zonas.py <exe_origen> <exe_destino> <pct_lejos> <pct_medio> [we9le|we9]
     [--lejos 40] [--largo 31] [--ancho 25]
Los porcentajes quedan en los bytes CAVE+0 (lejos) y CAVE+1 (medio): se pueden cambiar con un editor hex.
"""
import sys, struct, argparse, pefile

JUEGOS = {
    #        registrar falta  rand(n)   code cave
    "we9le": (0x5FC1F0,       0x647B30, 0x4760000),   # .securom (ceros)
    "we9":   (0x5D4A10,       0x620400, 0xACD400),    # cola de .text (Kitserver usa 0xACDFE0)
}
UNIDAD = 256.0             # 256 unidades = 1 metro
MEDIA_CANCHA = 13465 / UNIDAD  # 52,6 m (constante del juego)

p = argparse.ArgumentParser()
p.add_argument("origen"); p.add_argument("destino")
p.add_argument("pct_lejos", type=int); p.add_argument("pct_medio", type=int)
p.add_argument("juego", nargs="?", default="we9le", choices=JUEGOS)
p.add_argument("--lejos", type=float, default=40.0, help="metros desde el arco a partir de los cuales es zona lejos")
p.add_argument("--largo", type=float, default=31.0, help="|x| desde el centro donde empieza la zona del area")
p.add_argument("--ancho", type=float, default=25.0, help="|y| desde el centro: ancho de la zona del area")
a = p.parse_args()
assert 0 <= a.pct_lejos <= 100 and 0 <= a.pct_medio <= 100
X_LEJOS = MEDIA_CANCHA - a.lejos   # |x| menor a esto = lejos de los dos arcos
assert 0 < X_LEJOS < a.largo
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
TIMER = GRAV + 3                                   # falta pendiente (0x7FFF = nada)
# puntero a la pelota: la funcion de puntaje (justo antes) hace "mov esi,[PELOTA]; fld [esi+0x10]"
pre = img[FUNC - base - 0xD0:FUNC - base]
k = pre.find(b"\x8b\x35")
PELOTA = struct.unpack("<I", pre[k + 2:k + 6])[0]
assert pre[k + 6:k + 9] == b"\xd9\x46\x10", "no encontre el puntero a la pelota"
if any(d[off(CAVE):off(CAVE) + 0x100]):
    sys.exit("La zona del code cave no esta vacia en este exe (¿ya tiene un parche de arbitro?).")

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
c += b"\x25\xff\xff\xff\x7f"                      # and eax,7fffffff    (|x|; float positivo compara como entero)
c += b"\x3d" + struct.pack("<I", f32(X_LEJOS))    # cmp eax, x_lejos
j_lejos = len(c); c += b"\x72\x00"                # jb lejos
c += b"\x3d" + struct.pack("<I", f32(a.largo))    # cmp eax, largo
j_medio = len(c); c += b"\x72\x00"                # jb medio
c += b"\x8b\x42\x18"                              # mov eax,[edx+0x18]  (y)
c += b"\x25\xff\xff\xff\x7f"                      # and eax,7fffffff    (|y|)
c += b"\x3d" + struct.pack("<I", f32(a.ancho))    # cmp eax, ancho
j_area = len(c); c += b"\x72\x00"                 # jb restaurar (zona del area -> vanilla)
medio = len(c)
c += b"\x0f\xb6\x0d" + struct.pack("<I", CAVE + 1)  # movzx ecx, byte [pct_medio]
j_tirar = len(c); c += b"\xeb\x00"                # jmp tirar
lejos = len(c)
c += b"\x0f\xb6\x0d" + struct.pack("<I", CAVE)    # movzx ecx, byte [pct_lejos]
tirar = len(c)
c += b"\x51"                                      # push ecx (pct; rand puede pisar ecx)
c += b"\x6a\x64"                                  # push 100
c += b"\xe8" + rel(RAND)                          # call rand -> eax 0..99
c += b"\x83\xc4\x04"                              # add esp,4
c += b"\x59"                                      # pop ecx
c += b"\x39\xc8"                                  # cmp eax,ecx
j_cobra = len(c); c += b"\x73\x00"                # jae restaurar (sale cobrar)
c += b"\xc7\x05" + struct.pack("<I", TIMER) + struct.pack("<I", 0x7FFF)  # borrar falta pendiente
restaurar = len(c)
c += b"\x59\x5a\x58"                              # pop ecx/edx/eax
volver = len(c)
c += b"\xe9" + rel(SITIO + 10)                    # volver al juego
for pos, dest in ((j_back, volver), (j_lejos, lejos), (j_medio, medio), (j_area, restaurar),
                  (j_tirar, tirar), (j_cobra, restaurar)):
    c[pos + 1] = dest - (pos + 2)
assert len(c) <= 0xF0

d[off(CAVE)] = a.pct_lejos
d[off(CAVE) + 1] = a.pct_medio
d[off(code_va):off(code_va) + len(c)] = c
d[off(SITIO):off(SITIO) + 10] = b"\xe9" + struct.pack("<i", code_va - (SITIO + 5)) + b"\x90" * 5
open(a.destino, "wb").write(d)
print(f"OK ({a.juego}): {a.destino}\n"
      f"  lejos (a mas de {a.lejos:g} m del arco): deja pasar ~{a.pct_lejos}% de las faltas simples\n"
      f"  medio (hasta la zona del area): deja pasar ~{a.pct_medio}%\n"
      f"  vanilla: tarjetas y zona del area (a ~{MEDIA_CANCHA - a.largo:.1f} m del arco, |y|<{a.ancho:g} m)\n"
      f"  enganche {SITIO:#x}, gravedad {GRAV:#x}, pendiente {TIMER:#x}, pelota [{PELOTA:#x}], cave {CAVE:#x}, {len(c)} bytes")
