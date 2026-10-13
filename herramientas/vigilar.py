"""
vigilar.py - "Find out what writes to this address" sin Cheat Engine (juegos de 32 bits).

  python vigilar.py <va_hex> [--modo escribe|accede|ejecuta] [--largo 1|2|4]
                    [--segundos 120] [--proc WE9LEK.exe] [--max 50]

Se engancha al proceso como depurador, pone un breakpoint por HARDWARE (DR0) en la direccion
en todos los hilos y anota cada instruccion que la toca: direccion de la instruccion,
registros y el valor de la direccion en ese momento. Al terminar (tiempo o --max impactos)
quita el breakpoint y se desengancha SIN cerrar el juego.

Ojo: en modo escribe/accede la CPU frena DESPUES de la instruccion; se muestra la instruccion
anterior desensamblada (busca hacia atras) para ver quien escribio.
Salida: tambien queda en vigilar_<va>.log al lado del script.
"""
import argparse, ctypes, ctypes.wintypes as wt, os, sys, time

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
AQUI = os.path.dirname(os.path.abspath(__file__))

DBG_CONTINUE, DBG_NOT_HANDLED = 0x00010002, 0x80010001
EXC_BREAKPOINT, EXC_SINGLE_STEP = 0x80000003, 0x80000004
WX86_BREAKPOINT, WX86_SINGLE_STEP = 0x4000001F, 0x4000001E
WOW64_CONTEXT_ALL = 0x00010000 | 0x01 | 0x02 | 0x10  # CONTROL | INTEGER | DEBUG_REGISTERS


class WOW64_CONTEXT(ctypes.Structure):
    _fields_ = [("ContextFlags", wt.DWORD),
                ("Dr0", wt.DWORD), ("Dr1", wt.DWORD), ("Dr2", wt.DWORD), ("Dr3", wt.DWORD),
                ("Dr6", wt.DWORD), ("Dr7", wt.DWORD),
                ("FloatSave", ctypes.c_byte * 112),
                ("SegGs", wt.DWORD), ("SegFs", wt.DWORD), ("SegEs", wt.DWORD), ("SegDs", wt.DWORD),
                ("Edi", wt.DWORD), ("Esi", wt.DWORD), ("Ebx", wt.DWORD), ("Edx", wt.DWORD),
                ("Ecx", wt.DWORD), ("Eax", wt.DWORD), ("Ebp", wt.DWORD), ("Eip", wt.DWORD),
                ("SegCs", wt.DWORD), ("EFlags", wt.DWORD), ("Esp", wt.DWORD), ("SegSs", wt.DWORD),
                ("ExtendedRegisters", ctypes.c_byte * 512)]


class DEBUG_EVENT(ctypes.Structure):
    _fields_ = [("code", wt.DWORD), ("pid", wt.DWORD), ("tid", wt.DWORD),
                ("_pad", wt.DWORD), ("u", ctypes.c_ubyte * 176)]


class PE32(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wt.DWORD),
                ("cntThreads", wt.DWORD), ("th32ParentProcessID", wt.DWORD),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
                ("szExeFile", ctypes.c_char * 260)]


k32.WaitForDebugEvent.argtypes = [ctypes.POINTER(DEBUG_EVENT), wt.DWORD]
k32.Wow64GetThreadContext.argtypes = [wt.HANDLE, ctypes.POINTER(WOW64_CONTEXT)]
k32.Wow64SetThreadContext.argtypes = [wt.HANDLE, ctypes.POINTER(WOW64_CONTEXT)]
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                  ctypes.POINTER(ctypes.c_size_t)]
k32.OpenProcess.restype = wt.HANDLE
k32.CloseHandle.argtypes = [wt.HANDLE]


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


def u_ptr(ev, off):
    return ctypes.c_uint64.from_buffer_copy(bytes(ev.u[off:off + 8])).value


def u_dword(ev, off):
    return ctypes.c_uint32.from_buffer_copy(bytes(ev.u[off:off + 4])).value


def main():
    p = argparse.ArgumentParser()
    p.add_argument("va")
    p.add_argument("--modo", default="escribe", choices=["escribe", "accede", "ejecuta"])
    p.add_argument("--largo", type=int, default=4, choices=[1, 2, 4])
    p.add_argument("--segundos", type=float, default=120)
    p.add_argument("--proc", default="WE9LEK.exe")
    p.add_argument("--pid", type=int)
    p.add_argument("--max", type=int, default=50)
    p.add_argument("--al", help="solo cuenta impactos con AL en este rango hex, ej. 25-2b")
    p.add_argument("--pila", type=int, default=0, help="bytes de pila a revisar buscando direcciones de retorno")
    a = p.parse_args()

    va = int(a.va, 16)
    pid = a.pid or buscar_pid(a.proc)
    if not pid:
        sys.exit(f"No encuentro {a.proc} corriendo.")
    rw = {"ejecuta": 0, "escribe": 1, "accede": 3}[a.modo]
    ln = 0 if a.modo == "ejecuta" else {1: 0, 2: 1, 4: 3}[a.largo]
    dr7 = 0x1 | (rw << 16) | (ln << 18)

    try:
        import capstone
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    except ImportError:
        md = None

    hproc = k32.OpenProcess(0x0410, False, pid)
    hilos = {}  # tid -> handle
    log = open(os.path.join(AQUI, f"vigilar_{va:08x}.log"), "w", encoding="utf-8")

    def out(s):
        print(s); log.write(s + "\n"); log.flush()

    def leer(addr, n):
        buf = (ctypes.c_char * n)(); got = ctypes.c_size_t()
        k32.ReadProcessMemory(hproc, ctypes.c_void_p(addr), buf, n, ctypes.byref(got))
        return bytes(buf[:got.value])

    def poner(h, activo=True):
        c = WOW64_CONTEXT(); c.ContextFlags = WOW64_CONTEXT_ALL
        if not k32.Wow64GetThreadContext(h, ctypes.byref(c)):
            return False
        c.Dr0 = va if activo else 0
        c.Dr7 = (c.Dr7 & ~0xF0003) | (dr7 if activo else 0)
        c.Dr6 = 0
        return bool(k32.Wow64SetThreadContext(h, ctypes.byref(c)))

    def instr_anterior(eip):
        """Busca la instruccion que termina justo en eip (la que escribio)."""
        if md is None:
            return "?"
        b = leer(eip - 15, 15)
        for back in range(15, 0, -1):
            ins = list(md.disasm(b[15 - back:], eip - back))
            if ins and sum(i.size for i in ins) == back and len(ins) == 1:
                return f"{ins[0].address:#010x}  {ins[0].mnemonic} {ins[0].op_str}"
        for back in range(1, 16):
            ins = list(md.disasm(b[15 - back:], eip - back))
            if ins and sum(i.size for i in ins) == back:
                i = ins[-1]
                return f"{i.address:#010x}  {i.mnemonic} {i.op_str}"
        return "?"

    if not k32.DebugActiveProcess(pid):
        sys.exit(f"No pude engancharme (error {ctypes.get_last_error()}). ¿Hay otro depurador?")
    k32.DebugSetProcessKillOnExit(False)
    out(f"Enganchado a pid {pid}. Vigilando {va:#010x} ({a.modo}, {a.largo} bytes) por {a.segundos:.0f} s / {a.max} impactos.")

    fin = time.time() + a.segundos
    impactos, por_eip, armado = 0, {}, False
    ev = DEBUG_EVENT()
    try:
        while time.time() < fin and impactos < a.max:
            if not k32.WaitForDebugEvent(ctypes.byref(ev), 200):
                continue
            estado = DBG_CONTINUE
            if ev.code == 3:  # CREATE_PROCESS
                hf = u_ptr(ev, 0)
                if hf: k32.CloseHandle(hf)
                hilos[ev.tid] = u_ptr(ev, 16)
            elif ev.code == 2:  # CREATE_THREAD
                hilos[ev.tid] = u_ptr(ev, 0)
                if armado: poner(hilos[ev.tid])
            elif ev.code == 4:  # EXIT_THREAD
                hilos.pop(ev.tid, None)
            elif ev.code == 6:  # LOAD_DLL
                hf = u_ptr(ev, 0)
                if hf: k32.CloseHandle(hf)
            elif ev.code == 5:  # EXIT_PROCESS
                out("El juego se cerró."); break
            elif ev.code == 1:  # EXCEPTION
                cod = u_dword(ev, 0)
                if cod in (EXC_BREAKPOINT, WX86_BREAKPOINT):
                    if not armado:
                        ok = sum(poner(h) for h in hilos.values())
                        armado = True
                        out(f"Breakpoint puesto en {ok}/{len(hilos)} hilos. Jugá normalmente.")
                    else:
                        estado = DBG_NOT_HANDLED  # int3 propio del juego: que lo maneje el juego
                elif cod in (EXC_SINGLE_STEP, WX86_SINGLE_STEP) and ev.tid in hilos:
                    h = hilos[ev.tid]
                    c = WOW64_CONTEXT(); c.ContextFlags = WOW64_CONTEXT_ALL
                    k32.Wow64GetThreadContext(h, ctypes.byref(c))
                    filtro_ok = True
                    if c.Dr6 & 1 and a.al:
                        lo, hi = (int(x, 16) for x in a.al.split("-"))
                        filtro_ok = lo <= (c.Eax & 0xff) <= hi
                    if c.Dr6 & 1 and not filtro_ok:
                        if a.modo == "ejecuta":
                            c.EFlags |= 0x10000
                        c.Dr6 = 0
                        k32.Wow64SetThreadContext(h, ctypes.byref(c))
                    elif c.Dr6 & 1:
                        impactos += 1
                        valor = leer(va, a.largo)
                        quien = f"{c.Eip:#010x}" if a.modo == "ejecuta" else instr_anterior(c.Eip)
                        clave = quien.split()[0]
                        por_eip[clave] = por_eip.get(clave, 0) + 1
                        out(f"[{impactos}] {time.strftime('%H:%M:%S')} hilo {ev.tid} -> {quien}"
                            f" | valor ahora {valor.hex(' ')} | eax={c.Eax:#x} ebx={c.Ebx:#x} ecx={c.Ecx:#x}"
                            f" edx={c.Edx:#x} esi={c.Esi:#x} edi={c.Edi:#x} ebp={c.Ebp:#x} esp={c.Esp:#x}"
                            f" pila={leer(c.Esp, 16).hex(' ')}")
                        if a.pila:
                            pb = leer(c.Esp, a.pila)
                            rets = [int.from_bytes(pb[i:i+4], "little") for i in range(0, len(pb) - 3, 4)]
                            rets = [f"{r:#x}" for r in rets if 0x401000 <= r < 0xace000]
                            out("      retornos? " + " ".join(rets))
                        if a.modo == "ejecuta":
                            c.EFlags |= 0x10000  # RF: no volver a frenar en la misma instruccion
                        c.Dr6 = 0
                        k32.Wow64SetThreadContext(h, ctypes.byref(c))
                    else:
                        estado = DBG_NOT_HANDLED
                else:
                    estado = DBG_NOT_HANDLED
            k32.ContinueDebugEvent(ev.pid, ev.tid, estado)
    finally:
        # quitar breakpoints: hace falta que los hilos esten frenados -> usar el proximo evento o suspender
        for h in hilos.values():
            k32.SuspendThread(h); poner(h, False); k32.ResumeThread(h)
        k32.DebugActiveProcessStop(pid)
        out(f"Desenganchado. {impactos} impactos. Resumen por instrucción:")
        for k, v in sorted(por_eip.items(), key=lambda x: -x[1]):
            out(f"  {k}  x{v}")
        log.close()


if __name__ == "__main__":
    main()
