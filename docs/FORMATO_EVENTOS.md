# Formato de la lista de eventos en vivo

## Dónde está

`lista = [PTR] + 0x14 + 0x12D8`

| Exe | PTR | Último toque (u8) | Fase (u8) |
|---|---|---|---|
| WE9LEK.exe (crack limpio / Kingsley V5.5) | `0xF773EC` → en partido la lista quedó en `0x3B0D530` | `0x3B68AC3` | `0xF7122D` |
| we9.exe (nocd / Kingsley V5.5) | `0xFF694C` | `0x3BE0F83` | `0xFF078D` |
| PES6.exe | lo encuentra `espia.py diagnostico` | | |

En el código del juego, `getter = mov eax,[PTR]; add eax,0x14; ret` (WE9LE `0x6A5350`). Lo llama
`0x7BD880` (`call getter; add eax,0x12D8; ret` = primer registro). El siguiente registro lo calcula `0x7BD890`.

## Registros

Son de largo variable y la lista **termina en un byte 0**:

| Código (byte 0) | Largo |
|---|---|
| `0x0B`–`0x10` | 8 bytes |
| `0x11`–`0x1A` | 4 + 4 × byte[3] |
| resto | 4 bytes |

Registro corto: `[código, (equipo << 7) | jugador, minuto, flags]`
- equipo: 0 = local, 1 = visitante. jugador = índice del que está en cancha (no es el ID del option file).

| Código | Qué es | Estado |
|---|---|---|
| `0x01` | saque inicial | confirmado |
| `0x03` | **falta**. flags `0x80` = falta común; otros valores (`0x82`, `0x10`…) = con tarjeta u otra cosa | confirmado (falta). Los flags exactos de tarjeta están por confirmar |
| `0x08` | tiro libre (suele venir justo después de una falta) | probable |
| `0x05` / `0x06` | laterales / saques | probable |
| `0x0B` | pase / posesión, 8 bytes: `[0B, pasador, ?, ?, 00, receptor, ?, ?]` | probable |
| `0x16` / `0x18` / `0x19` | tiros con trayectoria (largo variable) | probable |

Para la pantalla de resumen, el juego convierte códigos con `0x6A5A10`: 3 → `0x25/0x26/0x28/0x29/0x2B` según flags
(`0x29` = falta, `0x27` = amarilla probable, `0x01` = tiro, `0x1B` = córner izq., `0x2C` = saque inicial). Leer esa
función es el atajo para terminar de nombrar los códigos.

## Otros datos útiles (WE9LE)

- **Fase del partido** `0xF7122D`: 1 = en juego, 2 = preparar pelota parada, 3/9 = laterales/saques,
  6 = falta/tiro libre. La escribe `0x5E0FED`.
- **Último que tocó la pelota** `0x3B68AC3`: 0–10 local, 11–21 visitante (la escribe siempre `0x5F0184`).
- **Jugadores en cancha**: 23 estructuras de `0x290` bytes desde `0x3B573C0` (+0x40 equipo, +0x3F dorsal/índice).
- **Árbitro**: estado en `0x3B17300` (+2 gravedad, +4 infractor, +5 víctima).
- **Cola cruda de eventos**: `0x3B0B8E4` (100 × 24 bytes, índice en `0x3B0B8BE`, tipo en +6).

Más detalle y la historia de cómo se encontró cada cosa: [MAPA_MEMORIA_WE9LE.md](MAPA_MEMORIA_WE9LE.md).

## Salida JSONL de `espia.py vivo --jsonl`

```json
{"t": 1760390000.12, "codigo": 3, "tipo": "falta", "confirmado": true, "equipo": "visitante", "jugador": 5, "minuto": 12, "flags": 128, "crudo": "03 85 0c 80", "tarjeta_u_otro": false}
{"t": 1760390001.40, "tipo": "fase", "fase": 6, "nombre": "falta_tiro_libre"}
{"t": 1760390009.88, "tipo": "toque", "jugador": 7, "equipo": "local"}
```

`crudo` va siempre, así se puede reinterpretar un partido viejo cuando se confirme un código nuevo.
