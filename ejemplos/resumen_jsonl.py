"""
resumen_jsonl.py - ejemplo de consumo: estadisticas por jugador a partir de un partido grabado con
    python espia\\espia.py vivo --jsonl partido.jsonl

uso: python resumen_jsonl.py partido.jsonl [otro.jsonl ...]
"""
import json, sys
from collections import Counter

conteo = Counter()
for ruta in sys.argv[1:]:
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            ev = json.loads(linea)
            if "codigo" in ev:  # eventos de la lista (no fase/toque)
                conteo[(ev["equipo"], ev["jugador"], ev["tipo"])] += 1
                if "receptor" in ev:
                    conteo[(ev["equipo"], ev["receptor"], "pase_recibido")] += 1

if not conteo:
    sys.exit(__doc__)
tipos = sorted({t for _, _, t in conteo})
print(f"{'equipo':10} {'jug':>3} " + " ".join(f"{t[:12]:>12}" for t in tipos))
for eq, jug in sorted({(e, j) for e, j, _ in conteo}):
    print(f"{eq:10} {jug:3} " + " ".join(f"{conteo[(eq, jug, t)]:12}" for t in tipos))
