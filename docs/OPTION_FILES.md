# Option files de WE9 / WE9LE / PES5 / PES6 (PC): formato e incompatibilidades

Resumen de la ingeniería inversa hecha para los conversores **WE9 → PES6** y **WE9 ⇄ WE9LE** (octubre de 2026).
Las conversiones completas se probaron en el juego. La librería `option-files/optionfile.py` implementa todo lo de
acá y el detalle fino (tablas completas, pasos de conversión, valores de referencia) está en
[option-files/PROYECTO_conversor_we9_pes6.md](option-files/PROYECTO_conversor_we9_pes6.md) y en el
[BRIEF](option-files/BRIEF_codigo_conversor_we9_pes6.md).

Fuentes: los option files reales de la federación y el código de los editores comunitarios PESEditor (PES6) y
PES-Editor-5 (PES5/WE9). Las tablas de cifrado y campos de `datos/tablas.json` se generaron de esos fuentes y se
verifican por huella SHA-256 al cargar.

## 1. Archivos

| Juego | Nombre exacto | Tamaño | Formato |
|---|---|---|---|
| WE9 | `KONAMI-WIN32WE9UOPT` | 1.250.304 | "pes5" |
| WE9 LIVEWARE EVOLUTION | `KONAMI-WIN32WE9KOPT` | 1.250.304 | "pes5" (solo cambian los primeros 9500 bytes) |
| PES5 | `KONAMI-WIN32PES5OPT` | 1.250.304 | "pes5" |
| PES6 | `KONAMI-WIN32PES6OPT` | 1.191.936 | "pes6" |

El juego busca el archivo por **nombre exacto**.

## 2. Cifrado (igual esquema en los dos formatos, distintas constantes)

1. **Capa 1:** XOR de todo el archivo con una tabla de 256 bytes (`keypc`), idéntica en los dos juegos.
2. **10 bloques**, cada uno con un checksum de 4 bytes en `inicio − 8`. El checksum es la suma de las palabras de
   32 bits del bloque cifrado, módulo 2³².
3. **Capa 2** (bloques 1–9; el 0 va en claro): palabras de 32 bits little endian con clave por índice de palabra.
   - WE9/PES5: `p = ((w − key5[i % 367]) + 1815549477) ^ 0x6C371625`
   - PES6: `p = ((w − key6[i % 446]) + 0x7AB3684C) ^ 0x7AB3684C`
4. Al **guardar**: banderas (`45, 46, 5958, 5959` en WE9; `45, 46, 5938, 5939` en PES6), cifrar, recalcular los 10
   checksums y aplicar la capa 1.

Trampa: el bloque 5 de PES6 mide 93501 bytes (no es múltiplo de 4) y se procesan `tamaño // 4` palabras.
Comprobado: cargar y guardar devuelve el mismo archivo byte a byte (WE9LE, PES5 y PES6).

| Bloque | WE9: inicio / tamaño | PES6: inicio / tamaño |
|---|---|---|
| 0 | 12 / 4948 | 12 / 4844 |
| 1 | 5144 / 1232 | 5144 / 1268 |
| 2 | 9508 / 4520 | 9544 / 4730 |
| 3 (jugadores editados) | 14044 / 22816 | 14288 / 22816 |
| 4 (jugadores) | 36872 / 620000 | 37116 / 620000 |
| 5 (plantillas, formaciones) | 657712 / 145880 | 657956 / 93501 |
| 6 (nombres de clubes) | 803608 / 19320 | 751472 / 12320 |
| 7 | 822940 / 146240 | 763804 / 147328 |
| 8 | 969192 / 259364 | 911144 / 259364 |
| 9 | 1228568 / 21016 | 1170520 / 21032 |

## 3. WE9 ⇄ WE9LE

Son el mismo formato y el mismo cifrado. **Solo difieren los primeros 9500 bytes** (cabecera + bloques 0 y 1 de
ajustes del sistema; los bytes 4–7 y 5136–5139 son checksums). Para convertir alcanza con reemplazar ese prefijo por
el de un archivo de la otra versión y comprobar los checksums.

Lección de un fallo real: PESFan Editor 5 guardó un WE9LE con la cabecera de WE9 y el juego lo rechazaba. Moraleja:
**nunca mezclar bloques de sistema entre juegos.** WE9 → WE9LE está probado en el juego. WE9LE → WE9 está verificado
en estructura, pero no en el juego. El conversor está en el repo `pes-we9-we9le`.

## 4. Jugadores

- Registro de **124 bytes**. Regulares `1..4999` en `base + idx·124`. Editados `32768..32951` en
  `baseE + (idx−32768)·124`.
  - WE9: `base` = 36872, `baseE` = 14044. Con datos: 1..4895.
  - PES6: `base` = 37116, `baseE` = 14288. Con datos: 1..4783. PES6 protege los índices ≥ 4414 (Liga Máster,
    tienda, etc.).
- `+0..31`: nombre en UTF-16LE (máximo 15 caracteres; vacío = no existe). `+32..47`: nombre de camiseta en ASCII.
  `+48..49`: nombre de llamada.
- **Campo** = `(tipo, off, shift, máscara)`. Se lee con `a = registro + 48 + off` y
  `valor = (((b[a] << 8) | b[a−1]) >> shift) & máscara`.
- Tipos: 0 crudo, 1 altura (+148 cm), 2 edad (+15), 3 nacionalidad (tabla por juego), 4 pie, 5 escala (+1),
  6 lesiones (C/B/A).
- **Incompatibilidad clave:** los mismos 77 campos están en **posiciones de bits distintas** en WE9 y en PES6
  (ejemplo: el peso de WE9 está en bits 6–12 del offset 41 y el de PES6 en bits 8–14, donde PES6 guarda además la
  piel). **Nunca copiar registros en bruto entre juegos: siempre campo a campo.** Las tablas completas están en el
  Apéndice A del PROYECTO y en `tablas.json` (`T5`, `T6`).
- Renombres: `FAVOURED FOOT` → `STRONG FOOT`, `CURLING` → `SWERVE`, posiciones `cbwS` = `cwp` y `om` = `am`.
  Habilidades especiales: se comparten 23, y las que existen solo en WE9 (`cbwL`, `bff`, `gkKick`, `statX`) se
  pierden.
- `REGISTERED POSITION = 13` existe solo en WE9 (se convierte a 12).
- **Nacionalidades:** mismos nombres con **índices distintos**, y algunas existen en un solo juego. Hay que
  convertir **por nombre** (Apéndice B), y lo que no existe pasa a `Free Nationality`.
- Banderas de editado (PES6): `nameEdited (0,3,0,1)`, `shirtEdited (0,3,1,1)`, `callEdited (0,3,2,1)`,
  `abilityEdited (0,40,4,1)`.

## 5. Apariencia (aproximada, en uso en el conversor)

| Dato | WE9 | PES6 |
|---|---|---|
| Peinado `hair` | `(0, 45, 0, 0x7FF)` | `(0, 45, 0, 0x7FF)` |
| Piel | `(0, 43, 1, 3)` | `(0, 41, 6, 3)` |
| Tipo de cara | `(0, 55, 0, 3)` | `(0, 55, 0, 3)` |
| Cara | ? | `(0, 53, 5, 0x1FF)` |

- Peinados `< 1026`: misma numeración en los dos juegos. `≥ 1026`: peinados especiales con numeración corrida;
  `datos/peinados_especiales.csv` trae las equivalencias conocidas y el resto se interpola y se ajusta al especial
  existente más cercano en PES6. Peinado 0 en WE9: queda en 0 si la base de PES6 usa 0 con cara tipo 0; si no, pasa a 108 (valor por defecto del conversor).
- Complexión: nibbles en los bytes 91 y 105–109 del registro, con corrimiento de bits entre juegos (tabla `PHYS` del
  conversor). Accesorios: bytes 94–99. Solo se copian los valores que existen en PES6; si no, se usa el valor por
  defecto (la moda de los editados del archivo base).
- Cara real y caras especiales **no** se trasladan: se pone `faceType = 0` y `face = 0`.

## 6. Equipos y plantillas

| | WE9 | PES6 |
|---|---|---|
| Selecciones | 0..56 (distinto orden: PES6 intercala Angola, Ghana, Togo, Trinidad y Tobago) | 0..56 |
| Clásicos | 57..63 (ARG, BRA, ING, FRA, ALE, ITA, HOL) | 57..63 (ING, FRA, ALE, ITA, HOL, ARG, BRA) |
| Japón | 64, 65 | 64 |
| Edited National 1..7 / Edited | 66..72 / 73 | 65..71 / 72 |
| Clubes | 74..211 (138) | 73..212 (140, incluye PES United / WE United) |

- Plantilla = `N` índices de jugador (2 bytes) + `N` dorsales (1 byte, 255 = vacío). `N` = 23 para selecciones y
  32 para clubes. Las direcciones están en `optionfile.py` (`slot23/slot32/num23/num32`).
- **Trampa de WE9: orden permutado.** En `670512 + 628·j + 6232` (con `j = t` o `t − 10`) hay 32 bytes de orden. La
  plantilla real es `ids[orden[k]]`. Si se ignora, salen desordenadas (81 equipos lo tenían en el archivo de la
  federación). En PES6 el orden está en `677202 + 6 + 364·t`.
- Formación PES6: `677202 + 364·t`. Posiciones de los 11 titulares en `+138` (códigos → rol: GK=0, CB=1–7,
  SB=8–9, DMF=10–14, WB=15–16, CMF=17–21, SMF=22–23, AMF=24–28, WF=29–30, SS=31–35, CF=36–40). Las formaciones de
  WE9 (628 bytes por equipo) tienen otra estructura y no se convierten.
- Nombres de clubes: WE9 en `803608 + 140·j` y PES6 en `751472 + 88·j` (UTF-8, hasta 49 bytes).
- Las ligas están en distinto orden entre juegos (la Bundesliga de WE9 son los `Team A..R` de PES6).
  `datos/clubes_we9_a_pes6.csv` trae el emparejamiento revisado.

## 7. Herramientas

- `option-files/optionfile.py`: librería y consola (`info`, `jugador`, `equipo`, `exportar` a JSON, `poner` un
  campo). Nunca pisa el archivo original y relee lo que escribe.
- Conversores completos (repos aparte, públicos): `pes-we9-a-pes6` (WE9/PES5/WE9LE → PES6, con plantillas,
  titulares por asignación húngara y apariencia) y `pes-we9-we9le`.

## 8. Puente con el espía en vivo (por hacer)

El espía da `equipo` + `jugador` 0–10 (el que está en cancha). Hipótesis a verificar: ese índice sigue el orden
efectivo de la plantilla (los 11 titulares, sección 6) del equipo que juega. Si se confirma, cada evento se puede
atribuir a un índice de jugador del option file, y de ahí salen las estadísticas persistentes, el option file online
y las cartas. Falta también saber qué equipo es el local y cuál el visitante en memoria.
