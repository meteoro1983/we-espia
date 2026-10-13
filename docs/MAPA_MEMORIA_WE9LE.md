# Análisis IA / árbitros — WE9 (2026-10-08)

Exes comparados: `WE9-nocd.rar` (WE9.exe limpio, 2006) vs
Kingsley813 `we9 - Gameplay Improvement v5.5 BETA.exe` (mismo tamaño, 130 bloques distintos).
Herramientas en `herramientas\`: `diffexe.py` (diff por VA), `xrefs.py` (quién usa una dirección), `ctx.py` (desensambla alrededor).

## Unidades de la cancha (deducido)
**256 unidades = 1 metro.** Media largo = 13465 (52,6 m), media ancho = 8729 (34,1 m); 13465/8729 = 1,543 = 105/68.
Área grande: media ancho 5160 (20,16 m exacto). 2344 = 9,15 m (distancia de barrera / círculo central).

## Qué cambió Kingsley en WE9 (todo valores, nada de lógica nueva)
| VA (WE9) | vanilla → V5.5 | metros | usos en código | lectura |
|---|---|---|---|---|
| 0xADD46C | 8729 → 10729 | 34,1 → 41,9 | 204 | media ancho de cancha (constante compartida) |
| 0xAE25C8 | -8729 → -9729 | | 31 | idem, lado negativo |
| 0xAE23E0 | -13465 → -13350 | 52,6 → 52,1 | 157 | línea de fondo |
| 0xAE23D8 | -700 → -250 | 2,7 → 1 | 2 | ? |
| 0xAEB318 | 8217 → 6050 | 32,1 → 23,6 | 48 | franja lateral (banda) |
| 0xADD3F8 | -6732,5 → -5200,5 | 26,3 → 20,3 | 23 | ? |
| 0xADD428 / 0xADD434 | 5160 / -5160 → 1000 / -3160 | | 3 + 3 | **clasificador de zonas laterales** (fn 0x4EFDC0: franjas -8217/-5160/-2344/2344/5160) → "menos juego por las bandas" |
| 0xADD3C8 | 1024 → 512 | 4 → 2 | 87 | distancia corta (marca/presión?) |
| 0xAEC768 | 3072 → 1100 | 12 → 4,3 | 8 | ? |
| 0xAD4034 | 0.00390625 → 0.00405 | | 48 | factor |
| 0xAD0C9C | 24000 → 10000 | | 0 directos | (¿niebla?) |
| 0x8E67A1 (código) | push 1430 → 1050 | | | parámetro de función 0x5B4170 (¿niebla?) |
| 0x7B63A9/B9 (código) | topspin / air-res | | | física (ya conocida) |
| 0xAEB014.. / 0xADF8C4 | física de pelota | | | ya mapeada |
| 0x402xxx, 0x59C1xx | resolución interna / render | | | gráficos |
| 0x8316FE + 0xACDFE0 | llamada a kload.dll | | | kitserver |

**Conclusión:** Kingsley cambió *constantes compartidas* (el compilador usa un solo 8729 para 204 lugares), o sea cambios a ciegas que afectan muchas rutinas a la vez.
**Nuestro enfoque mejor:** identificar la rutina concreta (como 0x4EFDC0) y redirigir solo esa instrucción a una constante nueva propia (code cave) → cambios quirúrgicos.

## Árbitros
No hay constante conocida. Plan con Cheat Engine: buscar el contador de faltas por valor exacto (lo muestra Estadísticas del partido) → "Find out what writes to this address" → retroceder hasta la decisión de cobrar → parche.

## WE7 (sin prioridad)
`D:\...\Descargas\winning-eleven-7-international_202304\Winning Eleven 7 International.iso` = WE7 International **para PC** (versión mejorada de PES3).
**Kitserver 3.1.0 ya soporta WE7** (kitserver.mapote.com/files) → no hace falta uno propio. Recomiendan dgVoodoo2 (D3D8.dll).

## Herramientas propias (en vez de Cheat Engine)
El instalador oficial de Cheat Engine 7.7 viene envuelto por "Plooto Inc" (adware, nombre con homoglifos) → descartado sin ejecutar.
- `herramientas\memscan.py` — búsqueda de valores estilo CE: `nuevo <valor>`, `filtrar <valor>`, `cambio subio|bajo|igual|distinto`, `ver`, `leer <va>`. Opciones `--proc WE9LEK.exe` (default) / `--pid`, `--tipo i32|i16|u8|f32`, `--sesion`.
- `herramientas\vigilar.py <va>` — "Find out what writes": depurador con breakpoint por hardware; `--modo escribe|accede|ejecuta`, `--largo`, `--segundos`, `--max`. Loguea instrucción + registros y se desengancha sin cerrar el juego. Log en `vigilar_<va>.log`.
- Probadas (2026-10-08) contra un proceso de 32 bits de prueba: memscan encontró el contador en 2 pasadas; vigilar marcó la instrucción exacta (`mov dword ptr [ecx], eax`) y el proceso siguió vivo.
- Respaldo GUI: x64dbg portable en `D:\Programs\_herramientas_re\x64dbg\release\x96dbg.exe` (usar x32dbg).

## Procedimiento próxima sesión (WE9LE en ventana, en esta PC)
1. Matías arranca WE9LE en ventana (disco MAMEDISK conectado), partido amistoso.
2. Contador de faltas: en Estadísticas ver faltas del equipo (ej. 0) → `memscan nuevo 0 --tipo u8` (probar también i16/i32) → tras cada falta `filtrar <n>`; si se pierde, `cambio subio` / `cambio igual` entre faltas.
3. `vigilar <va> --modo escribe` → próxima falta → instrucción que suma → `ctx.py` sobre el exe limpio de WE9LE para retroceder hasta la decisión de cobrar.
4. IA: `--modo ejecuta` en la rutina de interés (ej. 0x4EFDC0 en WE9; buscar su equivalente en WE9LE por bytes) para ver quién la llama y con qué valores.
5. Lo hallado en WE9LE se traslada a WE9 buscando la misma secuencia de bytes (como con la física: misma lógica, direcciones distintas).

## 2026-10-08 noche — caza en vivo de faltas (WE9LE, exe K55 = mismas direcciones que el limpio)
- **No hay contador de faltas por equipo**: la tabla de estadísticas (파울) se arma contando eventos del **registro de jugadas** (memscan por valor 8 + vecinos sin resultado; registrador F9/F10 solo dio flags transitorios 0→1→0 en 0x3B58xxx).
- **Registro de jugadas (WE9LE)**: puntero en `[0x38C5B84]` → struct `{ i16 cantidad; ...; +4: puntero a entradas }`, entradas de **4 bytes** `[b0, b1, b2, b3]` (b3 = minuto; b0..b2 = tipo/equipo/jugador, falta decodificar). Getters 0x9CD340 (cantidad), 0x9CD350/370/390/3B0 (bytes 0..3). Puntero asignado en 0x9CED2E / 0x9CF485 / 0x9CF4F2.
- Copia para el resumen: 0x9CC1BA copia el registro a `0x38C48D5` (cantidad u8) + entradas de 3 bytes desde `0x38C48D6` (minuto, ...); lo lee la pantalla en 0x9DC6D0.
- **Próximo paso**: con el juego corriendo, leer `[0x38C5B84]` → buffer de entradas → `vigilar --modo escribe` sobre el próximo slot vacío (cantidad*4) → la próxima falta da la instrucción que la anota → subir por la pila hasta la decisión de cobrar (árbitro). Después buscar la misma rutina en WE9 por bytes.
- Exe limpio de WE9LE recuperado: `exe_referencia\WE9LEK_limpio_crack.exe` (MD5 46e03250…). Idioma: text_k/lang_k del registro NO pasan a inglés (no hay textos en inglés en dat\); se juega en coreano y se leen estadísticas por captura de ventana (PrintWindow).

### Segunda sesión en vivo (misma noche) — LISTA DE EVENTOS EN VIVO hallada
- Lo de `[0x38C5B84]` es una COPIA que se arma recién en el entretiempo/final (0x9CD290 → 0x6A5BF0/0x6A5C50) y se libera al reanudar. No sirve para vigilar en juego.
- **Lista en vivo**: base = `[0xF773EC] + 0x14 + 0x12D8` → en la partida fue **0x3B0D530** (en .data, fija). Registros de largo variable, terminados en byte 0. Recorrido: 0x7BD880 (primero) / 0x7BD890 (siguiente): códigos 0x0B–0x10 = 8 bytes; 0x11–0x1A = 4 + 4*byte[3]; resto = 4 bytes.
- Formato registro corto: `[código, (equipo<<7)|jugador, minuto, flags]`. **Código 3 = FALTA** (flags: 0x80 = falta normal; 0x82/0x10 etc. = con tarjeta/otros; ver conversión 0x6A5A10: 3 → tipo de pantalla 0x25/0x26/0x28/0x29/0x2B según flags). Tras una falta suele venir `08 jj mm 00` (tiro libre). 0x0B = pases/posesión (8 bytes), 0x01 = saque inicial, 0x05/0x06 = laterales/saques?, 0x16/0x18/0x19 = tiros con trayectoria.
- Conversión a lista de pantalla: tipo 0x29 = falta, 0x01 = tiro, 0x1B = córner izq., 0x2C = saque inicial, 0x27 = falta con amarilla (probable).
- Lectores de estadísticas por tipo: funciones 0x7BD940…0x7C10B0 (todas hacen `+0x12D8`), son CONSULTAS, no el escritor.
- **Próximo paso (5 min de juego):** leer el final real de la lista (parsear desde 0x3B0D530 hasta el byte 0) → `vigilar.py <fin> --modo escribe` → en la próxima jugada da la función que AGREGA eventos; buscar quién la llama con código 3 → esa es la rutina de "cobrar falta" → arriba está la decisión del árbitro.
- Script de parseo usado: ver scratchpad de la sesión; lógica = la de 0x7BD890.

### ÁRBITRO RESUELTO (2026-10-08, tercera tanda en vivo) — `ARBITRO-PERMISIVO\`
- Cadena: lista de jugadas en vivo (código 3 = falta) ← conversor 0x7BCD00 ← cola cruda de eventos `0x3B0B8E4` (100 × 24 bytes, índice `0x3B0B8BE`, tipo en +6; tipos 0x25–0x2B = decisiones de árbitro: 0x29 falta, 0x27 amarilla…) ← 0x6A7600 ← mensajes por cambio de fase.
- Fase del partido: byte `0xF7122D` (1 = en juego, 6 = falta/tiro libre, 2 = preparar pelota parada, 3/9 = laterales/saques…). Escribe 0x5E0FED. Motivo de detención: `0x3B0B8AB` (función de reglas 0x697AA0, tabla 0xAED630).
- Árbitro: estado en `0x3B17300` (`+2` gravedad, `+4` infractor, `+5` víctima); falta pendiente `0x3B17341` (gravedad) / `0x3B17344` (cuenta para ley de ventaja, 0x7FFF = nada). 0x5FF130 decide: gravedad ≥3 → pita (tarjeta) / si no, evalúa ventaja → 0x5FFF82 pasa a fase 6.
- **Embudo único: `0x5FC1F0` "registrar falta"** (lo llaman 0x5FE510 —13 situaciones de contacto— y 0x5FFCA0). Calcula gravedad 1–4 con un puntaje + parámetros del árbitro (0x6F6A30, bytes +0xE..+0x12, fórmula (49,5 − p)·0,0202·k).
- **Parche**: desvío en 0x5FC1F0 a code cave: `rand(100) < PCT` → `xor eax,eax; ret` (no registra). PROBADO al 100 % en WE9LE: cero faltas en 2 partidos, sin cuelgues. Versión WE9: 0x5D4A10 / rand 0x620400 / cave 0xACD400 (sin probar en juego todavía).
- Mejora posible: en vez de azar puro, filtrar por gravedad (dejar pasar solo gravedad 1, cobrar tarjetas) parcheando dentro de 0x5FC1F0 antes de 0x5FC674.
- Bug arreglado en `vigilar.py`: los int3 propios del juego se devolvían como manejados → el juego se cerraba en la primera falta. Nuevo: `--al lo-hi` (filtro por AL) y `--pila N` (posibles retornos).

### IA — primer mapa en vivo (WE9LE, 2026-10-08 ~23:50)
- **Jugadores**: 23 estructuras de 0x290 bytes desde `0x3B573C0` (índice /0x17 en el código; +0x40 equipo, +0x3F dorsal/índice). Campos con estados discretos (muestreo 30 s): +0x68 (word, valores 0x04/0x80…), +0x6C/+0x6D/+0x6E/+0x6F/+0x72/+0x75/+0x92/+0x93/+0x95/+0x142 = **temporizadores** que bajan 1 por cuadro (0x66C17F…0x66C209), +0x150/+0x153 (lo escribe 0x7A438D), +0x1F4…+0x208 (tabla que cambia seguido), +0x24B.
- **Bucle por cuadro** (0x66C460): `0x679BC0`, `0x7A40F0`, `0x668F10`, `0x7A4650` (nivel equipo → candidatos a "cerebro" táctico) → por jugador `0x7A42D0(j,0)` (escribe +0x150) + `0x634CB0` → por jugador `0x66BC20` = **máquina de estados del jugador**: switch de ~45 estados con un handler cada uno (0x781FD0, 0x6870D0, 0x77F860, 0x6B1EB0, 0x7224E0, …, 0x7618A0) + 15 handlers por puntero en `0x3B69030..0x3B69064`.
- Llamado desde el bucle principal del partido 0x69BCA4 / 0x5E0BAC.
- **Próximo paso IA**: que Matías defina 2-3 comportamientos concretos a cambiar (p. ej. presión de la CPU, cantidad de pases/paredes, juego por bandas, desmarques al área). Para cada uno: identificar el estado/handler con vigilar (ejecuta + filtro), y tocar SOLO esa rutina (code cave), como con el árbitro.

### Objetivos de IA definidos por Matías (2026-10-08)
1. **Contacto**: la CPU "pone un poco el cuerpo" y ya te saca la pelota → hacer que el roce/cuerpo gane la pelota mucho menos (resolución de duelos por contacto).
2. **Marca y presión demasiado eficientes**: deja poco espacio → marca más floja / a más distancia, presión menos coordinada (que queden huecos).
3. **Creación de juego**: hoy sus goles son jugadas aisladas o pelota parada, nunca dominante → más asociativa: más pases cortos/paredes, más apoyo, menos neutralizar y más proponer.
Plan: (1) primero (es el más concreto: cambio de poseedor de la pelota tras contacto → vigilar el campo "dueño de la pelota" y subir hasta la resolución del duelo; probable parámetro de fuerza/equilibrio + azar, como la gravedad de la falta). (2) cerebro de equipo 0x7A40F0/0x7A4650 + constantes de distancia de marca (Kingsley ya tocó 0xADD3C8 1024→512 "distancia corta (marca/presión?)", 87 usos). (3) estados de pase/decisión del poseedor CPU.

### Objetivo 1 (robo por contacto) — primera caza en vivo (2026-10-09 00:00–00:12, ARG–BRA 5 estrellas)
- **Último jugador que tocó la pelota**: byte `0x3B68AC3` (0–10 equipo local, 11–21 visitante). Lo escribe SIEMPRE `0x5F0184` (or byte [edx+0x3B68AC3]); se llega por dos caminos:
  - `0x6544C9` ← handlers de recepción/control (0x6EXXXX–0x6FXXXX vía 0x5DA5FF; 0x79XXXX vía 0x66BEE4 estado del jugador; 0x78XXXX vía 0x66BEFA).
  - `0x5F2BCA` ← `0x6C680B` ← `0x6C9AD2` (función de **golpear la pelota**: aplica velocidad con dispersión al azar 0x647AE0/0x647AC0 y llama 0x6C65E0) y ← 0x5F2CF0 ← 0x712A48.
- Matías marcó 11 robos "por cuerpo" con F10 (111 cambios de pelota a la CPU en 10 min). El camino `0x6C680B/0x6C9AD2` aparece 0–4 s antes de 6 de las 11 marcas (30 eventos en total); handlers 0x79XXXX (0x79C7D1, 0x7996EA, 0x79BE63, 0x798D7B) aparecen justo en el segundo de la marca (¿control de la pelota suelta tras el roce?).
- Hipótesis: el "robo con el cuerpo" = el defensor CPU toca/desvía la pelota (golpe 0x6C9xxx desde un estado de quite/duelo) y otro la recoge. Próximo: vigilar `0x6C9AD2`/0x6C680B con pila profunda y marcas F10 para ver qué ESTADO del defensor lo dispara (handler en la máquina 0x66BC20) y ahí buscar la condición/probabilidad del duelo.
- Corrección: `0x6C65E0` (llamada desde 0x6C9AD2) NO es el golpe general de pases: solo 12–15 llamadas en ~5 min de partido → es un golpe especial (desvío/toque/despeje). Encaja con la hipótesis del "toque del defensor al poner el cuerpo". Para pases (objetivo 3) hay que encontrar otra rutina: usar la lista de eventos en vivo (registros 0x0B de 8 bytes = pase: [0B, pasador, ?, ?, 00, receptor, ...]) y vigilar quién escribe el código 0x0B → función de pase → subir a la decisión del poseedor CPU.

## Kingsley V5.5 en WE9LE (diff 2026-10-09) y pedido "construcción sí, defensa vanilla"
- WE9LE V5.5 toca muchas menos cosas que WE9 V5.5. Fuera de física/niebla/registro, solo 2 constantes de IA:
  - `0xADCD98` -6732,5 → -5200,5 (26,3 → 20,3 m), 23 usos: 0x4E9CD9, 0x4EC887, 0x4EDBF3, 0x5547C3, 0x620B48, 0x622A06, 0x62712D, 0x66D8ED, 0x66E00C, 0x67A94B, 0x67BEA6, 0x693003, 0x720EE8, 0x736DD6, 0x746924/CC0/EB3, 0x74989A, 0x771B92, 0x77824C, 0x7AA778, 0x7C315C, 0x7C85F4.
  - `0xAEC710` 8217 → 6050 (franja lateral 32,1 → 23,6 m), 48 usos (0x61EDCA … 0x846F89; `xrefs.py` lo lista).
- Readme V5.5: "midfield logic changed, more attacking opportunities for AI, more AI passing, less wing play".
- Problema: los usos están repartidos por rutinas de ataque y de defensa (máquina de estados 0x66xxxx/0x67xxxx incluida) → no se pueden separar solo con el diff.
- Plan: partido en vivo con `vigilar.py --modo ejecuta` sobre cada uso, anotando si corre con la CPU en posesión (dueño de la pelota `0x3B68AC3`) o defendiendo. Los usos "de posesión" se redirigen a una copia propia de la constante con el valor de Kingsley (code cave); el resto queda vanilla.
