"""probar.py - comprueba que optionfile.py lee y reescribe tus option files sin cambiar un byte.
uso: python probar.py <option file> [<option file> ...]"""
import sys
from optionfile import OptionFile

for ruta in sys.argv[1:]:
    of = OptionFile.abrir(ruta)
    orig, out = open(ruta, "rb").read(), of.bytes_cifrados()
    dif = sum(a != b for a, b in zip(orig, out))
    con = sum(1 for i in of.indices() if of.nombre(i))
    print(f"{ruta}: {of.variante}, {con} jugadores, ida y vuelta {'OK' if dif == 0 else f'{dif} bytes distintos (banderas de guardado?)'}")
