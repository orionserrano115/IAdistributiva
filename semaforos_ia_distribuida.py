"""
Semáforos con IA Distribuida - Cuadra de 3 semáforos
=====================================================
Cada semáforo es un AGENTE autónomo que:
  - Percibe el tráfico local (carros esperando)
  - Comunica su estado a los vecinos
  - Toma decisiones coordinadas sin controlador central

Teclas:
  ESPACIO  - Pausar / Reanudar
  A        - Agregar tráfico manual al semáforo 1
  S        - Agregar tráfico manual al semáforo 2
  D        - Agregar tráfico manual al semáforo 3
  R        - Reiniciar simulación
  ESC      - Salir
"""

import pygame
import sys
import random
import math
import time
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


# ─────────────────────────────────────────────
#  Constantes de pantalla y colores
# ─────────────────────────────────────────────
WIDTH, HEIGHT = 1100, 700
FPS = 60

# Colores
BG          = (18,  20,  26)
ROAD        = (40,  42,  54)
LANE        = (60,  63,  75)
WHITE       = (255, 255, 255)
GRAY        = (130, 135, 150)
DARK_GRAY   = (55,  58,  68)
PANEL_BG    = (25,  28,  38)
PANEL_BORDER= (60,  65,  80)

RED         = (220, 60,  60)
YELLOW      = (230, 185, 40)
GREEN       = (50,  200, 100)
RED_DIM     = (80,  25,  25)
YELLOW_DIM  = (80,  65,  15)
GREEN_DIM   = (20,  70,  35)

BLUE        = (60,  130, 220)
CYAN        = (40,  200, 220)
ORANGE      = (230, 130, 40)
PURPLE      = (160, 80,  220)

CAR_COLORS  = [
    (70, 140, 210), (200, 80, 80), (80, 190, 130),
    (210, 160, 50), (160, 80, 210), (200, 120, 60),
]


# ─────────────────────────────────────────────
#  Estado de semáforo
# ─────────────────────────────────────────────
class Phase(Enum):
    RED    = "rojo"
    YELLOW = "amarillo"
    GREEN  = "verde"


# ─────────────────────────────────────────────
#  Carro
# ─────────────────────────────────────────────
@dataclass
class Car:
    x: float
    y: float
    speed: float
    color: tuple
    width: int = 28
    height: int = 16
    stopped: bool = False
    passed: bool = False
    alpha: int = 255

    def draw(self, surface):
        if self.passed:
            return
        s = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        pygame.draw.rect(s, (*self.color, self.alpha), (0, 0, self.width, self.height), border_radius=4)
        # Ventanas
        wc = (min(255, self.color[0]+60), min(255, self.color[1]+60), min(255, self.color[2]+80), self.alpha)
        pygame.draw.rect(s, wc, (4, 3, 8, 10), border_radius=2)
        pygame.draw.rect(s, wc, (14, 3, 8, 10), border_radius=2)
        surface.blit(s, (int(self.x - self.width//2), int(self.y - self.height//2)))


# ─────────────────────────────────────────────
#  Agente Semáforo (nodo IA distribuida)
# ─────────────────────────────────────────────
class TrafficAgent:
    """
    Agente autónomo de semáforo.
    Implementa IA distribuida mediante:
      1. Percepción local  → cuenta carros esperando
      2. Comunicación      → comparte estado con vecinos
      3. Decisión adaptiva → ajusta tiempos según congestión
    """

    # Tiempos base (segundos)
    BASE_GREEN  = 5.0
    BASE_YELLOW = 1.5
    BASE_RED    = 6.0
    MIN_GREEN   = 3.0
    MAX_GREEN   = 12.0

    def __init__(self, agent_id: int, x: int, y: int, name: str):
        self.id        = agent_id
        self.x         = x
        self.y         = y
        self.name      = name
        self.phase     = Phase.RED
        self.neighbors: List["TrafficAgent"] = []

        # Temporizador
        self.phase_start = time.time()
        self.phase_duration = self.BASE_RED * (agent_id * 0.4 + 0.6)  # offset inicial

        # Cola de tráfico
        self.cars: List[Car] = []
        self.passed_count  = 0
        self.waiting_count = 0

        # Métricas IA
        self.congestion       = 0.0   # 0–1
        self.adaptive_bonus   = 0.0   # segundos extra de verde ganados
        self.messages_sent    = 0
        self.messages_recv    = 0
        self.last_neighbor_states: dict = {}

        # Posición de la línea de parada y zona de paso
        self.stop_line_x = x + 25
        self.spawn_x     = x - 280

        # Historial de fases para gráfica
        self.phase_history: List[tuple] = []  # (timestamp, phase)
        self.phase_history.append((time.time(), self.phase))

        # Offset de carril vertical
        self.lane_y = y

    def add_neighbor(self, agent: "TrafficAgent"):
        self.neighbors.append(agent)

    def spawn_car(self):
        """Genera un carro nuevo en el carril."""
        if len(self.cars) >= 8:
            return
        # Posición detrás del último carro
        last_x = min((c.x for c in self.cars if not c.passed), default=self.stop_line_x + 20)
        new_x = min(last_x - 40, self.spawn_x)
        if new_x < 50:
            return
        car = Car(
            x=new_x,
            y=self.lane_y,
            speed=random.uniform(1.5, 2.5),
            color=random.choice(CAR_COLORS),
        )
        self.cars.append(car)

    # ── Percepción ───────────────────────────
    def perceive(self):
        """Cuenta carros esperando en rojo."""
        waiting = [c for c in self.cars if not c.passed and c.x < self.stop_line_x + 5]
        self.waiting_count = len(waiting)
        self.congestion = min(1.0, self.waiting_count / 6.0)

    # ── Comunicación ─────────────────────────
    def broadcast_state(self) -> dict:
        """Mensaje que este agente envía a sus vecinos."""
        msg = {
            "id":          self.id,
            "phase":       self.phase,
            "congestion":  self.congestion,
            "waiting":     self.waiting_count,
            "time_in_phase": time.time() - self.phase_start,
        }
        self.messages_sent += 1
        return msg

    def receive_state(self, msg: dict):
        """Recibe el estado de un vecino."""
        self.last_neighbor_states[msg["id"]] = msg
        self.messages_recv += 1

    # ── Decisión adaptiva ────────────────────
    def _compute_green_duration(self) -> float:
        """
        IA: calcula cuánto tiempo de verde asignar.
        Considera congestión propia y de vecinos.
        """
        # Congestión promedio de vecinos
        neighbor_congestion = 0.0
        if self.last_neighbor_states:
            neighbor_congestion = sum(
                s["congestion"] for s in self.last_neighbor_states.values()
            ) / len(self.last_neighbor_states)

        # Si yo tengo mucho tráfico y vecinos poco → más verde para mí
        priority = self.congestion - 0.5 * neighbor_congestion
        bonus = priority * 6.0   # hasta 6s extra
        bonus = max(-2.0, min(4.0, bonus))
        self.adaptive_bonus = bonus
        return max(self.MIN_GREEN, min(self.MAX_GREEN, self.BASE_GREEN + bonus))

    # ── Ciclo de actualización ───────────────
    def update(self, dt: float, paused: bool):
        if paused:
            return

        now  = time.time()
        elapsed = now - self.phase_start

        # Percepción
        self.perceive()

        # Transición de fase
        if elapsed >= self.phase_duration:
            self._next_phase()

        # Mover carros
        self._move_cars(dt)

        # Spawn aleatorio
        if random.random() < 0.008:
            self.spawn_car()

    def _next_phase(self):
        now = time.time()
        if self.phase == Phase.GREEN:
            self.phase = Phase.YELLOW
            self.phase_duration = self.BASE_YELLOW
        elif self.phase == Phase.YELLOW:
            self.phase = Phase.RED
            self.phase_duration = self.BASE_RED
        elif self.phase == Phase.RED:
            self.phase = Phase.GREEN
            self.phase_duration = self._compute_green_duration()

        self.phase_start = now
        self.phase_history.append((now, self.phase))
        if len(self.phase_history) > 40:
            self.phase_history.pop(0)

    def _move_cars(self, dt: float):
        can_pass = self.phase == Phase.GREEN

        # Limpiar carros que ya salieron
        self.cars = [c for c in self.cars if c.x < WIDTH + 60]

        for i, car in enumerate(self.cars):
            if car.passed:
                car.x += car.speed * 2.5
                continue

            # Posición del carro de adelante
            front_car = None
            for j, other in enumerate(self.cars):
                if j != i and not other.passed and other.x > car.x:
                    if front_car is None or other.x < front_car.x:
                        front_car = other

            gap = (front_car.x - car.width//2 - car.x - car.width//2) if front_car else 999

            # Semáforo en rojo o amarillo → frenar antes de la línea
            if not can_pass and car.x + car.width//2 + car.speed >= self.stop_line_x:
                car.stopped = True
            elif gap < 10:
                car.stopped = True
            else:
                car.stopped = False

            if not car.stopped:
                car.x += car.speed
            
            # Cruzó la línea
            if car.x - car.width//2 > self.stop_line_x + 5 and can_pass:
                car.passed = True
                self.passed_count += 1

    # ── Dibujo ───────────────────────────────
    def draw(self, surface, font_sm, font_md, font_lg):
        self._draw_road_section(surface)
        self._draw_traffic_light(surface, font_lg)
        self._draw_cars(surface)
        self._draw_info_panel(surface, font_sm, font_md)

    def _draw_road_section(self, surface):
        road_h = 60
        pygame.draw.rect(surface, ROAD, (self.spawn_x - 10, self.lane_y - road_h//2, WIDTH, road_h))
        # Línea de parada
        pygame.draw.line(surface, GRAY, (self.stop_line_x, self.lane_y - road_h//2),
                         (self.stop_line_x, self.lane_y + road_h//2), 2)

    def _draw_traffic_light(self, surface, font):
        pole_x = self.x
        pole_top = self.lane_y - 120
        pole_bot = self.lane_y - 28

        # Poste
        pygame.draw.line(surface, GRAY, (pole_x, pole_top), (pole_x, pole_bot), 4)
        pygame.draw.line(surface, GRAY, (pole_x, pole_top), (pole_x + 30, pole_top), 4)

        # Caja del semáforo
        box_x, box_y = pole_x + 15, pole_top - 5
        box_w, box_h = 32, 88
        pygame.draw.rect(surface, DARK_GRAY, (box_x, box_y, box_w, box_h), border_radius=6)
        pygame.draw.rect(surface, GRAY, (box_x, box_y, box_w, box_h), 1, border_radius=6)

        # Luces
        cx = box_x + box_w // 2
        lights = [
            (cx, box_y + 16, RED,    RED_DIM,    Phase.RED),
            (cx, box_y + 44, YELLOW, YELLOW_DIM, Phase.YELLOW),
            (cx, box_y + 72, GREEN,  GREEN_DIM,  Phase.GREEN),
        ]
        for lx, ly, on_color, off_color, phase in lights:
            color = on_color if self.phase == phase else off_color
            pygame.draw.circle(surface, color, (lx, ly), 10)
            if self.phase == phase:
                # Brillo
                glow = pygame.Surface((30, 30), pygame.SRCALPHA)
                pygame.draw.circle(glow, (*color, 60), (15, 15), 15)
                surface.blit(glow, (lx - 15, ly - 15))

        # Nombre del agente
        label = font.render(self.name, True, WHITE)
        surface.blit(label, (pole_x - label.get_width()//2, self.lane_y - 145))

        # Tiempo restante
        elapsed   = time.time() - self.phase_start
        remaining = max(0, self.phase_duration - elapsed)
        timer_col = GREEN if self.phase == Phase.GREEN else (YELLOW if self.phase == Phase.YELLOW else RED)
        timer_txt = font.render(f"{remaining:.1f}s", True, timer_col)
        surface.blit(timer_txt, (box_x + box_w + 5, box_y + 35))

    def _draw_cars(self, surface):
        for car in self.cars:
            car.draw(surface)

    def _draw_info_panel(self, surface, font_sm, font_md):
        px = self.x - 90
        py = self.lane_y + 48
        pw, ph = 180, 130

        # Panel de fondo
        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel.fill((25, 28, 38, 200))
        surface.blit(panel, (px, py))
        pygame.draw.rect(surface, PANEL_BORDER, (px, py, pw, ph), 1, border_radius=4)

        phase_colors = {Phase.RED: RED, Phase.GREEN: GREEN, Phase.YELLOW: YELLOW}
        col = phase_colors[self.phase]

        lines = [
            (f"Fase: {self.phase.value.upper()}",          col),
            (f"Carros esperando: {self.waiting_count}",    WHITE),
            (f"Congestión: {self.congestion*100:.0f}%",    ORANGE if self.congestion > 0.5 else CYAN),
            (f"Bonus verde: {self.adaptive_bonus:+.1f}s",  GREEN if self.adaptive_bonus > 0 else GRAY),
            (f"Pasaron: {self.passed_count}",              CYAN),
            (f"Msgs enviados: {self.messages_sent}",       PURPLE),
        ]
        for i, (text, color) in enumerate(lines):
            surf = font_sm.render(text, True, color)
            surface.blit(surf, (px + 8, py + 6 + i * 19))


# ─────────────────────────────────────────────
#  Coordinador (solo supervisa, NO controla)
# ─────────────────────────────────────────────
class DistributedCoordinator:
    """
    Facilita el intercambio de mensajes entre agentes.
    No toma decisiones → eso lo hace cada agente.
    """
    def __init__(self, agents: List[TrafficAgent]):
        self.agents = agents
        # Conectar vecinos (topología de cadena)
        for i, a in enumerate(agents):
            if i > 0:
                a.add_neighbor(agents[i - 1])
            if i < len(agents) - 1:
                a.add_neighbor(agents[i + 1])

    def exchange_messages(self):
        """Paso de mensajes: cada agente difunde su estado."""
        messages = [a.broadcast_state() for a in self.agents]
        for agent in self.agents:
            for msg in messages:
                if msg["id"] != agent.id:
                    # Solo de vecinos directos
                    if any(n.id == msg["id"] for n in agent.neighbors):
                        agent.receive_state(msg)


# ─────────────────────────────────────────────
#  Panel de mensajes de red
# ─────────────────────────────────────────────
class MessageLog:
    def __init__(self, max_lines=8):
        self.lines: List[tuple] = []   # (text, color, alpha)
        self.max_lines = max_lines
        self.timer = 0

    def add(self, text, color=CYAN):
        self.lines.append([text, color, 255])
        if len(self.lines) > self.max_lines:
            self.lines.pop(0)

    def update(self, dt):
        self.timer += dt
        if self.timer > 0.8:
            self.timer = 0
            if self.lines:
                self.lines[0][2] = max(0, self.lines[0][2] - 30)

    def draw(self, surface, font, x, y, w, h):
        bg = pygame.Surface((w, h), pygame.SRCALPHA)
        bg.fill((20, 22, 32, 210))
        surface.blit(bg, (x, y))
        pygame.draw.rect(surface, PANEL_BORDER, (x, y, w, h), 1, border_radius=4)

        title = font.render("📡 Red de mensajes (IA distribuida)", True, PURPLE)
        surface.blit(title, (x + 8, y + 6))
        pygame.draw.line(surface, PANEL_BORDER, (x, y + 24), (x + w, y + 24), 1)

        for i, (text, color, alpha) in enumerate(self.lines):
            s = font.render(text, True, color)
            s.set_alpha(alpha)
            surface.blit(s, (x + 8, y + 30 + i * 18))


# ─────────────────────────────────────────────
#  Visualización de la red de comunicación
# ─────────────────────────────────────────────
def draw_communication_network(surface, agents: List[TrafficAgent], anim_t: float):
    """Dibuja líneas animadas entre agentes mostrando mensajes."""
    for i in range(len(agents) - 1):
        a1, a2 = agents[i], agents[i + 1]
        x1, y1 = a1.x, a1.lane_y - 80
        x2, y2 = a2.x, a2.lane_y - 80

        # Línea base
        pygame.draw.line(surface, PANEL_BORDER, (x1, y1), (x2, y2), 1)

        # Partículas animadas (pulso de datos)
        for j in range(3):
            t = (anim_t * 0.4 + j * 0.33) % 1.0
            px = x1 + (x2 - x1) * t
            py = y1 + (y2 - y1) * t
            alpha = int(200 * math.sin(math.pi * t))
            dot = pygame.Surface((8, 8), pygame.SRCALPHA)
            pygame.draw.circle(dot, (*PURPLE, alpha), (4, 4), 4)
            surface.blit(dot, (int(px) - 4, int(py) - 4))


# ─────────────────────────────────────────────
#  Gráfica de historial de fases
# ─────────────────────────────────────────────
def draw_phase_timeline(surface, agents, font, x, y, w, h):
    bg = pygame.Surface((w, h), pygame.SRCALPHA)
    bg.fill((20, 22, 32, 210))
    surface.blit(bg, (x, y))
    pygame.draw.rect(surface, PANEL_BORDER, (x, y, w, h), 1, border_radius=4)

    title = font.render("Historial de fases", True, WHITE)
    surface.blit(title, (x + 8, y + 5))

    row_h = (h - 28) // len(agents)
    phase_colors = {Phase.RED: RED, Phase.GREEN: GREEN, Phase.YELLOW: YELLOW}
    now = time.time()

    for i, agent in enumerate(agents):
        ry = y + 22 + i * row_h
        lbl = font.render(f"S{agent.id+1}", True, GRAY)
        surface.blit(lbl, (x + 4, ry + row_h//2 - 7))

        history = agent.phase_history
        if len(history) < 2:
            continue

        window = 30.0  # segundos visibles
        for j in range(len(history) - 1):
            t_start = history[j][0]
            t_end   = history[j+1][0]
            phase   = history[j][1]
            # Normalizar a ventana
            rx_start = (t_start - (now - window)) / window
            rx_end   = (t_end   - (now - window)) / window
            rx_start = max(0, rx_start)
            rx_end   = min(1, rx_end)
            if rx_end <= rx_start:
                continue
            bx = x + 22 + int(rx_start * (w - 28))
            bw = max(1, int((rx_end - rx_start) * (w - 28)))
            color = phase_colors.get(phase, GRAY)
            pygame.draw.rect(surface, color, (bx, ry + 2, bw, row_h - 6), border_radius=2)

        # Fase actual hasta ahora
        last_t, last_phase = history[-1]
        rx_start = (last_t - (now - window)) / window
        rx_end   = 1.0
        rx_start = max(0, rx_start)
        if rx_end > rx_start:
            bx = x + 22 + int(rx_start * (w - 28))
            bw = max(1, int((rx_end - rx_start) * (w - 28)))
            pygame.draw.rect(surface, phase_colors.get(last_phase, GRAY),
                             (bx, ry + 2, bw, row_h - 6), border_radius=2)


# ─────────────────────────────────────────────
#  Simulación principal
# ─────────────────────────────────────────────
def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Semáforos con IA Distribuida — Culebrita Orion")
    clock = pygame.time.Clock()

    font_sm = pygame.font.SysFont("consolas", 13)
    font_md = pygame.font.SysFont("consolas", 15, bold=True)
    font_lg = pygame.font.SysFont("consolas", 14, bold=True)
    font_title = pygame.font.SysFont("consolas", 18, bold=True)

    # ── Crear agentes ──────────────────────────
    lane_y = 300
    agents = [
        TrafficAgent(0, 280,  lane_y, "Agente-1"),
        TrafficAgent(1, 570,  lane_y, "Agente-2"),
        TrafficAgent(2, 860,  lane_y, "Agente-3"),
    ]
    # Offset de carril para no solapar
    agents[0].lane_y = lane_y - 0
    agents[1].lane_y = lane_y + 0
    agents[2].lane_y = lane_y + 0

    # Fases escalonadas para inicio realista
    agents[0].phase = Phase.GREEN;  agents[0].phase_duration = 6.0
    agents[1].phase = Phase.RED;    agents[1].phase_duration = 4.0
    agents[2].phase = Phase.RED;    agents[2].phase_duration = 8.0

    coordinator = DistributedCoordinator(agents)
    message_log = MessageLog()

    # Spawn inicial
    for agent in agents:
        for _ in range(random.randint(2, 4)):
            agent.spawn_car()

    paused    = False
    anim_t    = 0.0
    msg_timer = 0.0
    MSG_INTERVAL = 1.5   # segundos entre intercambios de mensajes

    # ── Bucle principal ────────────────────────
    while True:
        dt = clock.tick(FPS) / 1000.0
        anim_t += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key == pygame.K_r:
                    main(); return
                elif event.key == pygame.K_a:
                    agents[0].spawn_car()
                    message_log.add("[Usuario] Tráfico → Agente-1", YELLOW)
                elif event.key == pygame.K_s:
                    agents[1].spawn_car()
                    message_log.add("[Usuario] Tráfico → Agente-2", YELLOW)
                elif event.key == pygame.K_d:
                    agents[2].spawn_car()
                    message_log.add("[Usuario] Tráfico → Agente-3", YELLOW)

        # ── Intercambio de mensajes IA ──────────
        if not paused:
            msg_timer += dt
            if msg_timer >= MSG_INTERVAL:
                msg_timer = 0
                coordinator.exchange_messages()
                for agent in agents:
                    for nid, state in agent.last_neighbor_states.items():
                        message_log.add(
                            f"S{nid+1}→S{agent.id+1}: cong={state['congestion']*100:.0f}%  "
                            f"esp={state['waiting']}",
                            PURPLE
                        )

        # ── Actualizar agentes ──────────────────
        for agent in agents:
            agent.update(dt, paused)

        message_log.update(dt)

        # ── Dibujo ──────────────────────────────
        screen.fill(BG)

        # Franja de carretera continua
        pygame.draw.rect(screen, ROAD, (0, lane_y - 50, WIDTH, 100))
        # Líneas de carril
        for lx in range(0, WIDTH, 40):
            pygame.draw.rect(screen, LANE, (lx, lane_y - 2, 24, 4), border_radius=2)

        # Red de comunicación animada
        draw_communication_network(screen, agents, anim_t)

        # Agentes
        for agent in agents:
            agent.draw(screen, font_sm, font_md, font_lg)

        # Panel de mensajes
        message_log.draw(screen, font_sm, 10, 10, 520, 185)

        # Historial de fases
        draw_phase_timeline(screen, agents, font_sm, 540, 10, 550, 130)

        # Título y leyenda
        title = font_title.render("IA Distribuida — Coordinación de Semáforos", True, WHITE)
        screen.blit(title, (WIDTH//2 - title.get_width()//2, HEIGHT - 110))

        controls = [
            "ESPACIO: pausar   A/S/D: agregar tráfico   R: reiniciar   ESC: salir",
        ]
        for i, txt in enumerate(controls):
            s = font_sm.render(txt, True, GRAY)
            screen.blit(s, (WIDTH//2 - s.get_width()//2, HEIGHT - 85 + i*18))

        # Leyenda IA
        legend_items = [
            ("●", PURPLE, "Mensaje entre agentes"),
            ("●", CYAN,   "Congestión baja"),
            ("●", ORANGE, "Congestión alta"),
            ("●", GREEN,  "Bonus verde (IA adaptiva)"),
        ]
        lx = 10
        for dot, col, txt in legend_items:
            d = font_sm.render(dot, True, col)
            t = font_sm.render(txt, True, GRAY)
            screen.blit(d, (lx, HEIGHT - 55))
            screen.blit(t, (lx + 14, HEIGHT - 55))
            lx += 14 + t.get_width() + 20

        if paused:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 100))
            screen.blit(overlay, (0, 0))
            p = font_title.render("⏸  PAUSADO", True, YELLOW)
            screen.blit(p, (WIDTH//2 - p.get_width()//2, HEIGHT//2 - 20))

        pygame.display.flip()


if __name__ == "__main__":
    main()
