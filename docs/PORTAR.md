# Cómo mapear cosas nuevas (o portar a otro exe)

Todo se hizo sin Cheat Engine. El instalador oficial de CE 7.7 venía con adware y se descartó. Como respaldo con
interfaz gráfica sirve x64dbg (usar x32dbg: los juegos son de 32 bits).

## Si `diagnostico` dice "NO ENCONTRADA" (por ejemplo en PES6)

1. Probar en el exe de disco: `espia.py diagnostico --exe PES6.exe`. Si el exe está cifrado (SecuROM) no va a
   aparecer nada. Hay que hacerlo con el juego abierto, porque la memoria ya está descifrada.
2. Si sigue sin aparecer, el compilador cambió algún byte. Buscar una versión más laxa de la firma:
   - `lista`: lo más estable es `0F B6 08 83 C1 F5 83 F9 0F 77` (recorrer registros: `movzx ecx,[eax]; add ecx,-0xB; cmp ecx,0xF; ja`).
   - `toque`: el "último toque" se encuentra en vivo con `memscan` (0–21, cambia con cada toque).
   - `fase`: con `memscan`, 1 en juego y 6 al cobrar una falta.
3. Con la dirección encontrada en vivo: `herramientas/vigilar.py <va> --modo escribe --proc PES6.exe --pila 64`
   devuelve la instrucción que la escribe. Con `ctx.py` (sobre un volcado o exe sin cifrar) se arma la firma nueva.
   Después se agrega a `FIRMAS` en `espia.py`.

## Mapear un dato nuevo (ej. alineación → ID de jugador, marcador)

1. **memscan** (estilo Cheat Engine), con el juego en ventana:
   ```
   python herramientas\memscan.py --proc WE9LEK.exe nuevo 0 --tipo u8      (marcador 0)
   ... hacer un gol ...
   python herramientas\memscan.py filtrar 1
   python herramientas\memscan.py cambio igual   (sin cambios entre lecturas)
   python herramientas\memscan.py ver
   ```
2. **vigilar** la dirección candidata: `vigilar.py <va> --modo escribe` → qué instrucción la escribe. Con
   `--modo accede` se ve quién la lee, y con `--modo ejecuta` se ve cuándo corre una rutina. `--al 25-2b` filtra
   por el valor de AL y `--pila N` muestra posibles direcciones de retorno para subir por la cadena de llamadas.
   Se desengancha solo, sin cerrar el juego.
3. **Desensamblar** con `ctx.py <exe> <va>` y buscar usos con `xrefs.py <exe> <va>`.
4. **Fotos etiquetadas** (`we9le_registro.py grabar`): F9 control, F10/F11/F12 eventos. Después `analizar` lista las
   direcciones que suben +1 justo en esos eventos. Sirve cuando no hay valor visible para buscar. Tiene fijas las
   regiones de datos de WE9LE: para otro exe hay que ajustar `REGIONES`.
5. Lo que se encuentra en un exe se traslada a los otros por **secuencia de bytes** (misma lógica, distinta
   dirección). Así se mapeó WE9 desde WE9LE.

## Unidades

256 unidades = 1 metro. Media cancha de largo = 13465 (52,6 m) y de ancho = 8729 (34,1 m).
