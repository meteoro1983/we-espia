"""
we9le_registro.py - registrador de memoria para WE9LE (sin Cheat Engine).

Modos:
  python we9le_registro.py verificar
      Lee la fisica de pelota del juego en ejecucion (confirma que el
      gameplay.cfg del modulo se aplico).

  python we9le_registro.py grabar
      Queda escuchando teclas mientras jugas. Cada tecla saca una "foto"
      de la memoria del juego con una etiqueta:
          F9  = control (no paso nada desde la foto anterior)
          F10 = falta cometida por el equipo LOCAL
          F11 = falta cometida por el equipo VISITANTE
          F12 = tarjeta (amarilla o roja)
      Un pitido confirma cada foto. Ctrl+C en la consola para terminar.
      Consejo: PAUSA el juego, apreta la tecla, y segui. Arranca con F9 en
      el saque inicial. Una sesion = un partido (los contadores se reinician).

  python we9le_registro.py analizar <carpeta_sesion> --eventos local[,visitante,...]
      Busca direcciones que suben +1 exactamente en esos eventos y no
      cambian en los controles (F9). Lista los mejores candidatos.

Requiere Python 3 de 64 o 32 bits y numpy (solo para analizar).
"""
import ctypes, ctypes.wintypes as wt, json, os, struct, sys, time, zlib

PROCESO = os.environ.get("WE9_PROC", "WE9LEK.exe")  # WE9_PROC=WE9LEK_K55.exe para otro nombre
# Secciones de datos escribibles del exe (VA). Ahi vive casi todo el estado del partido.
REGIONES = [(0x0B0C000, 0x3068000), (0x42F8000, 0x03D9000)]
TECLAS = {0x78: "control", 0x79: "local", 0x7A: "visitante", 0x7B: "tarjeta"}

FISICA = [  # nombre, VA (WE9LE), valor vanilla
    ("ball-player.proximity",       0x0ACFB80, 256),
    ("ball.gravity",                0x0ADF074, 188),
    ("ball.global-bounce-stick",    0x0ADF078, -28),
    ("ball.spin-termination-speed", 0x0AEC418, -376),
    ("ball.bounce-stick-frequency", 0x0AEC420, -0.00390625),
    ("ball.topspin",                0x3B695B8, 4551266),
    ("ball.air-resistance",         0x3B695C0, 1400000),
    ("ball.touch-move-rate",        0x0AEC40C, 0.003472222248),
    ("ball.retardation-rate",       0x0AEC410, 0.01041666698),
    ("player.anim-speed",           0x0AEC42C, 0.0009765625),
]
FISICA_WE9 = {  # misma fisica en we9.exe (nocd), mapeada por contexto de bytes
    "ball-player.proximity": 0x0ACFA10, "ball.gravity": 0x0ADF8C4,
    "ball.global-bounce-stick": 0x0ADF8C8, "ball.spin-termination-speed": 0x0AEB020,
    "ball.bounce-stick-frequency": 0x0AEB028, "ball.topspin": 0x3BE1A78,
    "ball.air-resistance": 0x3BE1A80, "ball.touch-move-rate": 0x0AEB014,
    "ball.retardation-rate": 0x0AEB018, "player.anim-speed": 0x0AEB034,
}

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
u32 = ctypes.WinDLL("user32")
PROCESS_VM_READ, PROCESS_QUERY_INFORMATION = 0x0010, 0x0400


class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wt.DWORD),
                ("cntThreads", wt.DWORD), ("th32ParentProcessID", wt.DWORD),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
                ("szExeFile", ctypes.c_char * 260)]


def buscar_pid(nombre):
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)
    e = PROCESSENTRY32(); e.dwSize = ctypes.sizeof(e)
    ok = k32.Process32First(snap, ctypes.byref(e))
    while ok:
        if e.szExeFile.decode(errors="ignore").lower() == nombre.lower():
            k32.CloseHandle(snap); return e.th32ProcessID
        ok = k32.Process32Next(snap, ctypes.byref(e))
    k32.CloseHandle(snap)
    return None


def abrir():
    pid = buscar_pid(PROCESO)
    if not pid:
        sys.exit(f"No encuentro {PROCESO} corriendo. Abri el juego primero.")
    h = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not h:
        sys.exit("No pude abrir el proceso (proba ejecutar la consola como administrador).")
    return h


def leer(h, va, n):
    """Lee n bytes; las paginas ilegibles quedan en cero."""
    out = bytearray(n); paso = 0x10000; leido = ctypes.c_size_t()
    for off in range(0, n, paso):
        m = min(paso, n - off); buf = ctypes.create_string_buffer(m)
        if k32.ReadProcessMemory(h, ctypes.c_void_p(va + off), buf, m, ctypes.byref(leido)):
            out[off:off + m] = buf.raw[:m]
    return bytes(out)


def verificar():
    global PROCESO
    fisica = FISICA
    if not buscar_pid(PROCESO) and buscar_pid("we9.exe"):  # WE9 (no LE): mismas fisicas, otras VA
        PROCESO = "we9.exe"
        fisica = [(n, FISICA_WE9[n], van) for n, _, van in FISICA]
    h = abrir()
    print(f"[{PROCESO}]\n{'parametro':30} {'en el juego':>16} {'vanilla':>16}")
    for nombre, va, van in fisica:
        b = leer(h, va, 4)
        v = struct.unpack("<f", b)[0]
        marca = "" if abs(v - van) <= abs(van) * 1e-6 else "  <- modificado"
        print(f"{nombre:30} {v:16.10g} {van:16.10g}{marca}")
    k32.CloseHandle(h)


def grabar():
    import winsound
    h = abrir()
    carpeta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sesiones",
                           time.strftime("%Y%m%d_%H%M%S"))
    os.makedirs(carpeta)
    indice = {"regiones": REGIONES, "fotos": []}
    print(f"Grabando en {carpeta}\nF9 control | F10 falta LOCAL | F11 falta VISITANTE | F12 tarjeta | Ctrl+C sale")
    previo = {k: False for k in TECLAS}
    try:
        while True:
            for vk, etiqueta in TECLAS.items():
                abajo = bool(u32.GetAsyncKeyState(vk) & 0x8000)
                if abajo and not previo[vk]:
                    n = len(indice["fotos"])
                    datos = b"".join(leer(h, va, tam) for va, tam in REGIONES)
                    nombre = f"{n:03d}_{etiqueta}.bin.z"
                    with open(os.path.join(carpeta, nombre), "wb") as f:
                        f.write(zlib.compress(datos, 1))
                    indice["fotos"].append({"archivo": nombre, "etiqueta": etiqueta, "hora": time.time()})
                    with open(os.path.join(carpeta, "indice.json"), "w") as f:
                        json.dump(indice, f, indent=1)
                    print(f"  foto {n:03d}: {etiqueta}")
                    winsound.Beep(1200 if etiqueta == "control" else 800, 120)
                previo[vk] = abajo
            time.sleep(0.03)
    except KeyboardInterrupt:
        print(f"\nListo: {len(indice['fotos'])} fotos en {carpeta}")
    k32.CloseHandle(h)


def analizar(carpeta, eventos):
    import numpy as np
    with open(os.path.join(carpeta, "indice.json")) as f:
        indice = json.load(f)
    fotos = indice["fotos"]
    if len(fotos) < 3:
        sys.exit("Hacen falta al menos 3 fotos.")
    bases = []  # VA inicial de cada byte del volcado concatenado
    for va, tam in indice["regiones"]:
        bases.append((va, tam))

    def va_de(pos):
        for va, tam in bases:
            if pos < tam: return va + pos
            pos -= tam

    def cargar(i):
        with open(os.path.join(carpeta, fotos[i]["archivo"]), "rb") as f:
            return np.frombuffer(zlib.decompress(f.read()), dtype=np.uint8)

    vistas = {"u8": (np.uint8, 1), "u16": (np.uint16, 2), "u32": (np.uint32, 4)}
    res = {}
    for nombre, (dt, w) in vistas.items():
        ant = cargar(0)
        largo = (len(ant) // w) * w
        ok = None; malos = None; n_ev = 0
        for i in range(1, len(fotos)):
            act = cargar(i)
            a = ant[:largo].view(dt).astype(np.int64); b = act[:largo].view(dt).astype(np.int64)
            d = b - a
            if ok is None:
                ok = np.zeros(len(d), np.int32); malos = np.zeros(len(d), np.int32)
            et = fotos[i]["etiqueta"]
            if et in eventos:
                n_ev += 1; ok += (d == 1); malos += (d != 1)
            elif et == "control":
                malos += (d != 0)
            ant = act
        idx = np.nonzero((ok == n_ev) & (malos == 0))[0] if n_ev else np.array([], int)
        res[nombre] = (idx, w, n_ev)

    # historial de valores de los primeros 40 candidatos de cada vista (cada foto se descomprime una vez)
    elegidos = [(nombre, int(j) * w) for nombre, (idx, w, _) in res.items() for j in idx[:40]]
    hist = {c: [] for c in elegidos}
    for i in range(len(fotos)):
        datos = cargar(i)
        for nombre, pos in elegidos:
            dt, w = vistas[nombre]
            hist[(nombre, pos)].append(int(datos[pos:pos + w].view(dt)[0]))

    print(f"Eventos buscados: {eventos}")
    print("Etiquetas: " + " ".join(f["etiqueta"][0].upper() for f in fotos))
    for nombre, (idx, w, n_ev) in res.items():
        print(f"\n[{nombre}] {len(idx)} candidatos que suben +1 en los {n_ev} eventos y no cambian en controles")
        for j in idx[:40]:
            pos = int(j) * w
            print(f"  VA {va_de(pos):08x}  valores: {hist[(nombre, pos)]}")


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    if modo == "verificar":
        verificar()
    elif modo == "grabar":
        grabar()
    elif modo == "analizar" and len(sys.argv) >= 3:
        ev = ["local", "visitante"]
        if "--eventos" in sys.argv:
            ev = sys.argv[sys.argv.index("--eventos") + 1].split(",")
        analizar(sys.argv[2], ev)
    else:
        print(__doc__)
