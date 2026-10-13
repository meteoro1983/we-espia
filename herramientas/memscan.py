"""
memscan.py - buscador de valores en memoria (estilo Cheat Engine) para WE9/WE9LE.

Pensado para usarse paso a paso desde la consola mientras el juego corre en ventana:

  python memscan.py nuevo  <valor> [--tipo i32|i16|u8|f32] [--proc WE9LEK.exe] [--sesion nombre]
      Primer escaneo: guarda todas las direcciones escribibles que valen <valor>.
  python memscan.py filtrar <valor>     [--sesion nombre]
      Se queda solo con las que AHORA valen <valor>.
  python memscan.py cambio igual|subio|bajo|distinto [--sesion nombre]
      Filtra por cambio respecto de la lectura anterior (sin saber el valor).
  python memscan.py ver [--max 40]      [--sesion nombre]
      Muestra los candidatos y su valor actual.
  python memscan.py leer <va_hex> [n]   [--proc ...]
      Hexdump de n bytes en una VA.

La sesion (candidatos + valores) se guarda en sesiones_memscan/<nombre>.npz
"""
import argparse, ctypes, ctypes.wintypes as wt, os, sys
import numpy as np

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
AQUI = os.path.dirname(os.path.abspath(__file__))
SES_DIR = os.path.join(AQUI, "sesiones_memscan")
TIPOS = {"i32": np.int32, "i16": np.int16, "u8": np.uint8, "f32": np.float32}


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", wt.DWORD), ("PartitionId", wt.WORD),
                ("RegionSize", ctypes.c_size_t), ("State", wt.DWORD),
                ("Protect", wt.DWORD), ("Type", wt.DWORD)]


class PE32(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wt.DWORD),
                ("cntThreads", wt.DWORD), ("th32ParentProcessID", wt.DWORD),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
                ("szExeFile", ctypes.c_char * 260)]


k32.VirtualQueryEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.POINTER(MBI), ctypes.c_size_t]
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                  ctypes.POINTER(ctypes.c_size_t)]
k32.OpenProcess.restype = wt.HANDLE


def buscar_pid(nombre):
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)
    e = PE32(); e.dwSize = ctypes.sizeof(e)
    ok = k32.Process32First(snap, ctypes.byref(e))
    while ok:
        if e.szExeFile.decode(errors="ignore").lower() == nombre.lower():
            k32.CloseHandle(snap); return e.th32ProcessID
        ok = k32.Process32Next(snap, ctypes.byref(e))
    k32.CloseHandle(snap)
    return None


PID_FORZADO = None


def abrir(proc):
    pid = PID_FORZADO or buscar_pid(proc)
    if not pid:
        sys.exit(f"No encuentro {proc} corriendo.")
    h = k32.OpenProcess(0x0410, False, pid)  # VM_READ | QUERY_INFORMATION
    if not h:
        sys.exit(f"No pude abrir {proc} (error {ctypes.get_last_error()}).")
    return h


def regiones(h):
    """Regiones comprometidas y escribibles (heap, .data, pilas) por debajo de 4 GB."""
    a, m = 0, MBI()
    while a < 0xFFFF0000 and k32.VirtualQueryEx(h, ctypes.c_void_p(a), ctypes.byref(m), ctypes.sizeof(m)):
        base, size = m.BaseAddress or 0, m.RegionSize
        if m.State == 0x1000 and (m.Protect & 0xCC) and not (m.Protect & 0x100):  # RW/WC/XRW/XWC, sin GUARD
            yield base, size
        a = base + size


def leer(h, va, n):
    buf = (ctypes.c_char * n)()
    got = ctypes.c_size_t()
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(va), buf, n, ctypes.byref(got)):
        return None
    return bytes(buf[:got.value])


def ruta(sesion):
    os.makedirs(SES_DIR, exist_ok=True)
    return os.path.join(SES_DIR, sesion + ".npz")


def guardar(sesion, addrs, vals, tipo, proc):
    np.savez(ruta(sesion), addrs=addrs, vals=vals, tipo=tipo, proc=proc)


def cargar(sesion):
    d = np.load(ruta(sesion), allow_pickle=False)
    return d["addrs"], d["vals"], str(d["tipo"]), str(d["proc"])


def leer_actuales(h, addrs, dt):
    """Relee valores de las direcciones candidatas (agrupando por pagina para ir rapido)."""
    sz = np.dtype(dt).itemsize
    out = np.zeros(len(addrs), dtype=dt)
    ok = np.zeros(len(addrs), dtype=bool)
    if len(addrs) == 0:
        return out, ok
    paginas = addrs // 0x1000
    cortes = np.flatnonzero(np.diff(paginas)) + 1
    for grupo in np.split(np.arange(len(addrs)), cortes):
        a0 = int(addrs[grupo[0]]); a1 = int(addrs[grupo[-1]]) + sz
        b = leer(h, a0, a1 - a0)
        if b is None or len(b) < a1 - a0:
            continue
        offs = (addrs[grupo] - a0).astype(np.int64)
        vals = np.frombuffer(b"".join(b[o:o + sz] for o in offs), dtype=dt)
        out[grupo] = vals; ok[grupo] = True
    return out, ok


def cmd_nuevo(a):
    dt = TIPOS[a.tipo]
    valor = dt(float(a.valor) if a.tipo == "f32" else int(a.valor))
    h = abrir(a.proc)
    sz = np.dtype(dt).itemsize
    todas, total = [], 0
    for base, size in regiones(h):
        b = leer(h, base, size)
        if not b:
            continue
        total += len(b)
        n = (len(b) // sz) * sz
        arr = np.frombuffer(b[:n], dtype=dt)  # alineado al tamano del tipo
        idx = np.flatnonzero(arr == valor)
        if len(idx):
            todas.append(base + idx.astype(np.int64) * sz)
    addrs = np.concatenate(todas) if todas else np.zeros(0, np.int64)
    guardar(a.sesion, addrs, np.full(len(addrs), valor, dtype=dt), a.tipo, a.proc)
    print(f"Escaneados {total/1e6:.0f} MB -> {len(addrs)} candidatos con valor {valor}.")


def filtrar_y_guardar(a, cond):
    addrs, vals, tipo, proc = cargar(a.sesion)
    dt = TIPOS[tipo]
    h = abrir(proc)
    act, ok = leer_actuales(h, addrs, dt)
    keep = ok & cond(vals, act)
    guardar(a.sesion, addrs[keep], act[keep], tipo, proc)
    print(f"{len(addrs)} -> {int(keep.sum())} candidatos.")
    if keep.sum() <= 40:
        for ad, v in zip(addrs[keep], act[keep]):
            print(f"  {int(ad):#010x} = {v}")


def cmd_filtrar(a):
    addrs, vals, tipo, proc = cargar(a.sesion)
    dt = TIPOS[tipo]
    valor = dt(float(a.valor) if tipo == "f32" else int(a.valor))
    filtrar_y_guardar(a, lambda old, new: new == valor)


def cmd_cambio(a):
    c = {"igual": lambda o, n: n == o, "subio": lambda o, n: n > o,
         "bajo": lambda o, n: n < o, "distinto": lambda o, n: n != o}[a.como]
    filtrar_y_guardar(a, c)


def cmd_ver(a):
    addrs, vals, tipo, proc = cargar(a.sesion)
    h = abrir(proc)
    act, ok = leer_actuales(h, addrs[:a.max], TIPOS[tipo])
    print(f"{len(addrs)} candidatos ({tipo}, {proc}). Primeros {min(a.max, len(addrs))}:")
    for ad, v0, v in zip(addrs[:a.max], vals[:a.max], act):
        print(f"  {int(ad):#010x}  antes {v0}  ahora {v}")


def cmd_leer(a):
    h = abrir(a.proc)
    va, n = int(a.va, 16), a.n
    b = leer(h, va, n) or b""
    for i in range(0, len(b), 16):
        print(f"{va+i:#010x}  {b[i:i+16].hex(' ')}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sesion", default="faltas")
    p.add_argument("--proc", default="WE9LEK.exe")
    p.add_argument("--pid", type=int, help="usar este PID (si hay varios procesos con el mismo nombre)")
    sp = p.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("nuevo"); s.add_argument("valor"); s.add_argument("--tipo", default="i32", choices=TIPOS)
    s = sp.add_parser("filtrar"); s.add_argument("valor")
    s = sp.add_parser("cambio"); s.add_argument("como", choices=["igual", "subio", "bajo", "distinto"])
    s = sp.add_parser("ver"); s.add_argument("--max", type=int, default=40)
    s = sp.add_parser("leer"); s.add_argument("va"); s.add_argument("n", type=int, nargs="?", default=64)
    a = p.parse_args()
    global PID_FORZADO
    PID_FORZADO = a.pid
    {"nuevo": cmd_nuevo, "filtrar": cmd_filtrar, "cambio": cmd_cambio, "ver": cmd_ver, "leer": cmd_leer}[a.cmd](a)


if __name__ == "__main__":
    main()
