# CLAUDE.md — we-espia

Contexto para Claude (o cualquier agente) que trabaje en este repo.

## Qué es
Lector en vivo de la memoria de WE9 / WE9 LIVEWARE EVOLUTION / PES6 (PC, 32 bits, D3D8) más un kit de ingeniería
inversa. Es para una federación de amigos que juega con option files propios. Objetivos: estadísticas de jugadores y
equipos, un option file online que se nutre de los partidos y cartas con bonificaciones.
El código y los textos están en español rioplatense.

Dos mitades:
- **En vivo** (`espia/`): memoria del juego mientras se juega.
- **En disco** (`option-files/`): leer y escribir option files (`optionfile.py`). Formato en `docs/OPTION_FILES.md`.
  Viene de los conversores públicos `pes-we9-a-pes6` y `pes-we9-we9le`, que ya se probaron en el juego.

## Reglas
- `espia/` es **solo lectura** (`OpenProcess` con VM_READ|QUERY_INFORMATION). No escribir memoria del juego desde
  el espía. Si algún día se necesita, que sea en otra herramienta y de forma explícita.
- **No hardcodear direcciones** en el espía: cada dato nuevo entra como firma en `FIRMAS` + `derivar` y se verifica
  en los exes disponibles (`diagnostico --exe`) y en vivo.
- Marcar lo deducido como no confirmado (`"?"` en `CODIGOS`) hasta verlo en un partido real. El JSONL guarda `crudo`
  para reinterpretar después.
- Option files: **nunca copiar registros de jugador en bruto entre WE9 y PES6** (mismos campos, distintos bits).
  Siempre campo a campo, con las tablas `T5`/`T6`. Nacionalidades por nombre. En WE9 aplicar el orden permutado de
  la plantilla. Nunca pisar el archivo de entrada. Después de escribir, releer y validar los checksums
  (`optionfile.py` ya lo hace).
- No subir exes, ISOs, option files ni volcados de memoria de Konami (`.gitignore` ya lo cubre).
- `espia.py` usa solo la biblioteca estándar (ctypes). `herramientas/` usa numpy, capstone y pefile.

## Hechos verificados
- Firmas `lista`, `toque` y `fase` dan una sola dirección en: WE9LEK crack limpio, WE9LEK Kingsley V5.5, WE9LEK
  evoweb, we9.exe nocd y we9 Kingsley V5.5. En WE9LE coinciden con lo hallado en vivo en 2026-10-08.
- PES6 **no probado**: su exe en disco está cifrado (SecuROM) y la PC de origen no tenía la clave de registro
  `KONAMI\PES6`. Probar con `diagnostico` con el juego abierto.
- Partidos reales solo en WE9LE (lista de eventos, faltas, árbitro). WE9: firmas OK, sin partido de prueba.

- `optionfile.py`: ida y vuelta idéntica byte a byte en option files reales de WE9LE, PES5 y PES6. `poner` y
  `exportar` probados.

## Próximos pasos sugeridos
1. Confirmar en PES6 y WE9 en vivo (`diagnostico` + `vivo` durante un partido).
2. Alineación en cancha → ID del jugador en el option file (hipótesis: índice 0–10 = orden de la plantilla
   efectiva; ver `docs/OPTION_FILES.md` §8) (estructuras de jugador `0x3B573C0` en WE9LE,
   0x290 bytes c/u, +0x40 equipo, +0x3F dorsal/índice). Sin esto no hay stats persistentes.
3. Marcador y equipos en memoria.
4. Confirmar códigos `?` leyendo `0x6A5A10` (conversor a tipos de pantalla) en WE9LE.

Método y herramientas: `docs/PORTAR.md`. Mapa de memoria completo: `docs/MAPA_MEMORIA_WE9LE.md`.
Logs de las cacerías con `vigilar.py`: `docs/logs-caza/`.
