# Brief para escribir el código: conversor WE9 → PES6 (.exe en Python)

Este brief es para **quien escriba el código** (una persona o un modelo). Léelo entero antes de empezar. Complementa a `PROYECTO_conversor_we9_pes6.md`, que explica el formato y la lógica y es la **fuente de verdad**: si algo de este brief parece contradecirlo, gana el documento de proyecto y hay que avisar de la contradicción.

---

## 1. Qué hay que entregar

1. **Código fuente** en Python, modular, con comentarios en español.
2. **Un `.exe` para Windows** (PyInstaller) con interfaz de línea de comandos y una ventana mínima (tkinter) para elegir archivos.
3. **Pruebas automáticas** (`pytest`) que reproducen los valores dorados de la sección 8.
4. **`README.md`** corto con uso, requisitos y límites conocidos.

**Alcance: solo la fase 1** (jugadores y plantillas). La apariencia **no** se implementa. No añadas funciones que nadie pidió.

## 2. Reglas de oro (no negociables)

1. **Nunca modificar un archivo de entrada.** La salida va siempre a un archivo nuevo (por defecto en una carpeta `salida/`, con el nombre exacto `KONAMI-WIN32PES6OPT`).
2. **Nunca inventar un offset, una constante o una tabla.** Todo sale del documento de proyecto, de los fuentes Java o de los archivos de referencia. Si falta un dato, **parar y preguntar**.
3. **Verificar antes de escribir y después de escribir.** Si cualquier verificación falla, **no dejar un archivo de salida** y mostrar un error claro.
4. **Determinismo:** mismas entradas, mismo archivo de salida, byte a byte.
5. **Nada de escribir un registro de jugador en bruto** entre juegos. Siempre campo a campo (las posiciones de bits difieren entre WE9 y PES6).
6. **Tocar solo lo permitido:** registros de los jugadores destino, huecos y dorsales de los equipos emparejados, y las 4 banderas de guardado. Un byte cambiado fuera de eso es un error.
7. **No ocultar errores.** Cada anomalía (nacionalidad sin equivalente, jugador sin hueco, nombre recortado) va al informe, no se traga en silencio.

## 3. Stack y empaquetado

- **Python 3.11 o superior**, solo **biblioteca estándar**: `struct`, `csv`, `argparse`, `json`, `hashlib`, `unicodedata`, `pathlib`, `tkinter`. **Sin numpy ni scipy** en el `.exe` (el tamaño y los falsos positivos de antivirus empeoran mucho). Para la asignación 11×11 escribir un **algoritmo húngaro propio** (ver 6.6).
- **Windows 10 o superior.** Probar con rutas con espacios y tildes (por ejemplo `D:\Mis Juegos\PES Edición\...`).
- Empaquetado: `pyinstaller --onefile --name conversor_we9_pes6 src/cli.py` (consola) y una variante `--windowed` para la ventana. Algunos antivirus marcan los `.exe` de PyInstaller como sospechosos; mencionarlo en el README.
- Lectura/escritura de archivos siempre en **binario** (`rb`/`wb`). Los CSV, solo en las pruebas y en la tabla de clubes: `encoding='latin-1'` los de los editores y `utf-8-sig` la tabla de clubes; escribir con `newline=''`.

## 4. Estructura de proyecto sugerida

```
conversor/
  src/
    tablas.py          # GENERADO (ver 5). No editar a mano.
    cripto.py          # capas de cifrado, bloques, checksums (6.1)
    registro.py        # direcciones, lectura/escritura de campos, nombres (6.2)
    jugadores.py       # convertir_jugador, asignacion de huecos (6.3, 6.4)
    equipos.py         # emparejamiento de equipos, clubes (6.5)
    plantillas.py      # plantillas, orden permutado, titulares (6.6)
    conversion.py      # orquesta los pasos 1 a 8 del documento de proyecto
    verificacion.py    # comprobaciones previas y posteriores (6.7)
    informes.py        # reporte_jugadores.csv, reporte_equipos.csv, registro.txt
    cli.py             # argparse
    gui.py             # tkinter minimo
  tools/
    generar_tablas.py  # lee los fuentes Java y escribe tablas.py
  tests/               # pytest (seccion 8)
  README.md
```

## 5. Datos generados (`tablas.py`)

`tools/generar_tablas.py` debe **leer los fuentes Java** (los ZIP `PES-Editor-5-master` y `PESEditor-master` del usuario) y generar `tablas.py`. **No teclear las tablas a mano.**

| Dato | Origen | Cómo extraerlo | Longitud | Huella (`sha256(json.dumps(lista))[:16]`) |
|---|---|---|---|---|
| `KEYPC` (WE9 y PES6, idénticas) | `OptionFile.java`, array `keyPC` | valores `& 0xFF` (Java usa `byte` con signo; admite `Byte.MAX_VALUE`/`MIN_VALUE`) | 256 | `ec24faf2e9f1af5a` |
| `KEY5` (WE9) | `OptionFile.java` de PES-Editor-5, `int[] key` | cada valor **más `1815543808`**, módulo 2³² | 367 | `b89cb36c983aa7a3` |
| `KEY6` (PES6) | `OptionFile.java` de PESEditor, `int[] key` | cada valor módulo 2³² | 446 | `14c5492ce46746c9` |
| Campos de jugador WE9 | `Stats.java` de PES-Editor-5, líneas `this.x = new Stat(this.of, tipo, off, shift, mask, "...")` | expresión regular | 83 | — |
| Campos de jugador PES6 | `Stats.java` de PESEditor, líneas `Stat x = new Stat(tipo, off, shift, mask, "...")` (máscara en decimal o `0x..`) y el bloque `abilitySpecial` (23) | expresión regular | 63 + 23 | — |

Cada huella debe coincidir; **si no coincide, el generador falla**. Las constantes de bloques, direcciones y tablas de campos de los Apéndices A y B del documento de proyecto también se incluyen en `tablas.py` y se **comprueban contra el apéndice**.

Nacionalidades: tabla de nombre → índice por juego (Apéndice B). La conversión es **por nombre normalizado** (NFKD → ASCII → minúsculas → solo `a-z0-9`) con una tabla de alias; si no hay equivalente, `Free Nationality` de PES6 y un aviso en el informe.

## 6. Especificación por módulo

> Los fragmentos siguientes son la **implementación de referencia que funcionó**. Pueden refactorizarse, pero el comportamiento debe ser idéntico: la salida tiene que coincidir con los valores dorados de la sección 8.

### 6.1 `cripto.py`

Configuración por juego (`GAMES`), con los valores del documento de proyecto, sección 4:

```python
GAMES = {
 'pes5': dict(length=1250304, keylen=367, style=5,
              block=[12,5144,9508,14044,36872,657712,803608,822940,969192,1228568,1250316],
              size=[4948,1232,4520,22816,620000,145880,19320,146240,259364,21016],
              c1=1815549477, c2=0x6C371625),
 'pes6': dict(length=1191936, keylen=446, style=6,
              block=[12,5144,9544,14288,37116,657956,751472,763804,911144,1170520],
              size=[4844,1268,4730,22816,620000,93501,12320,147328,259364,21032],
              c1=0x7AB3684C, c2=0x7AB3684C),
}   # a cada una se le añaden keypc y key desde tablas.py
```

Implementación de referencia:

```python
def xor_pc(buf, g):
    kp = g['keypc']; return bytearray(b ^ kp[i & 255] for i, b in enumerate(buf))

def checksums(buf, g):
    out = []
    for i in range(10):
        w, _ = _words(buf, g['block'][i], g['size'][i])
        out.append(sum(w) & 0xFFFFFFFF)
    return out

def stored_checksums(buf, g):
    return [struct.unpack_from('<I', buf, g['block'][i]-8)[0] for i in range(10)]

def decrypt(buf, g):
    key, kl, c1, c2 = g['key'], g['keylen'], g['c1'], g['c2']
    for i in range(1, 10):
        start, size = g['block'][i], g['size'][i]
        w, n = _words(buf, start, size)
        for idx in range(n):
            p = (((w[idx] - key[idx % kl]) + c1) & 0xFFFFFFFF) ^ c2
            w[idx] = p
        struct.pack_into('<%dI' % n, buf, start, *w)

def encrypt(buf, g):
    key, kl, c1, c2 = g['key'], g['keylen'], g['c1'], g['c2']
    for i in range(1, 10):
        start, size = g['block'][i], g['size'][i]
        w, n = _words(buf, start, size)
        for idx in range(n):
            if g['style'] == 5:   # n = key + ((m ^ c2) - c1)
                c = (key[idx % kl] + ((w[idx] ^ c2) - c1)) & 0xFFFFFFFF
            else:                 # PES6: c = key + ((p ^ c2) - c2)
                c = (key[idx % kl] + ((w[idx] ^ c2) - c2)) & 0xFFFFFFFF
            w[idx] = c
        struct.pack_into('<%dI' % n, buf, start, *w)

def set_checksums(buf, g):
    cs = checksums(buf, g)
    for i in range(10):
        struct.pack_into('<I', buf, g['block'][i]-8, cs[i])

def load_pc(path, game):
    g = GAMES[game]
    raw = open(path, 'rb').read()
    assert len(raw) == g['length'], (len(raw), g['length'])
    buf = xor_pc(raw, g)
    ok = checksums(buf, g) == stored_checksums(buf, g)
    decrypt(buf, g)
    return buf, ok, g

def save_pc(buf, g):
    b = bytearray(buf); encrypt(b, g); set_checksums(b, g)
    return bytes(xor_pc(b, g))
```

Reglas:
- `load_pc` devuelve `(buffer, checksums_ok, config)`. **Si `checksums_ok` es falso, el conversor aborta.**
- `save_pc` cifra una **copia** y devuelve los bytes finales. El buffer en claro no se altera.
- Antes de usar cualquier archivo, comprobar `len(raw) == length`.

### 6.2 `registro.py`

```python
def rec(game, idx):
    L=LAYOUT[game]
    return L['base']+idx*124 if idx<FIRST_EDIT else L['baseE']+(idx-FIRST_EDIT)*124

def getraw(buf, game, idx, t):
    typ,off,sh,mask=t; a=rec(game,idx)+48+off
    return ((((buf[a]<<8)|buf[a-1])>>sh)&mask)

def setraw(buf, game, idx, t, v):
    typ,off,sh,mask=t; a=rec(game,idx)+48+off
    old=(buf[a]<<8)|buf[a-1]; old&=0xFFFF&~(mask<<sh)
    v=((v&mask)<<sh)|old
    buf[a-1]=v&0xFF; buf[a]=(v>>8)&0xFF

def getname(buf, game, idx):
    a=rec(game,idx); raw=bytes(buf[a:a+32]); i=0
    while i<30 and not (raw[i]==0 and raw[i+1]==0): i+=2
    return raw[:i].decode('utf-16le')

def setname(buf, game, idx, name):
    a=rec(game,idx); b=name.encode('utf-16le')[:30]
    buf[a:a+32]=b+b'\x00'*(32-len(b))

def squad_addr(game, t):
    q = SQ[game]
    if t < q['n23']:
        return q['slot23']+t*46, q['num23']+t*23, 23
    c = t-q['n23']
    return q['slot32']+c*64, q['num32']+c*32, 32

def get_squad(buf, game, t):
    sl, nm, size = squad_addr(game, t)
    ids = [buf[sl+2*k] | (buf[sl+2*k+1] << 8) for k in range(size)]
    nums = [buf[nm+k] for k in range(size)]
    return ids, nums

def set_squad(buf, game, t, ids, nums):
    sl, nm, size = squad_addr(game, t)
    assert len(ids) == size and len(nums) == size
    for k in range(size):
        buf[sl+2*k] = ids[k] & 0xFF; buf[sl+2*k+1] = (ids[k] >> 8) & 0xFF
        buf[nm+k] = nums[k] & 0xFF

def f5_order(buf, t):     # 32 bytes de orden del plantel
    a = 670512 + 628*f5_idx(t) + 6232
    return list(buf[a:a+32])

def f6_pos(buf, t, alt=0):
    a = 677202 + 138 + 364*t + alt*82
    return list(buf[a:a+11])
```

Constantes: `FIRST_EDIT = 32768`; `LAYOUT = {'pes5': dict(base=36872, baseE=14044), 'pes6': dict(base=37116, baseE=14288)}`; `SQ` (direcciones de plantillas, documento de proyecto 6.2).

Notas:
- `getname`/`setname` trabajan con **UTF-16LE**, 32 bytes, y cortan en el primer `0000` alineado. El nombre se limita a 15 caracteres.
- Un nombre vacío significa **jugador inexistente**.
- `f5_order` solo vale para equipos `t < 64` o `74 ≤ t < 212`.

### 6.3 `jugadores.py`: convertir un jugador

```python
def convert_player(b5, idx5, b6, idx6, notes):
    """Copia nombre, nombre de camiseta, stats y datos de un jugador de WE9 a un hueco de PES6.
    No toca la apariencia ni nada que no este listado aqui."""
    name = getname(b5, 'pes5', idx5)
    setname(b6, 'pes6', idx6, name[:15])
    a5, a6 = rec('pes5', idx5), rec('pes6', idx6)
    shirt = bytes(b5[a5+32:a5+48])
    if not shirt.strip(b'\x00'):
        s = ascii_shirt(name).encode('ascii'); shirt = s + b'\x00'*(16-len(s))
    b6[a6+32:a6+48] = shirt
    for c in ALLCOLS:
        t5, t6 = T5[c], T6[c]
        v = getraw(b5, 'pes5', idx5, t5)
        if c == 'NATIONALITY':
            nm = NAT5.get(v, '?')
            if nm in NAT6_INV: v = NAT6_INV[nm]
            else:
                v = NAT6_FREE; notes.append(f'{name}: nacionalidad {nm} no existe en PES6 -> Free Nationality')
        elif c == 'REGISTERED POSITION' and v == 13:
            v = 12
        setraw(b6, 'pes6', idx6, t6, v)
    setraw(b6, 'pes6', idx6, CALLNAME, 0xCDCD)
    for fl in (FLAG_NAME, FLAG_SHIRT, FLAG_CALL, FLAG_ABIL):
        setraw(b6, 'pes6', idx6, fl, 1)
    return name
```

Detalles que el código de referencia da por hechos y hay que respetar:
- `ALLCOLS` es la lista canónica de 77 columnas (46 base + 23 especiales + 8 otras) del Apéndice A. `T5[c]` y `T6[c]` son las tuplas `(tipo, off, shift, máscara)` de cada juego.
- La nacionalidad se convierte **por nombre**; `NAT5`/`NAT6` son los diccionarios índice → nombre.
- `REGISTERED POSITION == 13` pasa a 12.
- Tras `convertir_jugador`, el flujo principal pone además `faceType = 0` y `face = 0`.
- Si el nombre de camiseta de origen está vacío, se genera con `ascii_shirt` (NFKD, ASCII, mayúsculas, 15 caracteres).

### 6.4 Asignación de huecos (`jugadores.py`)

Seguir **exactamente** el paso 5 del documento de proyecto. Puntos delicados:
- Los conjuntos `R`, `P`, `Q` se calculan **antes** de escribir nada.
- Iterar los índices **en orden ascendente** (determinismo).
- `LIMITE = 4413`. Los índices de PES6 `≥ 4414` y `< 32768` no se escriben nunca.
- Los editados (`≥ 32768`) usan identidad.
- El conjunto de huecos libres para pendientes **excluye** los índices que son identidad de otro jugador de `R`.
- Registrar en el informe `slotmap` completo y los descartados.

### 6.5 `equipos.py`: emparejamiento

- Selecciones 0..56: **país dominante** de la plantilla (nacionalidad más frecuente, leída con la tabla de cada juego). Comprobar que los 57 países dominantes son distintos en cada juego, o abortar.
- Clásicos, Japón y editados: tablas fijas del documento de proyecto 6.1 y paso 2.
- Clubes: leer el CSV `mapeo_equipos_we9_a_pes6.csv` (columnas `liga, club_WE9, equipo_WE9, nombre_WE9, club_PES6, equipo_PES6, nombre_PES6, criterio`) y usar **`equipo_WE9` → `equipo_PES6`**. Si el CSV no se indica, generarlo con el procedimiento de la sección 8 del documento de proyecto (bloques de liga, primero por nombre normalizado, luego por posición).
- **Validar:** sin destinos repetidos ni orígenes repetidos, y cada índice dentro de su rango.

### 6.6 `plantillas.py`

1. **Plantilla efectiva de WE9:** aplicar el orden permutado (documento 6.3) antes de traducir. Es un error clásico ignorarlo.
2. **Traducir** cada índice con `slotmap`; lo no mapeado → 0, y su dorsal → 255.
3. **Reordenar los 11 titulares** solo si el equipo destino tiene formación (`t6 < 64` o `73 ≤ t6 < 213`). Posiciones de la formación 0 con `f6_pos`; rol por posición con la tabla del documento 6.4; coste según el documento de proyecto, paso 7.
4. **Algoritmo húngaro** propio, O(n³), 11×11, con costes `float`. Los empates pueden resolverse distinto que en `scipy.optimize.linear_sum_assignment`; por eso las pruebas comparan **el coste total por equipo** y no solo el hash (ver 8).
5. Los jugadores y sus dorsales se mueven **juntos**. El banquillo conserva el orden.
6. `set_squad` escribe los 2·N bytes de huecos y los N dorsales.

### 6.7 `verificacion.py`

**Antes** de escribir:
- Tamaños exactos y checksums válidos de origen y destino.
- Tablas de claves con la longitud y la huella correctas.
- `team_map` sin duplicados y con índices válidos.
- Descifrar y volver a cifrar el archivo de destino sin cambios debe dar **el mismo archivo** (prueba de ida y vuelta en memoria).

**Después** de escribir (releer el archivo de salida con `load_pc`):
- Checksums válidos.
- Datos descifrados idénticos al buffer, **salvo los 4 bytes de cada uno de los 10 checksums**.
- Para cada equipo emparejado: los nombres de su plantilla (recortados a 15) coinciden con los de WE9, y no hay jugadores repetidos dentro del equipo.
- Cada jugador escrito: releer todos sus campos y comparar con el origen (nacionalidad por nombre, regPos 13→12).
- **Ningún byte cambiado fuera del conjunto permitido** (regla de oro 6).

Si algo falla: borrar el archivo de salida y salir con código distinto de cero.

## 7. Trampas conocidas (cada una ya dio guerra)

1. **Precedencia en Java:** `m - key + C1 ^ C2` es `((m - key) + C1) ^ C2`. Enmascarar a 32 bits tras cada suma y resta.
2. **Bytes con signo:** en Java `byte` va de -128 a 127. En Python, `& 0xFF`.
3. **El bloque 5 de PES6 mide 93501**, no es múltiplo de 4: usar `tamaño // 4` palabras.
4. **El checksum se calcula sobre datos cifrados** y antes de la capa XOR final. Al cargar, se valida después de deshacer el XOR y antes de descifrar.
5. **El bloque 0 no se cifra** (se descifra del 1 al 9), pero sí tiene checksum.
6. **La tabla `KEY5` lleva un desplazamiento de `+1815543808`**; la `KEY6` no.
7. **El índice de palabra para la clave es relativo al bloque**, no al archivo.
8. **Los campos se leen con dos bytes** (`a-1` bajo, `a` alto). Un campo de 7 bits con shift 7 cruza el límite de byte.
9. **Orden de plantilla permutado en WE9** (81 equipos): aplicarlo siempre.
10. **Índices de editados:** `32768 + k`; su dirección usa `baseE`, no `base`.
11. **Nombres vacíos:** los editores muestran `<L n>` o `<Edited n>` para jugadores sin nombre. Sin nombre = no existe.
12. **Nombres con caracteres especiales:** copiar las unidades UTF-16 sin transformar. Hay tres casos conocidos en WE9 (índices 998, 2112 y 3548) donde el CSV muestra Latin-1 y el binario usa códigos propios del juego. **No tratarlos ni «corregirlos»** en fase 1.
13. **Los CSV de los editores ordenan por índice** (regulares 1..N y luego editados), sin columna de ID. No usar los CSV como fuente de datos del conversor; son solo para pruebas.
14. **Las banderas de guardado** (`data[45]`, `[46]`, `[5938]`, `[5939]` en PES6) hay que ponerlas en 1 antes de cifrar.
15. **No tocar los índices de jugador ≥ 4414** de PES6 (Liga Máster, tienda, jóvenes, veteranos, sin usar).
16. **No usar el nombre del archivo del usuario para decidir nada**: el destino se escribe siempre con el nombre exacto que el juego espera.
17. **Cuidado al subir archivos con el mismo nombre:** el conversor no debe asumir que la entrada y la salida difieren por el nombre; compararlas por ruta.

## 8. Pruebas obligatorias y valores dorados

Archivos de referencia (sus MD5 están en el documento de proyecto, sección 3): `KONAMI-WIN32WE9UOPT`, `KONAMI-WIN32PES6OPT`, `pes5.csv`, `pes6.csv`, `mapeo_equipos_we9_a_pes6.csv`.

### 8.1 Pruebas de cripto
- Ida y vuelta de `KONAMI-WIN32WE9UOPT` y `KONAMI-WIN32PES6OPT`: `save_pc(load_pc(x)) == x`, byte a byte, y `checksums_ok == True`.
- Longitud de `KEYPC`, `KEY5`, `KEY6` = 256, 367, 446 y huellas de la sección 5.

### 8.2 Pruebas de lectura contra los CSV
- WE9: 5183 jugadores (índices 1..4999 y 32768..32951). PES6: 4967 (1..4783 y 32768..32951).
- Todas las columnas numéricas decodificadas coinciden con el CSV: tipos 0, 1, 2 y 5 con sus desplazamientos. Las categóricas se comparan con la etiqueta (`R/L/B`, `C/B/A`, estilos como `raw+1`).
- Nombres: **0** diferencias en PES6; en WE9, **exactamente 3** (índices 998, 2112 y 3548, ver trampa 12). Hay además jugadores de WE9 con nombre vacío que el CSV muestra como `<L n>`.
- Ejemplo: WE9, índice 1: `Schranz`, ATTACK 30, DEFENSE 80.

### 8.3 Prueba de 10 jugadores
Pares `(índice WE9 → índice PES6)`: `32768+i → 1+i` para `i = 0..4` y `32768+5+i → 32768+i` para `i = 0..4`. Nombres esperados, en orden: `Catulo`, `Nogoles`, `Paul Catulo`, `Chupame`, `Javito`, `Jabali`, `Arbustito`, `Terry`, `Utanene`, `D.Carlos`. Los 5 primeros sustituyen a `Macho`, `Scharner`, `Stranzl`, `Dober` y `Pogatetz`. Tras escribirlos: 0 diferencias de campos y **ningún byte distinto fuera de los 10 registros** (más checksums y banderas).

### 8.4 Prueba de conversión completa (regresión)
Con las cinco entradas de referencia y los parámetros por defecto:

| Dato | Valor esperado |
|---|---|
| Equipos emparejados | 207 |
| Selecciones omitidas (WE9) | Marruecos (34), Senegal (36), Venezuela (50), China (51) |
| Selecciones de PES6 intactas | Angola (32), Ghana (35), Togo (38), Trinidad y Tobago (42) |
| `R` (referenciados) | 4315 |
| `Q` (con nombre sin equipo) | 764 |
| Descartados sin hueco | 620 |
| Jugadores transferidos | 4459 |
| Protegidos en PES6 | 138 |
| Movidos a otro hueco | 287 |
| Avisos de nacionalidad | 7 |
| Titulares fuera de rol / reordenados | 413 / 2178 (equipos reordenados: 198) |
| Errores de verificación; bytes fuera de lo permitido | 0; 0 |

**MD5 de referencia de la salida:** `88bd2e72a982e55123dd22dd72980178`.
Ese hash se obtuvo con `scipy.optimize.linear_sum_assignment` (scipy 1.17.1). Con un húngaro propio, los empates pueden resolverse distinto y el hash cambiar. Por eso la prueba **principal** es: (a) los conteos de la tabla, (b) el coste total de la asignación **igual** al de scipy en cada equipo, y (c) todos los bytes fuera de las plantillas de titulares idénticos a los de la salida de referencia. El hash completo solo se exige si se usa scipy en las pruebas.

### 8.5 Pruebas negativas
- Archivo de tamaño incorrecto → error claro y sin salida.
- Un byte alterado en un bloque (checksum inválido) → el conversor lo detecta y aborta.
- Tabla de clubes con un destino repetido → aborta.
- Origen y destino con la misma ruta → aborta.

## 9. Interfaz

### 9.1 Línea de comandos
```
conversor_we9_pes6.exe --origen KONAMI-WIN32WE9UOPT --destino KONAMI-WIN32PES6OPT --clubes mapeo_equipos_we9_a_pes6.csv --salida .\salida [--solo-verificar] [--sin-informes]
```
- `--solo-verificar`: hace todo en memoria y los informes, **sin escribir** el archivo de salida (modo de prueba).
- Código de salida `0` solo si todo se verificó.
- Mensajes en español, sin trazas de Python: errores previstos con texto claro; errores imprevistos al `registro.txt` con la traza.

### 9.2 Ventana
Cuatro selectores (origen, destino, tabla de clubes, carpeta de salida), un botón «Verificar» y otro «Convertir», un cuadro de texto con el registro y un aviso fijo: *«Haz copia de seguridad de tu option file antes de usar el resultado.»* No debe congelarse durante la conversión (hilo aparte).

### 9.3 Archivos de salida
- `salida/KONAMI-WIN32PES6OPT`
- `salida/reporte_jugadores.csv` (`indice_WE9, nombre, estado, indice_PES6`, estado: transferido / transferido en otro hueco / no transferido por falta de hueco)
- `salida/reporte_equipos.csv` (`equipo_WE9, equipo_PES6, descripcion, criterio`)
- `salida/registro.txt` (resumen con los conteos de 8.4, avisos y versión del programa)

## 10. Orden de trabajo (con una comprobación al final de cada paso)

1. `generar_tablas.py` + huellas. ✔ si las 3 huellas coinciden.
2. `cripto.py`. ✔ ida y vuelta idéntica de los dos option files.
3. `registro.py` + lectura. ✔ pruebas 8.2.
4. `convertir_jugador` y prueba de 10 jugadores. ✔ 8.3.
5. Emparejamiento de equipos. ✔ 207 pares, sin duplicados.
6. Asignación de huecos. ✔ conteos de 8.4 (transferidos, descartados, protegidos, movidos).
7. Plantillas y titulares (húngaro propio). ✔ coste total igual al de referencia.
8. Verificación completa y informes. ✔ 0 errores y 0 bytes fuera de lo permitido.
9. CLI, ventana, PyInstaller. ✔ prueba en una carpeta con espacios y tildes.
10. README y revisión final con la lista de la sección 12.

## 11. Fuera de alcance (no hacer)

- Apariencia, escudos, camisetas, nombres de clubes, formaciones de WE9, capitanes y lanzadores.
- Liga Máster y tienda.
- Otros juegos (PES5 europeo, WE9LE), otras plataformas (PS2, Xbox), formatos `.psu`/`.max`.
- Ningún «arreglo automático» de caracteres especiales.
- No editar nunca el option file de entrada ni escribir fuera de la carpeta de salida.

## 12. Lista final antes de entregar

- [ ] Las 3 huellas de claves coinciden.
- [ ] Ida y vuelta idéntica de los dos option files de referencia.
- [ ] Lectura: 0 diferencias en columnas numéricas (WE9 y PES6) y exactamente 3 nombres distintos en WE9.
- [ ] Prueba de 10 jugadores correcta.
- [ ] Conteos de 8.4 exactos; coste de asignación igual al de referencia.
- [ ] 0 bytes cambiados fuera de lo permitido.
- [ ] Pruebas negativas pasan (8.5).
- [ ] La salida se escribe con el nombre exacto `KONAMI-WIN32PES6OPT` y nunca sobre la entrada.
- [ ] El `.exe` funciona en una carpeta con espacios y tildes y no se congela.
- [ ] El README declara los límites (apariencia no incluida, 620 jugadores sin hueco, selecciones sin pareja, titulares fuera de rol).
- [ ] Todo punto que el brief no cubra se **preguntó**, no se improvisó.
