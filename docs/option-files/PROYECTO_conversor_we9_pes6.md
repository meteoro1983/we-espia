# Proyecto: conversor de option files WE9 → PES6 (PC)

Documento de **proyecto y lógica**. Describe qué hace el conversor, cómo funciona por dentro y qué está comprobado. El documento hermano `BRIEF_codigo_conversor_we9_pes6.md` es el brief para escribir el código.

Todo lo que aquí se afirma como **verificado** se comprobó en una sesión de trabajo con los archivos reales del usuario y con el código fuente de los editores PESEditor (PES6) y PES-Editor-5 (PES5/WE9). Lo que no se pudo comprobar está marcado como **no verificado** o **abierto**.

---

## 1. Objetivo y alcance

**Origen:** option file de WE9 para PC (`KONAMI-WIN32WE9UOPT`), editado durante años con cientos de jugadores fantasy.
**Destino:** option file de PES6 para PC (`KONAMI-WIN32PES6OPT`), ya generado por el propio juego.

**Fase 1 (este documento):** transferir jugadores (datos y atributos) y plantillas de equipos, escribiendo un option file de PES6 válido (cifrado y checksums correctos) sin ayuda de ningún editor.
**Fase 2 (posterior):** apariencia (peinado, cara, piel, cuerpo, etc.). Requiere deducir dónde la guarda WE9. No está resuelta.

**Fuera de alcance de la fase 1:** apariencia, nombres/escudos/camisetas de clubes, formaciones de WE9, Liga Máster y tienda, cualquier otro juego o plataforma (PS2, Xbox, WE9LE).

**Resultado esperado:** un archivo nuevo que el juego carga sin errores. El original de PES6 nunca se modifica.

## 2. Estado verificado

| Hito | Resultado |
|---|---|
| Descifrar y volver a cifrar los 4 option files disponibles | Idéntico byte a byte; checksums de origen válidos |
| Leer jugadores del binario y compararlos con los CSV de los editores | Todas las columnas numéricas coinciden en los dos juegos (5183 jugadores WE9, 4967 PES6) |
| Prueba de 10 jugadores inyectados en PES6 | El usuario confirmó que **funcionó** en el juego |
| Conversión completa (jugadores + 207 plantillas) | El usuario confirmó que **funcionó** en el juego |
| Apariencia | **No resuelto** |

## 3. Archivos y nombres

- El juego busca el option file por **nombre exacto**: `KONAMI-WIN32PES6OPT` (PES6), `KONAMI-WIN32WE9UOPT` (WE9 regular). El conversor debe **escribir el destino con ese nombre exacto**.
- Tamaños exactos (se validan antes de tocar nada): **WE9 = 1.250.304 bytes**, **PES6 = 1.191.936 bytes**.
- Los CSV de los editores (solo como referencia y para pruebas) tienen 82 columnas, codificación `latin-1`, saltos `\r\n`. Se pueden leer y reescribir idénticos con el módulo `csv`.

Archivos de referencia (fixtures) de la sesión:

| Archivo | MD5 |
|---|---|
| `KONAMI-WIN32WE9UOPT` (WE9 regular con los fantasy) | `6a7f010eecec3cda76f9dd4880baba5f` |
| `KONAMI-WIN32PES6OPT` (PES6 virgen) | `ad918e930e9593d7e2ed4619f8b53b86` |
| `pes5.csv` (export de WE9) | `3305814340cbe601e1615bd7398ab45f` |
| `pes6.csv` (export de PES6 virgen) | `44ef94bbf406048555485ca8f2cc83cb` |
| `mapeo_equipos_we9_a_pes6.csv` (tabla de clubes) | `09f83b34c988f4af9ed5a1ad62397321` |
| **Salida de referencia** `KONAMI-WIN32PES6OPT` convertido | `88bd2e72a982e55123dd22dd72980178` |

## 4. Formato del option file (PC)

Los dos juegos usan el mismo esquema. Cambian las constantes.

### 4.1 Capa 1: XOR de 256 bytes sobre todo el archivo
`byte[i] ^= keyPC[i & 255]`. La tabla `keyPC` es **la misma** en los dos juegos (verificado).

### 4.2 Bloques
El archivo se divide en 10 bloques. Cada uno tiene un **checksum de 4 bytes en `inicio - 8`** (little endian).

| Bloque | WE9: inicio / tamaño | PES6: inicio / tamaño |
|---|---|---|
| 0 | 12 / 4948 | 12 / 4844 |
| 1 | 5144 / 1232 | 5144 / 1268 |
| 2 | 9508 / 4520 | 9544 / 4730 |
| 3 | 14044 / 22816 | 14288 / 22816 |
| 4 | 36872 / 620000 | 37116 / 620000 |
| 5 | 657712 / 145880 | 657956 / 93501 |
| 6 | 803608 / 19320 | 751472 / 12320 |
| 7 | 822940 / 146240 | 763804 / 147328 |
| 8 | 969192 / 259364 | 911144 / 259364 |
| 9 | 1228568 / 21016 | 1170520 / 21032 |

Trampa: el tamaño del bloque 5 de PES6 (93501) **no es múltiplo de 4**. Se procesa `tamaño // 4` palabras, igual que el código Java.

### 4.3 Capa 2: cifrado por palabras (bloques 1 a 9; el bloque 0 va en claro)
Cada bloque se trata como palabras de 32 bits little endian; `idx` es el índice de palabra **dentro del bloque**. Todas las operaciones son módulo 2³².

| | WE9 | PES6 |
|---|---|---|
| Tabla `key` | 367 valores (más el desplazamiento `+1815543808` aplicado a cada uno) | 446 valores |
| Descifrar | `p = ((w - key[idx % 367]) + 1815549477) ^ 0x6C371625` | `p = ((w - key[idx % 446]) + 0x7AB3684C) ^ 0x7AB3684C` |
| Cifrar | `c = key[idx % 367] + ((p ^ 0x6C371625) - 1815549477)` | `c = key[idx % 446] + ((p ^ 0x7AB3684C) - 0x7AB3684C)` |

Atención a la precedencia en Java: `m - key + C1 ^ C2` es `((m - key) + C1) ^ C2`.

### 4.4 Checksums
`checksum[i] = suma de las palabras de 32 bits del bloque i, módulo 2³²`, calculada **sobre los datos ya cifrados** y **antes** de aplicar la capa 1 al guardar. Al cargar, se comprueba después de deshacer la capa 1 y antes de descifrar.

### 4.5 Orden de operaciones
- **Cargar:** deshacer capa 1 → (validar checksums) → descifrar bloques 1 a 9.
- **Guardar:** fijar banderas → cifrar bloques 1 a 9 → recalcular los 10 checksums → aplicar capa 1.
- **Banderas al guardar (PES6):** `data[45]=1`, `data[46]=1`, `data[5938]=1`, `data[5939]=1` (así lo hace PESEditor). En WE9 son 45, 46, 5958 y 5959.

### 4.6 Lección de un fallo real (WE9LE)
PESFan Editor 5 guardó un option file de WE9LE con la cabecera y los primeros bloques de WE9. Los 4 bytes 4 a 7 son el checksum del bloque 0. El juego rechazaba el archivo porque los bloques 0 y 1 (ajustes) no eran los suyos. Restaurar los primeros 9500 bytes de un archivo virgen lo arregló. Moraleja: **no mezclar bloques de sistema entre juegos**; el conversor solo toca jugadores y plantillas.

## 5. Registro de jugador

- **Tamaño del registro: 124 bytes.**
- **Índices:** regulares `1..4999` (el 0 no se usa); editados `32768..32951` (184).
- **Dirección del registro:** regulares `base + idx*124`; editados `baseE + (idx-32768)*124`.

| | WE9 | PES6 |
|---|---|---|
| `base` (regulares) | 36872 | 37116 |
| `baseE` (editados) | 14044 | 14288 |
| Jugadores con datos | regulares 1..4895; 4896..4999 `<Unused>` | regulares 1..4783; 4784..4999 sin usar |

### 5.1 Contenido del registro
- `+0..+31`: nombre, **UTF-16LE**, máximo 15 caracteres, terminado en `0000`. Nombre vacío = jugador inexistente (los editores muestran `<Edited n>` o similar).
- `+32..+47`: nombre de camiseta, 16 bytes ASCII mayúsculas, rellenos con `00`. Si el origen lo trae vacío se genera a partir del nombre (sin acentos, mayúsculas, máx. 15).
- `+48..+49`: `nombre de llamada` (callName). El conversor escribe `0xCDCD`.
- `+48 + off`: campos de estadísticas (ver abajo).

### 5.2 Lectura de un campo
Dado `(tipo, off, shift, máscara)`, con `a = dirección_registro + 48 + off`:

`valor = (((data[a] << 8) | data[a-1]) >> shift) & máscara`

La escritura limpia `máscara << shift` en esos 16 bits y escribe el valor desplazado. Se leen **dos bytes**, `a-1` (bajo) y `a` (alto).

### 5.3 Tipos de campo
| Tipo | Significado | Campos | Valor mostrado |
|---|---|---|---|
| 0 | número crudo | atributos, posiciones jugables (0/1), habilidades especiales (0/1), posición registrada, lado preferido (0=R, 1=L, 2=B) | `raw` |
| 1 | altura | `HEIGHT` | `raw + 148` |
| 2 | edad | `AGE` | `raw + 15` |
| 3 | nacionalidad | `NATIONALITY` | índice a la tabla de cada juego (**distinta**; ver Apéndice B) |
| 4 | pie fuerte | `STRONG FOOT` (0=R, 1=L) | `raw` |
| 5 | escala desplazada | precisión y frecuencia del pie débil, regularidad, condición, estilos de regate, tiro libre, penal y saque de arco | `raw + 1` |
| 6 | tolerancia a lesiones | `INJURY TOLERANCE` (0=C, 1=B, 2=A) | `raw` |

El código de los editores define también un tipo 7, que **no** lo usa ninguno de los campos de esta tabla.

Los campos categóricos (pie, lado preferido, lesión, estilos) usan **la misma codificación `raw → etiqueta` en los dos juegos** (verificado con los valores presentes en los dos option files). Única diferencia: el estilo de tiro libre llega a 10 en PES6 y a 9 en WE9, así que todo valor de WE9 es válido en PES6.

### 5.4 Equivalencias entre juegos
- Misma lista de 46 campos base, con dos renombres en el CSV: `FAVOURED FOOT` → `STRONG FOOT`; `CURLING` → `SWERVE`.
- Posiciones jugables: `cbwS` (WE9) = `cwp` (PES6), `om` = `am`.
- Habilidades especiales: WE9 y PES6 comparten 23. Se mapean **por etiqueta** (ver Apéndice A, que ya trae el orden). Los campos de WE9 sin equivalente se **descartan**: `cbwL` (ASW), `bff`, `gkKick`, `statX`.
- `REGISTERED POSITION`: el código 13 existe solo en WE9; se convierte a 12 (decisión adoptada, ver sección 10).
- Bandera `abilityEdited` (PES6, `(0, 40, 4, 1)`) corresponde a `statEdited` de WE9.

### 5.5 Banderas que el conversor activa en cada jugador escrito
`nameEdited (0,3,0,1)`, `shirtEdited (0,3,1,1)`, `callEdited (0,3,2,1)`, `abilityEdited (0,40,4,1)`, todas a 1.

### 5.6 Apariencia (solo PES6, solo lo conocido)
`hair (0,45,0,0x7FF)`, `faceType (0,55,0,3)`, `skin (0,41,6,3)`, `face (0,53,5,0x1FF)`.
En fase 1, a cada jugador escrito se le ponen `faceType=0` y `face=0` (cara genérica; evita heredar una cara real del hueco). `hair` y `skin` quedan como estaban en el hueco de destino.
En WE9 la posición de estos campos **es desconocida**. Nota: el peso de WE9 está en bits 6 a 12 del campo `(offset 41)` y el de PES6 en bits 8 a 14; la piel de PES6 ocupa justo bits 6 a 7. **Por eso los registros nunca se copian en bruto**: siempre campo a campo.

## 6. Equipos y plantillas

### 6.1 Índices de equipo
| | WE9 | PES6 |
|---|---|---|
| Selecciones | 0..56 (57) | 0..56 (57) |
| Clásicos | 57..63 | 57..63 |
| Japón | 64 (Japan 1), 65 (Japan 2) | 64 (Japan 1) |
| «Edited National 1..7» | 66..72 | 65..71 |
| «Edited» | 73 | 72 |
| Clubes | 74..211 (138) | 73..212 (140) |

Orden de los clásicos: WE9 = Argentina, Brasil, Inglaterra, Francia, Alemania, Italia, Países Bajos. PES6 = Inglaterra, Francia, Alemania, Italia, Países Bajos, Argentina, Brasil.

### 6.2 Plantillas
Cada equipo guarda `N` huecos de **2 bytes (índice de jugador, little endian; 0 = vacío)** y `N` bytes de **dorsal (255 = vacío)**. `N = 23` para selecciones/clásicos/extras y `N = 32` para clubes.

| | WE9 | PES6 |
|---|---|---|
| Equipos de 23 | 74 (0..73) | 73 (0..72) |
| Clubes de 32 | 138 | 140 |
| `slot23` / `slot32` | 664054 / 667458 | 664372 / 667730 |
| `num23` / `num32` | 657712 / 659414 | 657956 / 659635 |

Dirección de huecos: `slot23 + t*46` para `t < n23`; `slot32 + (t - n23)*64` para clubes. Los dorsales siguen la misma lógica con `num23`/`num32` (`t*23` o `(t - n23)*32`).

### 6.3 Orden de plantilla permutado (**importante en WE9**)
WE9 guarda 32 bytes de «orden» por equipo en `670512 + 628*j + 6232`, con `j = t` si `t < 64`, `j = t - 10` si `74 ≤ t < 212`. **La plantilla efectiva** es `ids_efectivos[k] = ids_crudos[orden[k]]` (y lo mismo con los dorsales). En el archivo del usuario, **81 equipos tienen orden no identidad**; si se ignora, las plantillas salen desordenadas.
En PES6 el orden está en `677202 + 6 + 364*t` y solo es no identidad en los equipos 204..212 (no tocados).

### 6.4 Formación de PES6
Bloque por equipo en `677202 + 364*t`. Códigos de posición de los 11 titulares de la formación 0: `677202 + 138 + 364*t`, 11 bytes (formación alternativa `alt`: `+ alt*82`). Existe para `t < 64` y `73 ≤ t < 213`; **no se reordena** para los equipos 64..72.
Códigos de posición → rol, según PESEditor (`tidy11`):
GK=0; CBT=1,2,3,6,7; CWP=4,5; SB=8,9; DMF=10..14; WB=15,16; CMF=17..21; SMF=22,23; AMF=24..28; WF=29,30; SS=31..35; CF=36..40.

## 7. Lógica de la conversión (pasos)

**Paso 1 — Validar** tamaños y checksums de los dos archivos. Abortar si algo no cuadra.

**Paso 2 — Emparejar equipos** (`team_map`, WE9 → PES6):
1. **Selecciones 0..56:** por **país dominante** de la plantilla (nacionalidad más frecuente), no por índice: PES6 intercala Angola, Ghana, Togo y Trinidad y Tobago. Sin pareja en PES6 (se omiten): Marruecos, Senegal, Venezuela, China. Sin pareja en WE9 (quedan intactas): Angola, Ghana, Togo, Trinidad y Tobago.
2. **Clásicos:** por nombre (ver 6.1). **Japón 1:** 64→64. **Edited National 1..7:** 66..72 → 65..71. **Edited:** 73 → 72. Japón 2 se omite.
3. **Clubes:** según la tabla de la sección 8 (editable por el usuario en `mapeo_equipos_we9_a_pes6.csv`).
Comprobar que no hay destinos repetidos.

**Paso 3 — Plantillas efectivas de WE9** de los equipos emparejados (6.3).

**Paso 4 — Conjuntos de jugadores:**
- `R` = jugadores de WE9 que aparecen en esas plantillas.
- `P` = jugadores de PES6 referenciados por equipos **no** emparejados (protegidos).
- `Q` = jugadores de WE9 con nombre que no están en `R` (libres).

**Paso 5 — Asignar huecos de PES6** (`slotmap`: índice WE9 → índice PES6):
1. Constante `LIMITE = 4413`: **los índices de PES6 ≥ 4414 se protegen** (Liga Máster, tienda, jóvenes, veteranos y sin usar).
2. Regulares de `R`: **identidad** (mismo índice) si `1 ≤ i ≤ 4413` y `i ∉ P`; si no, se guardan como pendientes.
3. Editados (32768+): **identidad** siempre.
4. Pendientes de `R`: van al primer hueco libre (`≤ 4413`, `∉ P`, no ocupado, y que no sea el índice de otro jugador de `R`).
5. `Q`: mismo procedimiento; los que no caben se **descartan** y se listan.

**Paso 6 — Escribir jugadores.** Para cada par, `convertir_jugador` (campo a campo según Apéndice A, nacionalidad por nombre, regPos 13→12, nombre, camiseta, `callName=0xCDCD`, banderas). Después `faceType=0` y `face=0`.

**Paso 7 — Escribir plantillas.** Para cada equipo emparejado: traducir los índices con `slotmap` (los no mapeados quedan en 0 con dorsal 255); si el equipo tiene bloque de formación, reordenar los **11 titulares** con asignación húngara (11×11) sobre esta matriz de costes:


```
coste(a, j) = (0 si el titular a puede jugar el rol del hueco j, es decir su campo de posición jugable vale 1; si no, 10)
            + (0 si su posición registrada coincide con el rol, o el rol es CBT y la posición es CWP/CBT; si no, 1)
            + 0.001 * |a - j|
```

Los jugadores y sus dorsales se mueven juntos. El banquillo conserva el orden de WE9.

**Paso 8 — Guardar y verificar.** Poner banderas (45, 46, 5938, 5939), cifrar, checksums, capa 1. Releer el archivo escrito y comprobar: checksums válidos, datos idénticos al buffer (salvo los 4 bytes de cada checksum), plantillas iguales a las de WE9 (comparando nombres), sin jugadores repetidos en un equipo, y **ningún byte cambiado fuera de**: registros de jugador destino, huecos y dorsales de los equipos emparejados y las 4 banderas.

## 8. Emparejamiento de clubes

WE9 y PES6 tienen las mismas ligas, en distinto orden. Se emparejan **dentro de cada bloque**: primero por **nombre coincidente** (normalizado: NFKD → ASCII → minúsculas → solo `a-z0-9`) y el resto **por posición dentro del bloque**.

| Liga | Clubes WE9 | Clubes PES6 |
|---|---|---|
| Premier | 0..19 | 0..19 |
| Ligue 1 | 20..39 | 20..39 |
| Bundesliga | 40..57 | 122..139 (`Team A`..`Team R`) |
| Serie A | 58..77 | 40..59 |
| Eredivisie | 78..95 | 60..77 |
| Liga | 96..115 | 78..97 |
| Otros | 116..137 | 98..119 |

(Las etiquetas de liga son aproximadas; lo que manda son los rangos. Índices de club; el equipo es `74 + i` en WE9 y `73 + j` en PES6.) Los dos clubes `PES United` y `WE United` de PES6 (120, 121) quedan intactos. Resultado de referencia: 65 emparejados por nombre y 73 por posición.
Los nombres de clubes están en el propio option file: WE9 en `803608` con paso `140`, PES6 en `751472` con paso `88`; nombre en UTF-8, hasta 49 bytes, terminado en 0.

## 9. Resultados de referencia (conversión completa)

| Dato | Valor |
|---|---|
| Equipos emparejados | **207** (138 clubes, 53 selecciones, 7 clásicos, Japón 1, 8 editados) |
| Jugadores WE9 referenciados por esos equipos (`R`) | 4315 |
| Jugadores con nombre sin equipo (`Q`) | 764 (144 caben, **620 descartados**) |
| Jugadores transferidos | **4459** |
| Protegidos en PES6 por equipos no emparejados | 138 |
| Jugadores movidos a otro hueco | 287 |
| Avisos de nacionalidad (→ `Free Nationality`) | 7 |
| Titulares fuera de rol / total reordenados | 413 de 2178 (~19 %) |
| Errores de verificación; bytes fuera de lo esperado | 0; 0 |
| MD5 de la salida | `88bd2e72a982e55123dd22dd72980178` |

## 10. Limitaciones y puntos abiertos

1. **Apariencia:** no se transfiere. Los jugadores conservan peinado y piel del hueco (y caras genéricas).
2. **620 jugadores con nombre no transferidos** (sin equipo en las plantillas emparejadas y sin hueco libre). Quedan en `reporte_jugadores.csv`.
3. **Selecciones sin pareja** (4 + 4), ver paso 2. Alternativa pendiente: emparejarlas por posición.
4. **Titulares fuera de rol (19 %):** consecuencia de usar la formación de PES6. Se puede afinar o transferir las formaciones de WE9 (estructura distinta: 628 bytes por equipo frente a 364).
5. **Caracteres especiales:** el nombre se copia como unidades UTF-16 crudas. En WE9, tres nombres (índices 998, 2112, 3548) usan códigos propios del juego para `û`, `á` y similares que el CSV muestra como Latin-1. **No verificado** que PES6 interprete esos códigos igual; revisar visualmente.
6. **Regla de PESEditor sobre editados:** los editados `32768..32919` no deberían ir a equipos > 56 en su modo seguro. La conversión los dejó en identidad y el juego los cargó; el riesgo se considera bajo pero **no se investigó a fondo**.
7. **`REGISTERED POSITION = 13`** (solo WE9) se convirtió a 12 por decisión; no se verificó su significado exacto.
8. **No se copian:** nombres, abreviaturas, escudos y camisetas de clubes; capitán y lanzadores; Liga Máster y tienda (índices ≥ 4414 protegidos).
9. Si PES6 tuviera banderas de validación adicionales por jugador, no están cubiertas: el juego aceptó la salida de referencia.

## 11. Fase 2 (apariencia): plan

1. En PES6 se conoce la posición de `hair`, `faceType`, `skin`, `face` (5.6). Aún se desconocen botines, accesorios y complexión.
2. En WE9 hay que **deducirla**: el usuario guarda, en el juego, un option file base y varios derivados que difieren **en un solo cambio** (peinado, piel, cara, cuerpo), de un mismo jugador editado. Se comparan los registros descifrados byte a byte.
3. Después hay que construir **tablas de equivalencia** de índices (peinado y cara no numeran igual en los dos juegos); algunas serán aproximaciones.
4. La fase 2 se añade como módulo nuevo sin tocar el núcleo de la fase 1.

---

## Apéndice A. Tabla de campos (generada del código de los editores)

Tupla = `(tipo, offset, shift, máscara)`. Lectura según 5.2. Las habilidades especiales de PES6 provienen del bloque `abilitySpecial` de `Stats.java` y se alinean por orden con las de WE9.

| Columna CSV (canónica = PES6) | WE9/PES5 (tipo, off, shift, máscara) | PES6 (tipo, off, shift, máscara) |
|---|---|---|
| GK  0 | 0, 8, 6, 1 | 0, 7, 7, 1 |
| CWP  2 | 0, 8, 7, 1 | 0, 7, 15, 1 |
| CBT  3 | 0, 12, 4, 1 | 0, 9, 7, 1 |
| SB  4 | 0, 12, 5, 1 | 0, 9, 15, 1 |
| DMF  5 | 0, 12, 6, 1 | 0, 11, 7, 1 |
| WB  6 | 0, 12, 7, 1 | 0, 11, 15, 1 |
| CMF  7 | 0, 16, 4, 1 | 0, 13, 7, 1 |
| SMF  8 | 0, 16, 5, 1 | 0, 13, 15, 1 |
| AMF  9 | 0, 16, 6, 1 | 0, 15, 7, 1 |
| WF 10 | 0, 16, 7, 1 | 0, 15, 15, 1 |
| SS  11 | 0, 20, 4, 1 | 0, 17, 7, 1 |
| CF  12 | 0, 20, 5, 1 | 0, 17, 15, 1 |
| REGISTERED POSITION | 0, 6, 4, 15 | 0, 6, 4, 15 |
| HEIGHT | 1, 41, 0, 63 | 1, 41, 0, 63 |
| STRONG FOOT | 4, 5, 0, 1 | 4, 5, 0, 1 |
| FAVOURED SIDE | 0, 20, 6, 3 | 0, 33, 14, 3 |
| WEAK FOOT ACCURACY | 5, 34, 5, 7 | 5, 33, 11, 7 |
| WEAK FOOT FREQUENCY | 5, 35, 0, 7 | 5, 33, 3, 7 |
| ATTACK | 0, 7, 0, 127 | 0, 7, 0, 127 |
| DEFENSE | 0, 7, 7, 127 | 0, 8, 0, 127 |
| BALANCE | 0, 9, 0, 127 | 0, 9, 0, 127 |
| STAMINA | 0, 9, 7, 127 | 0, 10, 0, 127 |
| TOP SPEED | 0, 10, 6, 127 | 0, 11, 0, 127 |
| ACCELERATION | 0, 11, 5, 127 | 0, 12, 0, 127 |
| RESPONSE | 0, 13, 0, 127 | 0, 13, 0, 127 |
| AGILITY | 0, 13, 7, 127 | 0, 14, 0, 127 |
| DRIBBLE ACCURACY | 0, 14, 6, 127 | 0, 15, 0, 127 |
| DRIBBLE SPEED | 0, 15, 5, 127 | 0, 16, 0, 127 |
| SHORT PASS ACCURACY | 0, 17, 0, 127 | 0, 17, 0, 127 |
| SHORT PASS SPEED | 0, 17, 7, 127 | 0, 18, 0, 127 |
| LONG PASS ACCURACY | 0, 18, 6, 127 | 0, 19, 0, 127 |
| LONG PASS SPEED | 0, 19, 5, 127 | 0, 20, 0, 127 |
| SHOT ACCURACY | 0, 21, 0, 127 | 0, 21, 0, 127 |
| SHOT POWER | 0, 21, 7, 127 | 0, 22, 0, 127 |
| SHOT TECHNIQUE | 0, 22, 6, 127 | 0, 23, 0, 127 |
| FREE KICK ACCURACY | 0, 23, 5, 127 | 0, 24, 0, 127 |
| SWERVE | 0, 25, 0, 127 | 0, 25, 0, 127 |
| HEADING | 0, 25, 7, 127 | 0, 26, 0, 127 |
| JUMP | 0, 26, 6, 127 | 0, 27, 0, 127 |
| TECHNIQUE | 0, 29, 0, 127 | 0, 29, 0, 127 |
| AGGRESSION | 0, 29, 7, 127 | 0, 30, 0, 127 |
| MENTALITY | 0, 30, 6, 127 | 0, 31, 0, 127 |
| GOAL KEEPING | 0, 31, 5, 127 | 0, 32, 0, 127 |
| TEAM WORK | 0, 33, 0, 127 | 0, 28, 0, 127 |
| CONSISTENCY | 5, 33, 7, 7 | 5, 33, 0, 7 |
| CONDITION / FITNESS | 5, 34, 2, 7 | 5, 33, 8, 7 |
| DRIBBLING | 0, 24, 4, 1 | 0, 21, 7, 1 |
| TACTIAL DRIBBLE | 0, 24, 5, 1 | 0, 21, 15, 1 |
| POSITIONING | 0, 24, 6, 1 | 0, 23, 7, 1 |
| REACTION | 0, 24, 7, 1 | 0, 23, 15, 1 |
| PLAYMAKING | 0, 28, 4, 1 | 0, 25, 7, 1 |
| PASSING | 0, 28, 5, 1 | 0, 25, 15, 1 |
| SCORING | 0, 28, 6, 1 | 0, 27, 7, 1 |
| 1-1 SCORING | 0, 28, 7, 1 | 0, 27, 15, 1 |
| POST PLAYER | 0, 32, 4, 1 | 0, 29, 7, 1 |
| LINES | 0, 32, 5, 1 | 0, 29, 15, 1 |
| MIDDLE SHOOTING | 0, 32, 6, 1 | 0, 31, 7, 1 |
| SIDE | 0, 32, 7, 1 | 0, 31, 15, 1 |
| CENTRE | 0, 35, 5, 1 | 0, 19, 15, 1 |
| PENALTIES | 0, 35, 6, 1 | 0, 19, 7, 1 |
| 1-TOUCH PASS | 0, 35, 7, 1 | 0, 35, 0, 1 |
| OUTSIDE | 0, 36, 0, 1 | 0, 35, 1, 1 |
| MARKING | 0, 36, 1, 1 | 0, 35, 2, 1 |
| SLIDING | 0, 36, 2, 1 | 0, 35, 3, 1 |
| COVERING | 0, 36, 3, 1 | 0, 35, 4, 1 |
| D-LINE CONTROL | 0, 36, 4, 1 | 0, 35, 5, 1 |
| PENALTY STOPPER | 0, 36, 5, 1 | 0, 35, 6, 1 |
| 1-ON-1 STOPPER | 0, 36, 6, 1 | 0, 35, 7, 1 |
| LONG THROW | 0, 36, 7, 1 | 0, 37, 7, 1 |
| INJURY TOLERANCE | 6, 35, 3, 3 | 6, 33, 6, 3 |
| DRIBBLE STYLE | 5, 6, 0, 3 | 5, 6, 0, 3 |
| FREE KICK STYLE | 5, 5, 1, 15 | 5, 5, 1, 15 |
| PK STYLE | 5, 5, 5, 7 | 5, 5, 5, 7 |
| DROP KICK STYLE | 5, 6, 2, 3 | 5, 6, 2, 3 |
| AGE | 2, 62, 5, 31 | 2, 65, 9, 31 |
| WEIGHT | 0, 41, 6, 127 | 0, 41, 8, 127 |
| NATIONALITY | 3, 63, 2, 127 | 3, 65, 0, 127 |

## Apéndice B. Tablas de nacionalidad (derivadas del option file y su CSV)

`—` = no existe en ese juego. La conversión es **por nombre**; lo que no exista en PES6 pasa a `Free Nationality`. Esta tabla sale de cruzar el binario con el CSV de cada editor; los nombres pueden variar de la lista interna de los editores, así que el conversor debe normalizar y mantener una tabla de alias.

| Nombre | índice WE9 | índice PES6 |
|---|---|---|
| Albania | 57 | 67 |
| Algeria | 71 | 76 |
| Angola | 72 | 32 |
| Argentina | 42 | 44 |
| Armenia | 58 | 71 |
| Australia | 56 | 56 |
| Austria | 0 | 0 |
| Belarus | 59 | 72 |
| Belgium | 1 | 1 |
| Benin | — | 77 |
| Bolivia | 104 | 63 |
| Bosnia and Herzegovina | 60 | 57 |
| Brazil | 43 | 45 |
| Bulgaria | 2 | 2 |
| Burkina Faso | 73 | 78 |
| Cameroon | 32 | 33 |
| Canada | 94 | 98 |
| Cape Verde | 74 | 79 |
| Chile | 44 | 46 |
| China | 51 | 65 |
| Colombia | 45 | 47 |
| Costa Rica | 39 | 40 |
| Cote d'Ivoire | 33 | 34 |
| Croatia | 3 | 3 |
| Cyprus | 61 | 68 |
| Czech Republic | 4 | 4 |
| DR Congo | 76 | 81 |
| Denmark | 5 | 5 |
| Ecuador | 46 | 48 |
| Egypt | 77 | 82 |
| England | 6 | 6 |
| Equatorial Guinea | 78 | 83 |
| Estonia | 63 | 58 |
| Finland | 7 | 7 |
| France | 8 | 8 |
| Free Nationality | 108 | 105 |
| Gabon | 79 | 84 |
| Gambia | 80 | 85 |
| Georgia | 62 | 73 |
| Germany | 9 | 9 |
| Ghana | 81 | 35 |
| Greece | 10 | 10 |
| Grenada | 95 | 99 |
| Guadeloupe | 96 | 100 |
| Guatemala | 97 | — |
| Guinea | 82 | 86 |
| Guinea-Bissau | 83 | 87 |
| Guyana | 105 | — |
| Honduras | 98 | 60 |
| Hungary | 11 | 11 |
| Iceland | 65 | 69 |
| Iran | 52 | 52 |
| Ireland | 12 | 12 |
| Israel | 66 | 59 |
| Italy | 13 | 13 |
| Jamaica | 99 | 61 |
| Japan | 53 | 53 |
| Kenya | — | 88 |
| Latvia | 14 | 14 |
| Liberia | 84 | 89 |
| Libya | 85 | 90 |
| Liechtenstein | — | 74 |
| Lithuania | 67 | 75 |
| Luxembourg | 68 | — |
| Macedonia | 69 | 70 |
| Mali | 86 | 91 |
| Martinique | 100 | 101 |
| Mauritius | 87 | — |
| Mexico | 40 | 41 |
| Moldova | 70 | — |
| Morocco | 34 | 92 |
| Mozambique | 88 | 93 |
| Namibia | 89 | — |
| Netherlands | 15 | 15 |
| Netherlands Antilles | 101 | 102 |
| New Zealand | 107 | 104 |
| Nigeria | 35 | 36 |
| Northern Ireland | 16 | 16 |
| Norway | 17 | 17 |
| Oman | — | 103 |
| Panama | 102 | 62 |
| Paraguay | 47 | 49 |
| Peru | 48 | 50 |
| Poland | 18 | 18 |
| Portugal | 19 | 19 |
| Romania | 20 | 20 |
| Russia | 21 | 21 |
| Saudi Arabia | 54 | 54 |
| Scotland | 22 | 22 |
| Senegal | 36 | 94 |
| Serbia and Montenegro | 23 | 23 |
| Sierra Leone | 90 | 95 |
| Slovakia | 24 | 24 |
| Slovenia | 25 | 25 |
| South Africa | 37 | 37 |
| South Korea | 55 | 55 |
| Spain | 26 | 26 |
| Sweden | 27 | 27 |
| Switzerland | 28 | 28 |
| Togo | 91 | 38 |
| Trinidad and Tobago | 103 | 42 |
| Tunisia | 38 | 39 |
| Turkey | 29 | 29 |
| USA | 41 | 43 |
| Ukraine | 30 | 30 |
| Uruguay | 49 | 51 |
| Uzbekistan | 106 | 66 |
| Venezuela | 50 | 64 |
| Wales | 31 | 31 |
| Zambia | 92 | — |
| Zimbabwe | — | 97 |
