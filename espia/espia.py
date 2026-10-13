"""
espia.py - lee EN VIVO lo que pasa en un partido de WE9 / WE9 LIVEWARE EVOLUTION / PES6 (PC)
sin tocar el juego (solo lectura de memoria, sin inyectar nada).

  python espia.py diagnostico            busca el juego y las direcciones, y dice que encontro
  python espia.py vivo [opciones]        muestra los eventos del partido a medida que pasan
        --jsonl partido.jsonl            ademas los guarda, un JSON por linea (para otras herramientas)
        --toques                         incluye cada cambio de "ultimo jugador que toco la pelota"
        --cada 0.1                       segundos entre lecturas
        --proc NOMBRE.exe / --pid N      forzar proceso (por defecto busca WE9LEK.exe, we9.exe, PES6.exe)

Las direcciones NO estan fijas en el codigo: se buscan por FIRMA (patron de bytes de la rutina) en
la memoria del juego ya arrancado. Asi el mismo script sirve para los tres exes, aunque el exe en
disco este cifrado (SecuROM) o parcheado por Kingsley/kitserver.
Al cerrar (Ctrl+C) imprime un resumen por equipo.

Requiere Python 3 (64 o 32 bits) en Windows. Sin dependencias.
"""
import argparse, ctypes, ctypes.wintypes as wt, json, re, struct, sys, time

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                  ctypes.POINTER(ctypes.c_size_t)]
k32.OpenProcess.restype = wt.HANDLE
PROCESOS = ["WE9LEK.exe", "we9.exe", "PES6.exe", "pes6.exe"]

# Firmas verificadas en WE9LEK (crack limpio y Kingsley V5.5) y we9.exe (nocd).
# PES6 comparte motor: deberian aparecer igual (correr "diagnostico" para confirmarlo).
FIRMAS = {
    # getter de la lista de eventos: call <getter> ; add eax, OFF ; ret  + recorredor de registros
    # getter = mov eax,[PTR] ; add eax,0x14 ; ret   ->  lista = [PTR] + 0x14 + OFF
    "lista": rb"\xE8(....)\x05(....)\xC3[\x90\xCC]{1,15}\x8B\x44\x24\x04\x85\xC0\x74.\x0F\xB6\x08"
             rb"\x83\xC1\xF5\x83\xF9\x0F\x77",
    # mov al,[esp+8] ; mov [TOQUE],al ; xor eax,eax ; mov [..],eax
    "toque": rb"\x8A\x44\x24\x08\xA2(....)\x33\xC0\xA3",
    # cambiar fase: cmp esi,9 ; mov [esi+FASES],bl  -> fase del partido = FASES+1
    "fase": rb"\x53\x8B\x5C\x24\x0C\x56\x8B\x74\x24\x0C\x83\xFE\x09\x88\x9E(....)",
}

# Codigos de la lista de eventos. "ok" = confirmado en vivo; "?" = deducido, falta confirmar.
CODIGOS = {
    0x01: ("saque_inicial", "ok"), 0x03: ("falta", "ok"), 0x05: ("lateral_o_saque", "?"),
    0x06: ("lateral_o_saque", "?"), 0x08: ("tiro_libre", "?"), 0x0B: ("pase", "?"),
    0x16: ("tiro", "?"), 0x18: ("tiro", "?"), 0x19: ("tiro", "?"),
}
FASES = {1: "en_juego", 2: "preparar_pelota_parada", 3: "lateral_o_saque", 6: "falta_tiro_libre",
         9: "lateral_o_saque", 11: "?", 12: "?"}


class PE32(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wt.DWORD),
                ("cntThreads", wt.DWORD), ("th32ParentProcessID", wt.DWORD),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
                ("szExeFile", ctypes.c_char * 260)]


def buscar_proceso(nombres):
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)
    e = PE32(); e.dwSize = ctypes.sizeof(e)
    ok, encontrados = k32.Process32First(snap, ctypes.byref(e)), {}
    while ok:
        encontrados[e.szExeFile.decode(errors="ignore").lower()] = e.th32ProcessID
        ok = k32.Process32Next(snap, ctypes.byref(e))
    k32.CloseHandle(snap)
    for n in nombres:
        if n.lower() in encontrados:
            return n, encontrados[n.lower()]
    return None, None


class Juego:
    def __init__(self, proc=None, pid=None):
        if pid:
            self.nombre, self.pid = proc or f"pid {pid}", pid
        else:
            self.nombre, self.pid = buscar_proceso([proc] if proc else PROCESOS)
        if not self.pid:
            sys.exit("No encuentro el juego corriendo (WE9LEK.exe / we9.exe / PES6.exe). Usá --proc o --pid.")
        self.h = k32.OpenProcess(0x0410, False, self.pid)  # VM_READ | QUERY_INFORMATION
        if not self.h:
            sys.exit(f"No pude abrir el proceso (error {ctypes.get_last_error()}). Probá la consola como administrador.")
        self.dir = {}

    def leer(self, va, n):
        buf = (ctypes.c_char * n)(); got = ctypes.c_size_t()
        if not k32.ReadProcessMemory(self.h, ctypes.c_void_p(va), buf, n, ctypes.byref(got)):
            return None
        return bytes(buf[:got.value])

    def u32(self, va):
        b = self.leer(va, 4)
        return struct.unpack("<I", b)[0] if b and len(b) == 4 else None

    def u8(self, va):
        b = self.leer(va, 1)
        return b[0] if b else None

    def localizar(self):
        """Lee la imagen del exe ya cargada (y descifrada) y busca las firmas."""
        base = 0x400000
        cab = self.leer(base, 0x1000)
        if not cab or cab[:2] != b"MZ":
            sys.exit("No pude leer la cabecera del exe en memoria.")
        pe = struct.unpack_from("<I", cab, 0x3C)[0]
        tam = struct.unpack_from("<I", cab, pe + 0x50)[0]  # SizeOfImage
        img = bytearray(tam)
        for off in range(0, tam, 0x10000):  # por bloques: las paginas ilegibles quedan en cero
            b = self.leer(base + off, min(0x10000, tam - off))
            if b:
                img[off:off + len(b)] = b
        def lista(m):
            g = m.start() + 5 + struct.unpack("<i", m.group(1))[0]
            if img[g] == 0xA1 and img[g + 5:g + 9] == bytes.fromhex("83 C0 14 C3"):
                return struct.unpack_from("<I", img, g + 1)[0], 0x14 + struct.unpack("<I", m.group(2))[0]
        derivar = {"lista": lista,
                   "toque": lambda m: struct.unpack("<I", m.group(1))[0],
                   "fase": lambda m: struct.unpack("<I", m.group(1))[0] + 1}
        res = {}
        for clave, patron in FIRMAS.items():
            # puede haber copias del mismo codigo (SecuROM): vale si todas dan la misma direccion
            valores = {derivar[clave](m) for m in re.finditer(patron, img, re.S)} - {None}
            res[clave] = len(valores)
            if len(valores) == 1:
                v = valores.pop()
                if clave == "lista":
                    self.dir["lista_ptr"], self.dir["lista_off"] = v
                else:
                    self.dir[clave] = v
        return res

    def lista(self):
        p = self.u32(self.dir["lista_ptr"])
        return p + self.dir["lista_off"] if p else None


def recorrer(buf):
    """Corta la lista en registros (misma logica que la rutina del juego). Termina en byte 0."""
    regs, i = [], 0
    while i < len(buf) and buf[i] != 0:
        c = buf[i]
        if 0x0B <= c <= 0x10:
            n = 8
        elif 0x11 <= c <= 0x1A:
            if i + 3 >= len(buf):
                break
            n = 4 + 4 * buf[i + 3]
        else:
            n = 4
        if i + n > len(buf):
            break
        regs.append(buf[i:i + n]); i += n
    return regs


def decodificar(r):
    tipo, estado = CODIGOS.get(r[0], (f"codigo_{r[0]:02x}", "?"))
    ev = {"codigo": r[0], "tipo": tipo, "confirmado": estado == "ok",
          "equipo": "local" if r[1] >> 7 == 0 else "visitante", "jugador": r[1] & 0x7F,
          "minuto": r[2], "flags": r[3], "crudo": r.hex(" ")}
    if r[0] == 0x03:
        ev["tarjeta_u_otro"] = r[3] != 0x80  # 0x80 = falta comun; otros valores = con tarjeta u otra cosa (a confirmar)
    if r[0] == 0x0B and len(r) == 8:  # [0B, pasador, ?, ?, 00, receptor, ?, ?]
        ev["receptor"] = r[5] & 0x7F
    return ev


class ExeEnDisco(Juego):
    """Mapea un exe del disco como lo haria Windows, para probar firmas sin el juego abierto."""
    def __init__(self, ruta):
        d = open(ruta, "rb").read()
        pe = struct.unpack_from("<I", d, 0x3C)[0]
        nsec, opt = struct.unpack_from("<H", d, pe + 6)[0], struct.unpack_from("<H", d, pe + 20)[0]
        self.base = struct.unpack_from("<I", d, pe + 0x34)[0]
        self.img = bytearray(struct.unpack_from("<I", d, pe + 0x50)[0])
        self.img[:0x1000] = d[:0x1000]
        for i in range(nsec):
            va, raw_tam, raw = struct.unpack_from("<III", d, pe + 24 + opt + i * 40 + 12)
            trozo = d[raw:raw + min(raw_tam, len(self.img) - va)]
            self.img[va:va + len(trozo)] = trozo
        self.nombre, self.pid, self.dir = ruta, 0, {}

    def leer(self, va, n):
        o = va - self.base
        return bytes(self.img[o:o + n]) if 0 <= o < len(self.img) else None


def cmd_diagnostico(a):
    j = ExeEnDisco(a.exe) if a.exe else Juego(a.proc, a.pid)
    print(f"Proceso: {j.nombre} (pid {j.pid})")
    hits = j.localizar()
    for k, n in hits.items():
        estado = "OK" if n == 1 else ("NO ENCONTRADA" if n == 0 else f"AMBIGUA ({n} direcciones distintas)")
        print(f"  firma {k:6} {estado}")
    for k, v in j.dir.items():
        print(f"  {k:10} = {v:#x}")
    if a.exe:
        return
    if "lista_ptr" in j.dir:
        base = j.lista()
        if base:
            regs = recorrer(j.leer(base, 0x2000) or b"")
            print(f"  lista de eventos en {base:#x}: {len(regs)} registros ahora mismo")
        else:
            print("  lista de eventos: puntero en 0 (normal fuera de un partido)")
    if "fase" in j.dir:
        f = j.u8(j.dir["fase"]); print(f"  fase actual = {f} ({FASES.get(f, '?')})")
    if "toque" in j.dir:
        t = j.u8(j.dir["toque"]); print(f"  ultimo toque = {t} (0-10 local, 11-21 visitante)")


def cmd_vivo(a):
    j = Juego(a.proc, a.pid)
    j.localizar()
    if "lista_ptr" not in j.dir:
        sys.exit("No encontré la lista de eventos en este exe. Corré 'diagnostico' y mirá docs/PORTAR.md.")
    out = open(a.jsonl, "a", encoding="utf-8") if a.jsonl else None
    print(f"Espiando {j.nombre} (pid {j.pid}). Ctrl+C para terminar.")
    vistos, fase0, toque0, resumen = 0, None, None, {}

    def emitir(ev):
        ev = {"t": round(time.time(), 2), **ev}
        if out:
            out.write(json.dumps(ev, ensure_ascii=False) + "\n"); out.flush()
        if ev["tipo"] == "toque":
            print(f"  toque  -> jugador {ev['jugador']} {ev['equipo']}")
        elif ev["tipo"] == "fase":
            print(f"  fase   -> {ev['fase']} ({ev['nombre']})")
        else:
            extra = f" -> {ev['receptor']}" if "receptor" in ev else ""
            print(f"[{ev['minuto']:3}'] {ev['tipo']:16} {ev['equipo']:9} jug {ev['jugador']:2}{extra}  ({ev['crudo']})")

    try:
        while True:
            base = j.lista()
            regs = recorrer(j.leer(base, 0x2000) or b"") if base else []
            if len(regs) < vistos:  # partido nuevo o lista reiniciada
                vistos = 0
            for r in regs[vistos:]:
                ev = decodificar(r)
                emitir(ev)
                clave = (ev["equipo"], ev["tipo"])
                resumen[clave] = resumen.get(clave, 0) + 1
            vistos = len(regs)
            if "fase" in j.dir:
                f = j.u8(j.dir["fase"])
                if f is not None and f != fase0:
                    emitir({"tipo": "fase", "fase": f, "nombre": FASES.get(f, "?")}); fase0 = f
            if a.toques and "toque" in j.dir:
                t = j.u8(j.dir["toque"])
                if t is not None and t != toque0 and t < 22:
                    emitir({"tipo": "toque", "jugador": t % 11, "equipo": "local" if t < 11 else "visitante"})
                toque0 = t
            if j.u32(j.dir["lista_ptr"]) is None:
                print("El juego se cerró."); break
            time.sleep(a.cada)
    except KeyboardInterrupt:
        pass
    print("\nResumen (eventos de la lista):")
    for (eq, tipo), n in sorted(resumen.items()):
        print(f"  {eq:9} {tipo:16} {n}")
    if out:
        out.close()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    comun = argparse.ArgumentParser(add_help=False)
    comun.add_argument("--proc"); comun.add_argument("--pid", type=int)
    sp = p.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("diagnostico", parents=[comun])
    s.add_argument("--exe", help="probar las firmas en un exe en disco (sin arrancarlo; no sirve si esta cifrado)")
    s = sp.add_parser("vivo", parents=[comun])
    s.add_argument("--jsonl"); s.add_argument("--toques", action="store_true")
    s.add_argument("--cada", type=float, default=0.1)
    a = p.parse_args()
    {"diagnostico": cmd_diagnostico, "vivo": cmd_vivo}[a.cmd](a)


if __name__ == "__main__":
    main()
