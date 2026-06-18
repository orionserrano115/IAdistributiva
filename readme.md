# 🚦 Semáforos con IA Distribuida

Simulación visual de una cuadra con 3 semáforos coordinados mediante **inteligencia artificial distribuida**. Cada semáforo es un agente autónomo que percibe su entorno, se comunica con sus vecinos y toma decisiones propias — sin ningún controlador central.

Desarrollado con Python y pygame.

---

## Concepto: ¿qué es la IA distribuida aquí?

En un sistema centralizado, un servidor central decide cuándo cambia cada semáforo. En este proyecto, **no existe ese servidor**. Cada agente:

1. **Percibe** cuántos carros tiene esperando en su carril.
2. **Transmite** su estado (congestión, fase actual, carros en espera) a sus vecinos directos.
3. **Decide** de forma autónoma cuánto tiempo de verde asignarse, usando su propia congestión y la de sus vecinos como entrada.

La coordinación emerge del intercambio de mensajes — no de una entidad que mande sobre las demás.

---

## Requisitos

- Python 3.8 o superior
- pygame

```bash
pip install pygame
```

---

## Cómo ejecutar

```bash
python semaforos_ia_distribuida.py
```

La ventana abre en **1100 × 700 px** a 60 FPS.

---

## Controles

| Tecla     | Acción                              |
|-----------|-------------------------------------|
| `ESPACIO` | Pausar / Reanudar la simulación     |
| `A`       | Agregar un carro al carril del Agente-1 |
| `S`       | Agregar un carro al carril del Agente-2 |
| `D`       | Agregar un carro al carril del Agente-3 |
| `R`       | Reiniciar la simulación             |
| `ESC`     | Salir                               |

---

## Estructura del código

```
semaforos_ia_distribuida.py
│
├── Car                        # Vehículo con movimiento y colisión
├── TrafficAgent               # Agente semáforo (nodo IA)
│   ├── perceive()             #   → mide congestión local
│   ├── broadcast_state()      #   → genera mensaje para vecinos
│   ├── receive_state()        #   → recibe mensajes de vecinos
│   └── _compute_green_duration() # → decisión adaptiva de tiempo verde
├── DistributedCoordinator     # Facilitador de mensajes (no controlador)
├── MessageLog                 # Panel de red en pantalla
├── draw_communication_network # Visualiza pulsos de datos entre agentes
└── draw_phase_timeline        # Historial de fases en tiempo real
```

---

## Lógica adaptiva del agente

Cada vez que un agente pasa a **verde**, calcula su duración así:

```python
priority = congestion_propia - 0.5 * congestion_promedio_vecinos
bonus    = priority * 6.0          # entre -2s y +4s
verde    = clamp(BASE_GREEN + bonus, MIN_GREEN, MAX_GREEN)
#          clamp(5s + bonus, 3s, 12s)
```

Si el agente tiene alta congestión y sus vecinos poca → se gana más verde.
Si sus vecinos están saturados → cede tiempo para no bloquear la red.

---

## Parámetros configurables

Dentro de la clase `TrafficAgent`:

| Constante     | Valor por defecto | Descripción                        |
|---------------|-------------------|------------------------------------|
| `BASE_GREEN`  | `5.0` s           | Tiempo base en verde               |
| `BASE_YELLOW` | `1.5` s           | Duración del amarillo              |
| `BASE_RED`    | `6.0` s           | Tiempo base en rojo                |
| `MIN_GREEN`   | `3.0` s           | Mínimo verde permitido             |
| `MAX_GREEN`   | `12.0` s          | Máximo verde permitido             |

Y en el bucle principal:

| Variable       | Valor | Descripción                              |
|----------------|-------|------------------------------------------|
| `MSG_INTERVAL` | `1.5` s | Cada cuánto intercambian mensajes los agentes |
| `FPS`          | `60`  | Cuadros por segundo                      |

---

## Qué se ve en pantalla

- **Carretera** con 3 semáforos y carros moviéndose en tiempo real.
- **Panel de red** (arriba izquierda): mensajes reales entre agentes con congestión y carros en espera.
- **Historial de fases** (arriba derecha): línea de tiempo de los últimos 30 segundos por agente.
- **Panel por agente** (bajo cada semáforo): fase actual, congestión, bonus de verde y total de carros que pasaron.
- **Partículas animadas** entre semáforos: representan los pulsos de datos de la red distribuida.

---

## Autor

Proyecto **Culebrita Orion** — simulación educativa de IA distribuida aplicada a tráfico urbano.