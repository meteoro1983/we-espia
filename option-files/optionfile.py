#!/usr/bin/env python3
"""
optionfile.py - leer y escribir option files de WE9 / WE9LE / PES5 y PES6 (PC), sin editores.

Como libreria:
    from optionfile import OptionFile
    of = OptionFile.abrir("KONAMI-WIN32WE9KOPT")
    j = of.jugador(1234)                  # dict: nombre, camiseta, todos los campos (valor mostrado)
    of.poner(1234, "SHOT POWER", 99)      # valor mostrado (altura en cm, edad en anios, nacionalidad por nombre)
    of.guardar("salida/KONAMI-WIN32WE9KOPT")   # cifra y recalcula checksums; nunca pisa el original

Por consola:
    python optionfile.py info      <OF>
    python optionfile.py jugador   <OF> <indice | nombre>
    python optionfile.py equipo    <OF> <indice de equipo>
    python optionfile.py exportar  <OF> salida.json          (todos los jugadores y plantillas)
    python optionfile.py poner     <OF> <indice> <campo> <valor> --salida <carpeta>

Formato completo y origen de cada dato: docs/OPTION_FILES.md.
Solo biblioteca estandar.
"""
import argparse, hashlib, json, os, struct, sys, unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(AQUI, "datos", "tablas.json"), encoding="utf-8") as _f:
    TAB = json.load(_f)
for _k in ("keypc", "key5", "key6"):  # huellas: las tablas de cifrado tienen que estar intactas
    if hashlib.sha256(json.dumps(TAB[_k]).encode()).hexdigest()[:16] != TAB["fp"][_k]:
        raise SystemExit(f"datos/tablas.json danado ({_k}).")

FIRST_EDIT = 32768
JUEGOS = {
    # "pes5" = WE9, WE9LE y PES5 (mismo formato; WE9 y WE9LE solo difieren en los primeros 9500 bytes)
    "pes5": dict(length=1250304, keylen=367, style=5, key=TAB["key5"],
                 block=[12, 5144, 9508, 14044, 36872, 657712, 803608, 822940, 969192, 1228568],
                 size=[4948, 1232, 4520, 22816, 620000, 145880, 19320, 146240, 259364, 21016],
                 c1=1815549477, c2=0x6C371625, base=36872, baseE=14044, regulares=5000,
                 n23=74, slot23=664054, slot32=667458, num23=657712, num32=659414, equipos=212,
                 clubes=(803608, 140), banderas=(45, 46, 5958, 5959),
                 campos={c: tuple(v) for c, v in TAB["T5"].items()},
                 nac={int(k): v for k, v in TAB["NAT5"].items()}, selecciones=TAB["NAC5"], primer_club=74),
    "pes6": dict(length=1191936, keylen=446, style=6, key=TAB["key6"],
                 block=[12, 5144, 9544, 14288, 37116, 657956, 751472, 763804, 911144, 1170520],
                 size=[4844, 1268, 4730, 22816, 620000, 93501, 12320, 147328, 259364, 21032],
                 c1=0x7AB3684C, c2=0x7AB3684C, base=37116, baseE=14288, regulares=4784,
                 n23=73, slot23=664372, slot32=667730, num23=657956, num32=659635, equipos=213,
                 clubes=(751472, 88), banderas=(45, 46, 5938, 5939),
                 campos={c: tuple(v) for c, v in TAB["T6"].items()},
                 nac={int(k): v for k, v in TAB["NAT6"].items()}, selecciones=TAB["NAC6"], primer_club=73),
}
JUEGOS["pes6"]["campos"].update({k: tuple(v) for k, v in TAB["S6"].items()})  # apariencia conocida de PES6
JUEGOS["pes6"]["campos"]["abilityEdited"] = (0, 40, 4, 1)
JUEGOS["pes5"]["campos"].update({"hair": (0, 45, 0, 0x7FF), "faceType": (0, 55, 0, 3), "skin": (0, 43, 1, 3)})
KEYPC = bytes(TAB["keypc"])
NOMBRES_ARCHIVO = {"KONAMI-WIN32WE9UOPT": "WE9", "KONAMI-WIN32WE9KOPT": "WE9LE",
                   "KONAMI-WIN32PES5OPT": "PES5", "KONAMI-WIN32PES6OPT": "PES6"}


class ErrorOF(Exception):
    pass


def _xor(buf):
    return bytearray(b ^ KEYPC[i & 255] for i, b in enumerate(buf))


def _palabras(buf, ini, tam):
    n = tam // 4  # ojo: el bloque 5 de PES6 mide 93501 (no multiplo de 4)
    return list(struct.unpack_from("<%dI" % n, buf, ini)), n


def _checksums(buf, g):
    return [sum(_palabras(buf, g["block"][i], g["size"][i])[0]) & 0xFFFFFFFF for i in range(10)]


def _descifrar(buf, g):
    key, kl, c1, c2 = g["key"], g["keylen"], g["c1"], g["c2"]
    for i in range(1, 10):  # el bloque 0 va en claro
        w, n = _palabras(buf, g["block"][i], g["size"][i])
        for k in range(n):
            w[k] = (((w[k] - key[k % kl]) + c1) & 0xFFFFFFFF) ^ c2
        struct.pack_into("<%dI" % n, buf, g["block"][i], *w)


def _cifrar(buf, g):
    key, kl, c1, c2 = g["key"], g["keylen"], g["c1"], g["c2"]
    resta = c1 if g["style"] == 5 else c2
    for i in range(1, 10):
        w, n = _palabras(buf, g["block"][i], g["size"][i])
        for k in range(n):
            w[k] = (key[k % kl] + ((w[k] ^ c2) - resta)) & 0xFFFFFFFF
        struct.pack_into("<%dI" % n, buf, g["block"][i], *w)


def _norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return "".join(ch for ch in s if ch.isalnum())


class OptionFile:
    def __init__(self, buf, juego, variante, ruta=None):
        self.buf, self.juego, self.variante, self.ruta = buf, juego, variante, ruta
        self.g = JUEGOS[juego]

    # ---------- carga / guardado
    @classmethod
    def abrir(cls, ruta, forzar=False):
        datos = open(ruta, "rb").read()
        juego = next((j for j, g in JUEGOS.items() if g["length"] == len(datos)), None)
        if not juego:
            raise ErrorOF(f"Tamano {len(datos)}: no es un option file de PC de WE9/WE9LE/PES5 ni de PES6.")
        g = JUEGOS[juego]
        buf = _xor(datos)
        guardados = [struct.unpack_from("<I", buf, g["block"][i] - 8)[0] for i in range(10)]
        if _checksums(buf, g) != guardados and not forzar:
            raise ErrorOF("Checksums invalidos: archivo danado o de otro juego.")
        _descifrar(buf, g)
        variante = NOMBRES_ARCHIVO.get(os.path.basename(ruta).upper(), "PES6" if juego == "pes6" else "WE9/WE9LE/PES5")
        return cls(buf, juego, variante, ruta)

    def bytes_cifrados(self):
        b = bytearray(self.buf)
        for p in self.g["banderas"]:  # como hacen los editores al guardar
            b[p] = 1
        _cifrar(b, self.g)
        for i, c in enumerate(_checksums(b, self.g)):
            struct.pack_into("<I", b, self.g["block"][i] - 8, c)
        return bytes(_xor(b))

    def guardar(self, ruta):
        if self.ruta and os.path.abspath(ruta) == os.path.abspath(self.ruta):
            raise ErrorOF("No piso el archivo original: elegi otra ruta.")
        datos = self.bytes_cifrados()
        OptionFile(_descifrado(datos, self.g), self.juego, self.variante)  # relectura: valida checksums
        os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)
        with open(ruta, "wb") as f:
            f.write(datos)

    # ---------- jugadores
    def rec(self, idx):
        return self.g["base"] + idx * 124 if idx < FIRST_EDIT else self.g["baseE"] + (idx - FIRST_EDIT) * 124

    def indices(self):
        return list(range(1, self.g["regulares"])) + list(range(FIRST_EDIT, FIRST_EDIT + 184))

    def crudo(self, idx, campo):
        _, off, sh, mask = self.g["campos"][campo]
        a = self.rec(idx) + 48 + off
        return (((self.buf[a] << 8) | self.buf[a - 1]) >> sh) & mask

    def poner_crudo(self, idx, campo, v):
        _, off, sh, mask = self.g["campos"][campo]
        a = self.rec(idx) + 48 + off
        if not 0 <= v <= mask:
            raise ErrorOF(f"{campo}: {v} fuera de rango (0..{mask} crudo).")
        old = ((self.buf[a] << 8) | self.buf[a - 1]) & (0xFFFF & ~(mask << sh))
        v = (v << sh) | old
        self.buf[a - 1], self.buf[a] = v & 0xFF, (v >> 8) & 0xFF

    def valor(self, idx, campo):
        tipo = self.g["campos"][campo][0]
        v = self.crudo(idx, campo)
        if tipo == 1: return v + 148          # altura en cm
        if tipo == 2: return v + 15           # edad
        if tipo == 3: return self.g["nac"].get(v, f"?{v}")
        if tipo == 5: return v + 1            # escalas 1..8
        return v

    def poner(self, idx, campo, valor):
        if campo not in self.g["campos"]:
            raise ErrorOF(f"Campo desconocido: {campo}. Ver 'jugador' para la lista.")
        tipo = self.g["campos"][campo][0]
        if tipo == 3:
            inv = {_norm(n): k for k, n in self.g["nac"].items()}
            if _norm(str(valor)) not in inv:
                raise ErrorOF(f"Nacionalidad desconocida en este juego: {valor}")
            v = inv[_norm(str(valor))]
        else:
            v = int(valor) - {1: 148, 2: 15, 5: 1}.get(tipo, 0)
        self.poner_crudo(idx, campo, v)
        if "abilityEdited" in self.g["campos"]:  # PES6: marcar como editado, como hacen los editores
            self.poner_crudo(idx, "abilityEdited", 1)

    def nombre(self, idx):
        raw = bytes(self.buf[self.rec(idx):self.rec(idx) + 32]); i = 0
        while i < 30 and not (raw[i] == 0 and raw[i + 1] == 0):
            i += 2
        return raw[:i].decode("utf-16le", "replace")

    def camiseta(self, idx):
        a = self.rec(idx) + 32
        return bytes(self.buf[a:a + 16]).split(b"\0")[0].decode("ascii", "replace")

    def jugador(self, idx):
        d = {"indice": idx, "nombre": self.nombre(idx), "camiseta": self.camiseta(idx)}
        d.update({c: self.valor(idx, c) for c in self.g["campos"]})
        return d

    def buscar(self, texto):
        t = _norm(texto)
        return [i for i in self.indices() if t and t in _norm(self.nombre(i))]

    # ---------- equipos
    def nombre_equipo(self, t):
        g = self.g
        if t < 57:
            return g["selecciones"][t]
        if t >= g["primer_club"]:
            a = g["clubes"][0] + g["clubes"][1] * (t - g["primer_club"])
            raw = bytes(self.buf[a:a + 49]); i = raw.find(0)
            return (raw if i < 0 else raw[:i]).decode("utf-8", "replace")
        return f"equipo {t} (clasico / Japon / editado)"

    def plantilla(self, t):
        """[(indice_jugador, dorsal)] en el orden EFECTIVO (en WE9 se aplica el orden permutado)."""
        g = self.g
        if t < g["n23"]:
            sl, nm, n = g["slot23"] + t * 46, g["num23"] + t * 23, 23
        else:
            c = t - g["n23"]; sl, nm, n = g["slot32"] + c * 64, g["num32"] + c * 32, 32
        ids = [self.buf[sl + 2 * k] | (self.buf[sl + 2 * k + 1] << 8) for k in range(n)]
        nums = [self.buf[nm + k] for k in range(n)]
        if self.juego == "pes5" and (t < 64 or 74 <= t < 212):
            j = t if t < 64 else t - 10
            a = 670512 + 628 * j + 6232
            orden = list(self.buf[a:a + 32])
            ids = [ids[o] if o < n else 0 for o in orden[:n]]
            nums = [nums[o] if o < n else 255 for o in orden[:n]]
        return [(i, d) for i, d in zip(ids, nums)]


def _descifrado(datos, g):
    buf = _xor(datos)
    guardados = [struct.unpack_from("<I", buf, g["block"][i] - 8)[0] for i in range(10)]
    if _checksums(buf, g) != guardados:
        raise ErrorOF("La relectura del archivo guardado no valida: no se escribio nada.")
    _descifrar(buf, g)
    return buf


# ---------------------------------------------------------------- consola
def _main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("info"); s.add_argument("of")
    s = sp.add_parser("jugador"); s.add_argument("of"); s.add_argument("quien")
    s = sp.add_parser("equipo"); s.add_argument("of"); s.add_argument("t", type=int)
    s = sp.add_parser("exportar"); s.add_argument("of"); s.add_argument("salida")
    s = sp.add_parser("poner"); s.add_argument("of"); s.add_argument("idx", type=int)
    s.add_argument("campo"); s.add_argument("valor"); s.add_argument("--salida", required=True)
    a = p.parse_args()
    try:
        of = OptionFile.abrir(a.of)
        if a.cmd == "info":
            con = [i for i in of.indices() if of.nombre(i)]
            print(f"{a.of}\n  juego: {of.variante} (formato {of.juego}), checksums OK")
            print(f"  jugadores con nombre: {len(con)}  |  equipos: {of.g['equipos']}")
        elif a.cmd == "jugador":
            idxs = [int(a.quien)] if a.quien.isdigit() else of.buscar(a.quien)
            for i in idxs[:20]:
                print(json.dumps(of.jugador(i), ensure_ascii=False, indent=1))
            if not idxs:
                print("No encontrado.")
        elif a.cmd == "equipo":
            print(f"[{a.t}] {of.nombre_equipo(a.t)}")
            for k, (i, d) in enumerate(of.plantilla(a.t)):
                if i:
                    print(f"  {k:2}  #{d:<3} {i:5}  {of.nombre(i)}")
        elif a.cmd == "exportar":
            datos = {"juego": of.variante, "formato": of.juego,
                     "jugadores": [of.jugador(i) for i in of.indices() if of.nombre(i)],
                     "equipos": [{"indice": t, "nombre": of.nombre_equipo(t),
                                  "plantilla": [{"jugador": i, "dorsal": d} for i, d in of.plantilla(t) if i]}
                                 for t in range(of.g["equipos"])]}
            with open(a.salida, "w", encoding="utf-8") as f:
                json.dump(datos, f, ensure_ascii=False, indent=1)
            print(f"{len(datos['jugadores'])} jugadores y {len(datos['equipos'])} equipos -> {a.salida}")
        elif a.cmd == "poner":
            antes = of.valor(a.idx, a.campo)
            of.poner(a.idx, a.campo, a.valor)
            destino = os.path.join(a.salida, os.path.basename(a.of))
            of.guardar(destino)
            print(f"{of.nombre(a.idx)}: {a.campo} {antes} -> {of.valor(a.idx, a.campo)}  ({destino})")
    except ErrorOF as e:
        sys.exit(f"Error: {e}")


if __name__ == "__main__":
    _main()
