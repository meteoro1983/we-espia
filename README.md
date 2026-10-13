# we-espia

Agente "espía" para **Winning Eleven 9, WE9 LIVEWARE EVOLUTION y PES6 (PC)**. Lee la memoria del juego
**en vivo, mientras se juega**: eventos del partido (faltas, pases, tiros, saques…), quién tocó la pelota por última vez
y la fase del partido (en juego, falta, lateral…). Trae también las herramientas de ingeniería inversa con las que se
encontró todo eso y los parches de árbitro permisivo.

La idea es que sea la base de herramientas de la federación: estadísticas por jugador y equipo, un option file
online que se va nutriendo de lo que pasa en los partidos, cartas con bonificaciones, etc.

- **Solo lectura:** el espía no inyecta nada ni modifica el juego. Lee la memoria como lo hace Cheat Engine.
- **Sin direcciones fijas:** busca cada rutina por su **firma** (patrón de bytes) en la memoria del juego ya
  arrancado. Así anda con el exe original, el crack, Kingsley V5.5 o kitserver, aunque el exe en disco esté cifrado.

## Estado

| | WE9LE | WE9 | PES6 |
|---|---|---|---|
| Firmas (lista de eventos, último toque, fase) | ✅ verificadas (3 exes) | ✅ verificadas (nocd y Kingsley) | ⚠️ sin probar: mismo motor, correr `diagnostico` |
| Lista de eventos en vivo | ✅ usada en partidos reales | 🟡 misma rutina, sin partido de prueba | ⚠️ |
| Parches de árbitro | ✅ probados en partido | 🟡 armado, sin partido de prueba | ❌ (direcciones fijas de WE9/WE9LE) |

Códigos de evento confirmados: **falta (3)** y **saque inicial (1)**. Pase, tiro, tiro libre y lateral están
deducidos y hay que confirmarlos (ver [docs/FORMATO_EVENTOS.md](docs/FORMATO_EVENTOS.md)).

## Uso rápido

Requiere Windows y Python 3 (el espía no tiene dependencias). Jugar en **ventana** facilita todo.

```bat
:: con el juego abierto (en un partido o en el menú)
python espia\espia.py diagnostico

:: espiar el partido y guardar los eventos (un JSON por línea)
python espia\espia.py vivo --jsonl partido.jsonl
python espia\espia.py vivo --toques          :: además, cada cambio de "último que tocó la pelota"

:: probar las firmas en un exe sin abrir el juego (solo exes sin cifrar: crack / nocd)
python espia\espia.py diagnostico --exe "C:\...\WE9LEK.exe"

:: con un partido guardado: estadísticas por jugador
python ejemplos\resumen_jsonl.py partido.jsonl
```

Ejemplo de salida de `vivo`:

```
[ 12'] falta            visitante jug  5  (03 85 0c 80)
  fase   -> 6 (falta_tiro_libre)
[ 12'] tiro_libre       local     jug  5  (08 05 0c 00)
[ 13'] pase             visitante jug  2 -> 7  (0b 82 0d 00 00 87 00 00)
```

Si hace falta, abrí la consola como administrador. Algunos antivirus desconfían de cualquier programa que lea la
memoria de otro proceso.

## Contenido

| Carpeta | Qué es |
|---|---|
| `espia/espia.py` | El espía: localiza por firma, lee la lista de eventos, la fase y el último toque, y emite JSONL |
| `ejemplos/` | Cómo consumir el JSONL (estadísticas por jugador) |
| `herramientas/` | Kit de ingeniería inversa sin Cheat Engine: `memscan.py` (buscar valores), `vigilar.py` ("qué escribe/lee/ejecuta esta dirección", con breakpoint por hardware), `we9le_registro.py` (fotos de memoria con F9–F12 + análisis), `ctx.py` (desensamblar), `xrefs.py` (quién usa una dirección), `diffexe.py` (diff de dos exes) |
| `parches/arbitro/` | Árbitro permisivo para WE9/WE9LE: por porcentaje, selectivo o por zonas (escriben un exe nuevo y nunca pisan el original) |
| `docs/` | Mapa de memoria (WE9LE + equivalencias WE9), formato de eventos, cómo portar a otro exe, logs de las cacerías |

`herramientas/` necesita `pip install -r requirements.txt` (numpy, capstone, pefile).

## Lo que todavía no está (para seguir)

- **Identidad del jugador:** el evento trae `equipo` + `jugador` (índice 0–10 del que está en cancha), no el ID del
  option file. Falta mapear la alineación en memoria → ID del jugador. Es lo primero que hace falta para
  estadísticas persistentes y cartas.
- Marcador, nombres de equipos y reloj exacto: no mapeados (el minuto viene en cada evento).
- Confirmar los códigos marcados con `?`.

En [docs/PORTAR.md](docs/PORTAR.md) está el método para mapear cosas nuevas y para portar una firma que no aparece.

## Aviso

No incluye ningún exe ni archivo de Konami. Cada uno usa su copia del juego. Proyecto de fans, sin fines comerciales.
Licencia MIT.
