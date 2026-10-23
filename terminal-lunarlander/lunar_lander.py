#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 MP LUNAR LANDER  -  simulador de pouso lunar para terminal
 Bilíngue: PORTUGUÊS (PT-BR) / ENGLISH (EN-US), escolhido na tela inicial.
===============================================================================

 DEPENDÊNCIAS
 ------------
   * Python 3.8+
   * Linux / macOS : nenhuma dependência extra (`curses` é da stdlib)
   * Windows       : pip install windows-curses

 EXECUÇÃO
 --------
   python3 lunar_lander.py

 CONTROLES
 ---------
   W / Seta CIMA ........ propulsor principal (freia a queda)
   A D / Setas LAT ...... propulsores laterais (empuxo + inclinação)
   P .................... pausa
   T .................... troca o idioma a qualquer momento
   Q / ESC .............. sair

 ARQUITETURA
 -----------
   1) FONT5 / banner()          -> fonte ASCII 5x5 para títulos
   2) STRINGS / Game.T()        -> internacionalização (pt / en)
   3) Terrain                   -> geração do relevo + plataformas de pouso
   4) Lander                    -> estado físico (pos, vel, tilt, combustível)
   5) Explosion                 -> animação ASCII de destruição
   6) Game.handle_input()       -> entrada não-bloqueante
      Game.update(dt)           -> integração física em tempo real
      Game.render()             -> desenho (erase + refresh, sem flicker)
   7) curses.wrapper + finally  -> terminal sempre restaurado
===============================================================================
"""

import curses
import math
import random
import time

# ---------------------------------------------------------------------------
# CONSTANTES GLOBAIS
# ---------------------------------------------------------------------------

FPS = 30
FRAME_TIME = 1.0 / FPS

# Célula do terminal é ~2x mais alta que larga: usamos isso para que o
# movimento horizontal e as explosões tenham proporção visual correta.
ASPECT = 2.0

MIN_W, MIN_H = 64, 22

# --- Física (unidades = "células verticais"; 1 u/s ~ 1 m/s de telemetria) ---
GRAVITY = 1.62          # aceleração lunar (a real é 1,62 m/s²)
MAIN_THRUST = 4.10      # empuxo do motor principal
SIDE_THRUST = 2.20      # empuxo dos propulsores laterais
FUEL_MAIN = 11.0        # consumo por segundo do motor principal
FUEL_SIDE = 5.0         # consumo por segundo dos laterais
MAX_FALL = 14.0         # velocidade terminal (evita números absurdos)

# --- Tolerâncias de pouso ---------------------------------------------------
SAFE_VY = 2.20          # velocidade vertical máxima no toque
SAFE_VX = 1.20          # velocidade horizontal máxima no toque
SAFE_TILT = 12.0        # inclinação máxima (graus) para a nave estar "ereta"

# --- Atitude (inclinação) ---------------------------------------------------
TILT_RATE = 70.0        # graus/s aplicados pelos propulsores laterais
TILT_DAMP = 2.6         # auto-nivelamento do RCS quando nada é pressionado
TILT_MAX = 45.0

START_LIVES = 3

# Estados da máquina de estados
ST_LANG, ST_BRIEF, ST_PLAY, ST_PAUSE, ST_CRASH, ST_LANDED, ST_GAMEOVER = range(7)


# ---------------------------------------------------------------------------
# 1) FONTE ASCII 5x5 PARA OS TÍTULOS
# ---------------------------------------------------------------------------

GLYPH_H = 5
FONT5 = {
    "A": (" ### ", "#   #", "#####", "#   #", "#   #"),
    "B": ("#### ", "#   #", "#### ", "#   #", "#### "),
    "C": (" ####", "#    ", "#    ", "#    ", " ####"),
    "D": ("#### ", "#   #", "#   #", "#   #", "#### "),
    "E": ("#####", "#    ", "#### ", "#    ", "#####"),
    "F": ("#####", "#    ", "#### ", "#    ", "#    "),
    "G": (" ####", "#    ", "#  ##", "#   #", " ####"),
    "H": ("#   #", "#   #", "#####", "#   #", "#   #"),
    "I": ("#####", "  #  ", "  #  ", "  #  ", "#####"),
    "J": ("    #", "    #", "    #", "#   #", " ### "),
    "K": ("#   #", "#  # ", "###  ", "#  # ", "#   #"),
    "L": ("#    ", "#    ", "#    ", "#    ", "#####"),
    "M": ("#   #", "## ##", "# # #", "#   #", "#   #"),
    "N": ("#   #", "##  #", "# # #", "#  ##", "#   #"),
    "O": (" ### ", "#   #", "#   #", "#   #", " ### "),
    "P": ("#### ", "#   #", "#### ", "#    ", "#    "),
    "Q": (" ### ", "#   #", "# # #", "#  # ", " ## #"),
    "R": ("#### ", "#   #", "#### ", "#  # ", "#   #"),
    "S": (" ####", "#    ", " ### ", "    #", "#### "),
    "T": ("#####", "  #  ", "  #  ", "  #  ", "  #  "),
    "U": ("#   #", "#   #", "#   #", "#   #", " ### "),
    "V": ("#   #", "#   #", "#   #", " # # ", "  #  "),
    "W": ("#   #", "#   #", "# # #", "## ##", "#   #"),
    "X": ("#   #", " # # ", "  #  ", " # # ", "#   #"),
    "Y": ("#   #", " # # ", "  #  ", "  #  ", "  #  "),
    "Z": ("#####", "   # ", "  #  ", " #   ", "#####"),
    " ": ("     ", "     ", "     ", "     ", "     "),
}


def banner(text):
    """Converte texto em 5 linhas de arte ASCII (glifos desconhecidos = espaço)."""
    glyphs = [FONT5.get(c.upper(), FONT5[" "]) for c in text]
    return [" ".join(g[row] for g in glyphs) for row in range(GLYPH_H)]


def banner_width(text):
    return max(0, len(text) * 6 - 1)


# ---------------------------------------------------------------------------
# 2) INTERNACIONALIZAÇÃO
# ---------------------------------------------------------------------------

LANGS = ("pt", "en")

STRINGS = {
    "pt": {
        "title_1":     "LUNAR",
        "title_2":     "LANDER",
        "title_small": "LUNAR LANDER",
        "lang_title":  "IDIOMA / LANGUAGE",
        "lang_1":      "[1]  PORTUGUES  (PT-BR)",
        "lang_2":      "[2]  ENGLISH    (EN-US)",
        "lang_hint":   "Pressione 1 ou 2 para escolher   -   [Q] sair",
        "lang_set":    "IDIOMA: PORTUGUES",
        "brief_title": "INSTRUCOES",
        "sub":         "MODULO LUNAR  -  APOLLO / TERMINAL",
        "help_main":   "W / SETA CIMA .... propulsor principal",
        "help_side":   "A  D / SETAS ..... propulsores laterais",
        "help_pause":  "P .. pausa    T .. idioma    Q .. sair",
        "goal":        "Pouse numa plataforma com velocidade baixa e nave ereta.",
        "limits":      "LIMITES: VY < %.1f   VX < %.1f   INCL < %.0f graus",
        "start":       "[ESPACO] INICIAR DESCIDA",
        "hud_alt":     "ALT",
        "hud_vy":      "VEL-Y",
        "hud_vx":      "VEL-X",
        "hud_tilt":    "INCL",
        "hud_fuel":    "COMB",
        "hud_score":   "PONTOS",
        "hud_lives":   "MODULOS",
        "hud_level":   "MISSAO",
        "hud_wind":    "VENTO",
        "no_fuel":     "COMBUSTIVEL ESGOTADO - SEM CONTROLE!",
        "low_fuel":    "ALERTA: COMBUSTIVEL BAIXO",
        "pause_word":  "PAUSA",
        "pause_title": "PAUSA",
        "pause_help":  "[P] continuar    [Q] sair",
        "ok_title":    "POUSO CONFIRMADO",
        "ok_word":     "SUCESSO",
        "ok_msg":      "Contato! O modulo esta intacto.",
        "b_pad":       "PLATAFORMA %s      base %4d  x%d  = %5d",
        "b_soft":      "POUSO SUAVE (VY %.2f)              = %5d",
        "b_fuel":      "COMBUSTIVEL RESTANTE %3d%%          = %5d",
        "b_total":     "PONTUACAO TOTAL                   = %5d",
        "next":        "[ESPACO] proxima missao (%d)",
        "crash_title": "MODULO PERDIDO",
        "crash_word":  "CRASH",
        "r_fast_v":    "Impacto vertical excessivo: VY %.2f (max %.2f)",
        "r_fast_h":    "Deriva horizontal excessiva: VX %.2f (max %.2f)",
        "r_tilt":      "Modulo tombado: inclinacao %.0f graus (max %.0f)",
        "r_rough":     "Solo irregular - fora da plataforma de pouso.",
        "lives_left":  "MODULOS RESTANTES: %d",
        "retry":       "[ESPACO] tentar novamente",
        "go_title":    "FIM DE MISSAO",
        "go_word":     "GAME OVER",
        "go_msg":      "Nenhum modulo lunar restante.",
        "go_level":    "MISSOES CUMPRIDAS : %d",
        "go_land":     "POUSOS BEM SUCEDIDOS : %d",
        "go_score":    "PONTUACAO FINAL   : %d",
        "go_retry":    "[R] jogar novamente     [Q] sair",
        "too_small":   "Aumente o terminal para pelo menos %dx%d",
        "bye":         "Obrigado por jogar MP LUNAR LANDER!",
    },
    "en": {
        "title_1":     "LUNAR",
        "title_2":     "LANDER",
        "title_small": "LUNAR LANDER",
        "lang_title":  "IDIOMA / LANGUAGE",
        "lang_1":      "[1]  PORTUGUES  (PT-BR)",
        "lang_2":      "[2]  ENGLISH    (EN-US)",
        "lang_hint":   "Press 1 or 2 to choose   -   [Q] quit",
        "lang_set":    "LANGUAGE: ENGLISH",
        "brief_title": "INSTRUCTIONS",
        "sub":         "LUNAR MODULE  -  APOLLO / TERMINAL",
        "help_main":   "W / UP ARROW ..... main thruster",
        "help_side":   "A  D / ARROWS .... lateral thrusters",
        "help_pause":  "P .. pause    T .. language    Q .. quit",
        "goal":        "Land on a pad at low speed with the module upright.",
        "limits":      "LIMITS: VY < %.1f   VX < %.1f   TILT < %.0f degrees",
        "start":       "[SPACE] BEGIN DESCENT",
        "hud_alt":     "ALT",
        "hud_vy":      "V-SPD",
        "hud_vx":      "H-SPD",
        "hud_tilt":    "TILT",
        "hud_fuel":    "FUEL",
        "hud_score":   "SCORE",
        "hud_lives":   "MODULES",
        "hud_level":   "MISSION",
        "hud_wind":    "WIND",
        "no_fuel":     "OUT OF FUEL - NO CONTROL!",
        "low_fuel":    "WARNING: LOW FUEL",
        "pause_word":  "PAUSED",
        "pause_title": "PAUSE",
        "pause_help":  "[P] resume    [Q] quit",
        "ok_title":    "TOUCHDOWN CONFIRMED",
        "ok_word":     "SUCCESS",
        "ok_msg":      "Contact! The module is intact.",
        "b_pad":       "LANDING PAD %s     base %4d  x%d  = %5d",
        "b_soft":      "SOFT LANDING (VY %.2f)             = %5d",
        "b_fuel":      "FUEL REMAINING %3d%%                = %5d",
        "b_total":     "TOTAL SCORE                       = %5d",
        "next":        "[SPACE] next mission (%d)",
        "crash_title": "MODULE LOST",
        "crash_word":  "CRASH",
        "r_fast_v":    "Vertical impact too hard: VY %.2f (max %.2f)",
        "r_fast_h":    "Horizontal drift too high: VX %.2f (max %.2f)",
        "r_tilt":      "Module toppled: tilt %.0f degrees (max %.0f)",
        "r_rough":     "Rough terrain - not a landing pad.",
        "lives_left":  "MODULES LEFT: %d",
        "retry":       "[SPACE] try again",
        "go_title":    "MISSION OVER",
        "go_word":     "GAME OVER",
        "go_msg":      "No lunar modules left.",
        "go_level":    "MISSIONS REACHED  : %d",
        "go_land":     "SUCCESSFUL LANDINGS : %d",
        "go_score":    "FINAL SCORE       : %d",
        "go_retry":    "[R] play again     [Q] quit",
        "too_small":   "Please resize the terminal to at least %dx%d",
        "bye":         "Thanks for playing MP LUNAR LANDER!",
    },
}

LAST_LANG = "pt"


# ---------------------------------------------------------------------------
# 3) TERRENO E PLATAFORMAS
# ---------------------------------------------------------------------------

class Pad:
    """Plataforma de pouso: faixa plana com multiplicador de pontuação."""

    __slots__ = ("x0", "x1", "y", "mult")

    def __init__(self, x0, x1, y, mult):
        self.x0 = x0        # coluna inicial (inclusive)
        self.x1 = x1        # coluna final (inclusive)
        self.y = y          # linha da superfície
        self.mult = mult    # multiplicador (2x, 3x, 5x)

    def contains(self, col):
        return self.x0 <= col <= self.x1

    def label(self):
        return "%dX" % self.mult


class Terrain:
    """
    Relevo lunar: um vetor de alturas (linha da superfície por coluna) gerado
    por passeio aleatório + suavização, com plataformas planas recortadas.
    """

    def __init__(self, w, h, level, rng=random):
        self.w = w
        self.h = h
        self.top_limit = h // 2 + 1          # relevo nunca sobe além disso
        self.bottom = h - 1
        self.height = [0] * w
        self.pads = []
        self._generate(level, rng)

    # --- geração -----------------------------------------------------------
    def _generate(self, level, rng):
        rough = min(0.62, 0.28 + 0.05 * level)      # relevo mais recortado a cada missão
        y = rng.randint(self.bottom - 6, self.bottom - 2)
        for x in range(self.w):
            if rng.random() < rough:
                y += rng.choice((-2, -1, 1, 2))
            y = max(self.top_limit, min(self.bottom, y))
            self.height[x] = y

        for _ in range(2):                           # suavização
            sm = self.height[:]
            for x in range(1, self.w - 1):
                sm[x] = (self.height[x - 1] + self.height[x] * 2 + self.height[x + 1]) // 4
            self.height = sm

        self._carve_pads(level, rng)

    def _carve_pads(self, level, rng):
        """Recorta 3 faixas planas. Quanto mais estreita, maior o multiplicador."""
        specs = [(max(4, 9 - level), 2),
                 (max(3, 7 - level), 3),
                 (max(3, 5 - level), 5)]
        rng.shuffle(specs)
        occupied = []
        margin = 3
        for width, mult in specs:
            for _ in range(80):                      # tenta achar um lugar livre
                x0 = rng.randint(margin, self.w - margin - width - 1)
                x1 = x0 + width - 1
                if any(not (x1 + 4 < a or x0 - 4 > b) for a, b in occupied):
                    continue
                seg = self.height[x0:x1 + 1]
                y = sorted(seg)[len(seg) // 2]       # nivela pela mediana
                y = max(self.top_limit + 2, min(self.bottom - 1, y))
                for x in range(x0, x1 + 1):
                    self.height[x] = y
                occupied.append((x0, x1))
                self.pads.append(Pad(x0, x1, y, mult))
                break

    # --- consultas ---------------------------------------------------------
    def surface(self, col):
        """Linha da superfície na coluna (com clamp nas bordas)."""
        return self.height[max(0, min(self.w - 1, int(col)))]

    def pad_at(self, col):
        for p in self.pads:
            if p.contains(int(col)):
                return p
        return None


# ---------------------------------------------------------------------------
# 4) O MÓDULO LUNAR
# ---------------------------------------------------------------------------

class Lander:
    """
    Estado físico da nave.
      x, y   -> posição (coluna/linha, em float)
      vx, vy -> velocidade (vy > 0 = descendo)
      tilt   -> inclinação em graus (negativo = inclinado à esquerda)
    A nave ocupa 2 linhas (nariz e corpo) e 3 colunas.
    """

    __slots__ = ("x", "y", "vx", "vy", "tilt", "fuel", "fuel_max",
                 "thrust_main", "thrust_side", "alive")

    def __init__(self, x, y, fuel):
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.tilt = 0.0
        self.fuel = float(fuel)
        self.fuel_max = float(fuel)
        self.thrust_main = False
        self.thrust_side = 0          # -1 esquerda, 0 nada, +1 direita
        self.alive = True

    # A "quilha" (pés) fica uma linha abaixo do centro do corpo.
    def feet_y(self):
        return self.y + 1.0

    def fuel_pct(self):
        return 0.0 if self.fuel_max <= 0 else 100.0 * self.fuel / self.fuel_max

    def update(self, dt, wind):
        """Integração de Euler: gravidade + empuxo + vento + atitude."""
        # --- vertical ---
        self.vy += GRAVITY * dt
        if self.thrust_main and self.fuel > 0:
            self.vy -= MAIN_THRUST * dt
            self.fuel = max(0.0, self.fuel - FUEL_MAIN * dt)
        self.vy = max(-MAX_FALL, min(MAX_FALL, self.vy))

        # --- horizontal (vento sempre atua; propulsor só com combustível) ---
        self.vx += wind * dt
        if self.thrust_side and self.fuel > 0:
            self.vx += SIDE_THRUST * self.thrust_side * dt
            self.fuel = max(0.0, self.fuel - FUEL_SIDE * dt)
            # o RCS lateral inclina o módulo enquanto está acionado
            self.tilt += TILT_RATE * self.thrust_side * dt
        else:
            # auto-nivelamento exponencial quando nenhum lateral é usado
            self.tilt -= self.tilt * min(1.0, TILT_DAMP * dt)
        self.tilt = max(-TILT_MAX, min(TILT_MAX, self.tilt))
        self.vx = max(-8.0, min(8.0, self.vx))

        # --- posição (x usa ASPECT para o movimento parecer proporcional) ---
        self.x += self.vx * ASPECT * dt
        self.y += self.vy * dt


# ---------------------------------------------------------------------------
# 5) EXPLOSÃO
# ---------------------------------------------------------------------------

class Explosion:
    """Anel ASCII em expansão + fagulhas, com vida útil de ~1,2 s."""

    __slots__ = ("x", "y", "age", "life", "sparks")

    def __init__(self, x, y, rng=random):
        self.x = float(x)
        self.y = float(y)
        self.age = 0.0
        self.life = 1.30
        # fagulhas balísticas: (dx, dy, vx, vy, char)
        self.sparks = []
        for _ in range(26):
            ang = rng.uniform(0, math.tau)
            spd = rng.uniform(3.0, 11.0)
            self.sparks.append([0.0, 0.0,
                                math.cos(ang) * spd * ASPECT,
                                math.sin(ang) * spd * 0.55,
                                rng.choice("*.oO+'")])

    @property
    def alive(self):
        return self.age < self.life

    def update(self, dt):
        self.age += dt
        for s in self.sparks:
            s[0] += s[2] * dt
            s[1] += s[3] * dt
            s[3] += GRAVITY * 2.2 * dt      # as fagulhas também caem

    def radius(self):
        t = min(1.0, self.age / 0.45)
        return 1.0 + t * 5.5


# ---------------------------------------------------------------------------
# 6) O JOGO
# ---------------------------------------------------------------------------

class Game:

    def __init__(self, scr, lang="pt", keep_lang=False):
        self.scr = scr
        self.rng = random.Random()
        self._init_curses()
        self._init_colors()

        self.lang = lang
        self.state = ST_BRIEF if keep_lang else ST_LANG
        self.score = 0
        self.level = 1
        self.lives = START_LIVES
        self.landings = 0
        self.message = ""
        self.message_timer = 0.0
        self.result_lines = []
        self.explosion = None
        self.state_timer = 0.0
        self.hold_main = 0.0        # janela de acionamento do motor principal
        self.hold_side = 0.0        # janela dos propulsores laterais (sinal = lado)
        self.running = True

        self._layout()
        self.new_mission(reset=True)
        # a missão 1 fica pronta "atrás" do menu; o estado de entrada volta aqui
        self.state = ST_BRIEF if keep_lang else ST_LANG

    # ---------------------- infraestrutura --------------------------------
    def _init_curses(self):
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        self.scr.nodelay(True)      # entrada NÃO bloqueante
        self.scr.keypad(True)
        self.scr.timeout(0)

    def _init_colors(self):
        """Pares de cor; degrada para monocromático se o terminal não suportar."""
        names = ("hud", "dim", "ship", "flame", "flame2", "ground", "rock",
                 "pad2", "pad3", "pad5", "good", "bad", "warn", "title",
                 "sky", "star")
        self.C = {n: 0 for n in names}
        try:
            curses.start_color()
            curses.use_default_colors()
            if not curses.has_colors():
                return
        except curses.error:
            return
        defs = {
            "hud":    curses.COLOR_WHITE,
            "dim":    curses.COLOR_BLUE,
            "ship":   curses.COLOR_WHITE,
            "flame":  curses.COLOR_YELLOW,
            "flame2": curses.COLOR_RED,
            "ground": curses.COLOR_WHITE,
            "rock":   curses.COLOR_BLUE,
            "pad2":   curses.COLOR_GREEN,
            "pad3":   curses.COLOR_CYAN,
            "pad5":   curses.COLOR_MAGENTA,
            "good":   curses.COLOR_GREEN,
            "bad":    curses.COLOR_RED,
            "warn":   curses.COLOR_YELLOW,
            "title":  curses.COLOR_YELLOW,
            "sky":    curses.COLOR_BLUE,
            "star":   curses.COLOR_WHITE,
        }
        for i, (name, fg) in enumerate(defs.items(), start=1):
            try:
                curses.init_pair(i, fg, -1)
                self.C[name] = curses.color_pair(i)
            except curses.error:
                self.C[name] = 0

    # ---------------------- idioma ----------------------------------------
    def T(self, key, *args):
        s = STRINGS[self.lang].get(key) or STRINGS["pt"].get(key, key)
        return (s % args) if args else s

    def toggle_lang(self):
        global LAST_LANG
        self.lang = LANGS[(LANGS.index(self.lang) + 1) % len(LANGS)]
        LAST_LANG = self.lang
        self._flash(self.T("lang_set"), 1.4)
        if self.state in (ST_LANDED, ST_CRASH):     # regera o painel traduzido
            self._rebuild_result()

    def set_lang(self, lang):
        global LAST_LANG
        self.lang = lang
        LAST_LANG = lang

    def _flash(self, text, secs=1.5):
        self.message = text
        self.message_timer = secs

    # ---------------------- layout / missão -------------------------------
    def _layout(self):
        self.h, self.w = self.scr.getmaxyx()
        self.too_small = (self.w < MIN_W or self.h < MIN_H)
        self.hud_h = 2               # duas linhas de telemetria no topo
        self.sky_top = self.hud_h

    def new_mission(self, reset=False):
        """Gera terreno, reposiciona a nave e define o vento da missão."""
        if reset:
            self.level = 1
            self.score = 0
            self.lives = START_LIVES
            self.landings = 0
        w = max(MIN_W, self.w)
        self.terrain = Terrain(w, self.h, self.level, self.rng)
        fuel = max(55.0, 120.0 - 7.0 * (self.level - 1))
        start_x = self.rng.uniform(self.w * 0.2, self.w * 0.8)
        self.ship = Lander(start_x, self.sky_top + 1, fuel)
        self.ship.vx = self.rng.uniform(-0.6, 0.6) * min(3, self.level)
        self.ship.vy = 0.4
        # vento lateral constante a partir da missão 2
        self.wind = 0.0 if self.level < 2 else \
            self.rng.choice((-1, 1)) * self.rng.uniform(0.10, 0.09 + 0.05 * self.level)
        self.explosion = None
        self.result_lines = []
        self.no_fuel_warned = False
        self.low_fuel_warned = False
        self.stars = [(self.rng.randrange(1, w - 1),
                       self.rng.randrange(self.sky_top, max(self.sky_top + 1, self.h // 2)))
                      for _ in range(max(8, w // 8))]
        self.state = ST_PLAY

    # ---------------------- ENTRADA ---------------------------------------
    def handle_input(self):
        """
        Lê TODAS as teclas pendentes. Como o terminal não informa "tecla solta",
        cada pressionada acende o propulsor por uma janela curta de tempo
        (THRUST_HOLD), o que dá um controle analógico e suave ao segurar a tecla.
        """
        THRUST_HOLD = 0.16
        while True:
            ch = self.scr.getch()
            if ch == -1:
                break

            if ch == curses.KEY_RESIZE:
                self._layout()
                continue

            k = chr(ch).lower() if 32 <= ch < 127 else ''

            # --- globais ---
            if k == 'q' or ch == 27:                 # Q ou ESC
                self.running = False
                return
            if k == 't' and self.state != ST_LANG:
                self.toggle_lang()
                continue

            # --- por estado ---
            if self.state == ST_LANG:
                if k == '1':
                    self.set_lang("pt")
                    self.state = ST_BRIEF
                elif k == '2':
                    self.set_lang("en")
                    self.state = ST_BRIEF
                continue

            if self.state == ST_BRIEF:
                if k == ' ':
                    self.state = ST_PLAY
                continue

            if self.state == ST_LANDED:
                if k == ' ':
                    self.level += 1
                    self.new_mission()
                continue

            if self.state == ST_CRASH:
                if k in (' ', 'r') and self.state_timer > 0.8:
                    if self.lives <= 0:
                        self.state = ST_GAMEOVER
                    else:
                        self.new_mission()
                continue

            if self.state == ST_GAMEOVER:
                if k == 'r':
                    self.new_mission(reset=True)
                continue

            if k == 'p':
                self.state = ST_PAUSE if self.state == ST_PLAY else ST_PLAY
                continue
            if self.state != ST_PLAY:
                continue

            # --- propulsores ---
            if ch == curses.KEY_UP or k == 'w':
                self.hold_main = THRUST_HOLD
            elif ch == curses.KEY_LEFT or k == 'a':
                self.hold_side = -THRUST_HOLD
            elif ch == curses.KEY_RIGHT or k == 'd':
                self.hold_side = THRUST_HOLD

    # ---------------------- LÓGICA ----------------------------------------
    def update(self, dt):
        if self.message_timer > 0:
            self.message_timer -= dt
        if self.state in (ST_CRASH, ST_LANDED):
            self.state_timer += dt
        if self.state == ST_CRASH and self.explosion:
            self.explosion.update(dt)
        if self.state != ST_PLAY:
            return

        self.state_timer = 0.0
        s = self.ship

        # converte as "janelas de pressionamento" em estado de propulsor
        s.thrust_main = self.hold_main > 0
        s.thrust_side = (0 if abs(self.hold_side) < 1e-6
                         else (1 if self.hold_side > 0 else -1))
        self.hold_main = max(0.0, self.hold_main - dt)
        if self.hold_side > 0:
            self.hold_side = max(0.0, self.hold_side - dt)
        elif self.hold_side < 0:
            self.hold_side = min(0.0, self.hold_side + dt)

        # sem combustível não há empuxo (mas a gravidade continua)
        if s.fuel <= 0:
            s.thrust_main = False
            s.thrust_side = 0
            if not self.no_fuel_warned:
                self.no_fuel_warned = True
                self._flash(self.T("no_fuel"), 2.2)
        elif s.fuel_pct() <= 25 and not self.low_fuel_warned:
            self.low_fuel_warned = True
            self._flash(self.T("low_fuel"), 1.8)

        s.update(dt, self.wind)

        # paredes laterais: a nave não sai da tela (perde a inércia ao bater)
        if s.x < 2.0:
            s.x, s.vx = 2.0, max(0.0, s.vx)
        elif s.x > self.w - 3.0:
            s.x, s.vx = self.w - 3.0, min(0.0, s.vx)
        if s.y < self.sky_top:                       # teto de voo
            s.y, s.vy = float(self.sky_top), max(0.0, s.vy)

        self._check_touchdown()

    def _check_touchdown(self):
        """Detecta contato dos pés com o relevo e classifica pouso ou colisão."""
        s = self.ship
        cols = [int(round(s.x)) - 1, int(round(s.x)), int(round(s.x)) + 1]
        feet = s.feet_y()
        contact = any(feet >= self.terrain.surface(c) - 1 for c in cols)
        if not contact:
            return

        pads = [self.terrain.pad_at(c) for c in cols]
        pad = pads[1]
        on_pad = pad is not None and all(p is pad for p in pads)

        if not on_pad:
            self._crash("r_rough")
        elif abs(s.vy) > SAFE_VY:
            self._crash("r_fast_v", abs(s.vy), SAFE_VY)
        elif abs(s.vx) > SAFE_VX:
            self._crash("r_fast_h", abs(s.vx), SAFE_VX)
        elif abs(s.tilt) > SAFE_TILT:
            self._crash("r_tilt", abs(s.tilt), SAFE_TILT)
        else:
            self._land(pad)

    # --- desfechos ---------------------------------------------------------
    def _crash(self, reason_key, *args):
        s = self.ship
        s.alive = False
        self.lives -= 1
        self.crash_reason = (reason_key, args)
        self.explosion = Explosion(s.x, s.feet_y(), self.rng)
        self.state = ST_CRASH
        self.state_timer = 0.0
        self._rebuild_result()

    def _land(self, pad):
        s = self.ship
        impact_vy = abs(s.vy)          # guarda o impacto ANTES de assentar a nave
        # assenta a nave exatamente sobre a plataforma
        s.y = pad.y - 2.0
        s.vx = s.vy = 0.0
        s.tilt = 0.0
        base = 100 * self.level
        pad_pts = base * pad.mult
        # quanto mais suave o toque, maior o bônus (0 a 120 pontos)
        soft = int(max(0.0, (SAFE_VY - impact_vy) / SAFE_VY) * 120)
        fuel_pts = int(s.fuel_pct() * 4)
        self.last_land = (pad, base, pad_pts, impact_vy, soft, s.fuel_pct(), fuel_pts)
        self.score += pad_pts + soft + fuel_pts
        self.landings += 1
        self.state = ST_LANDED
        self.state_timer = 0.0
        self._rebuild_result()

    def _rebuild_result(self):
        """(Re)monta o painel de resultado no idioma corrente."""
        if self.state == ST_LANDED and hasattr(self, "last_land"):
            pad, base, pad_pts, vy, soft, fuelp, fuel_pts = self.last_land
            self.result_lines = [
                (self.T("ok_msg"), "good"),
                ("", "dim"),
                (self.T("b_pad", pad.label(), base, pad.mult, pad_pts), "hud"),
                (self.T("b_soft", abs(vy), soft), "hud"),
                (self.T("b_fuel", int(fuelp), fuel_pts), "hud"),
                ("", "dim"),
                (self.T("b_total", self.score), "title"),
                ("", "dim"),
                (self.T("next", self.level + 1), "hud"),
            ]
        elif self.state == ST_CRASH and hasattr(self, "crash_reason"):
            key, args = self.crash_reason
            tail = (self.T("retry") if self.lives > 0
                    else self.T("go_retry"))
            self.result_lines = [
                (self.T(key, *args), "bad"),
                ("", "dim"),
                (self.T("lives_left", max(0, self.lives)), "warn"),
                (self.T("hud_score") + ": %d" % self.score, "hud"),
                ("", "dim"),
                (tail, "hud"),
            ]

    # ---------------------- RENDERIZAÇÃO ----------------------------------
    def _put(self, y, x, text, attr=0):
        """addstr seguro: recorta o que sai da tela e ignora o canto final."""
        if y < 0 or y >= self.h or x >= self.w:
            return
        if x < 0:
            text = text[-x:]
            x = 0
        text = text[:max(0, self.w - x)]
        if not text:
            return
        if y == self.h - 1 and x + len(text) >= self.w:
            text = text[:self.w - x - 1]
            if not text:
                return
        try:
            self.scr.addstr(y, x, text, attr)
        except curses.error:
            pass

    def render(self):
        self.scr.erase()
        if self.too_small:
            self._put(0, 0, self.T("too_small", MIN_W, MIN_H),
                      self.C["bad"] | curses.A_BOLD)
            self.scr.refresh()
            return

        if self.state != ST_LANG:
            self._draw_stars()
            self._draw_terrain()
            self._draw_pads()
            if self.state != ST_CRASH:
                self._draw_ship()
            if self.explosion and self.state == ST_CRASH:
                self._draw_explosion()
            self._draw_hud()
        self._draw_overlays()
        self.scr.refresh()

    def _draw_stars(self):
        for (x, y) in self.stars:
            self._put(y, x, ".", self.C["star"] | curses.A_DIM)

    def _draw_terrain(self):
        """Superfície com caractere conforme a inclinação + preenchimento."""
        H = self.terrain.height
        for x in range(min(self.w - 1, self.terrain.w)):
            y = H[x]
            prev = H[x - 1] if x > 0 else y
            nxt = H[x + 1] if x + 1 < self.terrain.w else y
            if self.terrain.pad_at(x):
                continue                     # pads são desenhados à parte
            if prev > y and nxt >= y:
                ch = "/"
            elif nxt > y and prev >= y:
                ch = "\\"
            elif prev == y == nxt:
                ch = "_"
            else:
                ch = "-"
            self._put(y, x, ch, self.C["ground"] | curses.A_BOLD)
            for yy in range(y + 1, self.h):  # rocha abaixo da superfície
                self._put(yy, x, ":", self.C["rock"] | curses.A_DIM)

    def _draw_pads(self):
        """Plataformas em cor própria + etiqueta do multiplicador acima."""
        for p in self.terrain.pads:
            attr = self.C["pad%d" % p.mult] | curses.A_BOLD
            width = p.x1 - p.x0 + 1
            self._put(p.y, p.x0, "=" * width, attr)
            for x in range(p.x0, p.x1 + 1):
                for yy in range(p.y + 1, self.h):
                    self._put(yy, x, ":", self.C["rock"] | curses.A_DIM)
            tag = "[%s]" % p.label()
            tx = p.x0 + (width - len(tag)) // 2
            self._put(p.y - 1, tx, tag, attr)

    def _draw_ship(self):
        """
        Mini-sprite de 2 linhas. O nariz se desloca conforme a inclinação,
        e as chamas aparecem no motor acionado.
        """
        s = self.ship
        x, y = int(round(s.x)), int(round(s.y))
        attr = self.C["ship"] | curses.A_BOLD

        if s.tilt < -SAFE_TILT:
            nose = "^  "
        elif s.tilt > SAFE_TILT:
            nose = "  ^"
        else:
            nose = " ^ "
        self._put(y, x - 1, nose, attr)
        self._put(y + 1, x - 1, "/=\\", attr)

        # chama do motor principal (embaixo)
        if s.thrust_main and s.fuel > 0:
            f = self.C["flame"] | curses.A_BOLD
            f2 = self.C["flame2"] | curses.A_BOLD
            self._put(y + 2, x - 1, "\\", f2)
            self._put(y + 2, x, self.rng.choice("VvW"), f)
            self._put(y + 2, x + 1, "/", f2)

        # chama dos propulsores laterais (empuxo aponta para o lado oposto)
        if s.thrust_side and s.fuel > 0:
            f = self.C["flame"] | curses.A_BOLD
            if s.thrust_side > 0:
                self._put(y + 1, x - 2, "<", f)
            else:
                self._put(y + 1, x + 2, ">", f)

    def _draw_explosion(self):
        e = self.explosion
        t = e.age / e.life
        pal = ("flame", "flame2", "warn", "bad")
        attr = self.C[pal[int(e.age * 16) % len(pal)]] | curses.A_BOLD

        # anel em expansão (corrigido pelo aspecto -> parece circular)
        r = e.radius()
        if t < 0.75:
            steps = max(10, int(r * 10))
            for i in range(steps):
                ang = math.tau * i / steps
                px = int(round(e.x + math.cos(ang) * r * ASPECT))
                py = int(round(e.y + math.sin(ang) * r))
                self._put(py, px, "#" if t < 0.35 else "*", attr)

        # fagulhas balísticas
        for sp in e.sparks:
            px, py = int(round(e.x + sp[0])), int(round(e.y + sp[1]))
            if py >= self.terrain.surface(px):
                continue
            self._put(py, px, sp[4], attr)

    # --- HUD ---------------------------------------------------------------
    def _bar(self, pct, width=12):
        filled = int(round(width * max(0.0, min(100.0, pct)) / 100.0))
        return "[" + "#" * filled + "." * (width - filled) + "]"

    def _draw_hud(self):
        s = self.ship
        hud = self.C["hud"] | curses.A_BOLD
        alt = max(0.0, self.terrain.surface(s.x) - 1 - s.feet_y())

        # --- linha 1: telemetria, com cor de segurança em cada eixo ---------
        x = 1
        self._put(0, 0, " " * (self.w - 1), hud)
        seg = "%s %5.1f  " % (self.T("hud_alt"), alt)
        self._put(0, x, seg, hud); x += len(seg)

        c_vy = self.C["good"] if abs(s.vy) <= SAFE_VY else self.C["bad"]
        seg = "%s %+5.2f  " % (self.T("hud_vy"), s.vy)
        self._put(0, x, seg, c_vy | curses.A_BOLD); x += len(seg)

        c_vx = self.C["good"] if abs(s.vx) <= SAFE_VX else self.C["bad"]
        seg = "%s %+5.2f  " % (self.T("hud_vx"), s.vx)
        self._put(0, x, seg, c_vx | curses.A_BOLD); x += len(seg)

        c_ti = self.C["good"] if abs(s.tilt) <= SAFE_TILT else self.C["bad"]
        seg = "%s %+4.0fd " % (self.T("hud_tilt"), s.tilt)
        self._put(0, x, seg, c_ti | curses.A_BOLD); x += len(seg)

        if abs(self.wind) > 0.001:
            arrow = ">>" if self.wind > 0 else "<<"
            seg = "%s %s" % (self.T("hud_wind"), arrow)
            self._put(0, x, seg, self.C["warn"] | curses.A_BOLD)

        # --- linha 2: combustível, pontos, módulos, missão ------------------
        pct = s.fuel_pct()
        c_fuel = (self.C["good"] if pct > 45 else
                  self.C["warn"] if pct > 20 else self.C["bad"])
        line2 = " %s %s %3d%%   %s %6d   %s %d   %s %d" % (
            self.T("hud_fuel"), self._bar(pct), int(pct),
            self.T("hud_score"), self.score,
            self.T("hud_lives"), max(0, self.lives),
            self.T("hud_level"), self.level)
        self._put(1, 0, " " * (self.w - 1), hud)
        self._put(1, 0, line2, c_fuel | curses.A_BOLD)

        # --- mensagem de telemetria (alertas) -------------------------------
        if self.message_timer > 0 and self.state == ST_PLAY:
            self._put(self.sky_top, max(0, (self.w - len(self.message)) // 2),
                      self.message, self.C["warn"] | curses.A_BOLD)

    # --- painéis -----------------------------------------------------------
    def _panel(self, rows, title=None):
        """Painel centralizado com moldura; cada linha tem sua própria cor."""
        if not rows:
            return
        wid = min(max(len(s) for s, _ in rows) + 4, self.w - 2)
        hei = len(rows) + 2
        top = max(0, (self.h - hei) // 2)
        left = max(0, (self.w - wid) // 2)
        frame = self.C["hud"] | curses.A_BOLD
        self._put(top, left, "+" + "-" * (wid - 2) + "+", frame)
        for i, (text, attr) in enumerate(rows):
            y = top + 1 + i
            self._put(y, left, "|", frame)
            self._put(y, left + wid - 1, "|", frame)
            self._put(y, left + 1, text.center(wid - 2)[:wid - 2], attr)
        self._put(top + hei - 1, left, "+" + "-" * (wid - 2) + "+", frame)
        if title:
            self._put(top, left + 2, "[ %s ]" % title,
                      self.C["title"] | curses.A_BOLD)

    def _banner_rows(self, text, palette=("hud", "hud", "title", "title", "warn")):
        return [(line, self.C[palette[i % len(palette)]] | curses.A_BOLD)
                for i, line in enumerate(banner(text))]

    def _big_or_small(self, word, min_h, palette=None):
        """Usa arte ASCII se couber; senão, texto espaçado."""
        if self.w >= banner_width(word) + 6 and self.h >= min_h:
            return self._banner_rows(word, palette) if palette \
                else self._banner_rows(word)
        return [(" ".join(word), self.C["title"] | curses.A_BOLD)]

    def _draw_overlays(self):
        dim = self.C["dim"]
        hud = self.C["hud"] | curses.A_BOLD
        hi = self.C["title"] | curses.A_BOLD

        if self.state == ST_LANG:
            rows = []
            rows += self._big_or_small(STRINGS["pt"]["title_1"], 24)
            rows += self._big_or_small(STRINGS["pt"]["title_2"], 24)
            rows += [("", dim),
                     (STRINGS["pt"]["lang_1"], self.C["good"] | curses.A_BOLD),
                     (STRINGS["en"]["lang_2"], self.C["good"] | curses.A_BOLD),
                     ("", dim),
                     (STRINGS[self.lang]["lang_hint"], hud)]
            while len(rows) + 2 > self.h and len(rows) > 4:
                del rows[0]
            self._panel(rows, STRINGS["pt"]["lang_title"])

        elif self.state == ST_BRIEF:
            rows = []
            if self.h >= 26:
                rows += self._big_or_small(self.T("title_1"), 26)
                rows += self._big_or_small(self.T("title_2"), 26)
            else:
                rows += [(" ".join(self.T("title_small")), hi)]
            rows += [("", dim), (self.T("sub"), self.C["sky"] | curses.A_BOLD),
                     ("", dim),
                     (self.T("help_main"), hud),
                     (self.T("help_side"), hud),
                     (self.T("help_pause"), hud),
                     ("", dim),
                     (self.T("goal"), self.C["good"]),
                     (self.T("limits", SAFE_VY, SAFE_VX, SAFE_TILT), self.C["warn"]),
                     ("", dim), (self.T("start"), hi)]
            while len(rows) + 2 > self.h and len(rows) > 4:
                del rows[-4]
            self._panel(rows, self.T("brief_title"))

        elif self.state == ST_PAUSE:
            rows = [("", dim)]
            rows += self._big_or_small(self.T("pause_word"), 15)
            rows += [("", dim), (self.T("pause_help"), hud), ("", dim)]
            self._panel(rows, self.T("pause_title"))

        elif self.state == ST_LANDED:
            rows = self._big_or_small(self.T("ok_word"), 26,
                                      ("good", "good", "good", "hud", "hud"))
            rows += [("", dim)] + [(t, self.C[c] | curses.A_BOLD)
                                   for t, c in self.result_lines]
            while len(rows) + 2 > self.h and len(rows) > 6:
                del rows[0]
            self._panel(rows, self.T("ok_title"))

        elif self.state == ST_CRASH:
            if self.state_timer < 0.9:          # deixa a explosão aparecer antes
                return
            rows = self._big_or_small(self.T("crash_word"), 26,
                                      ("bad", "bad", "flame2", "flame2", "warn"))
            rows += [("", dim)] + [(t, self.C[c] | curses.A_BOLD)
                                   for t, c in self.result_lines]
            while len(rows) + 2 > self.h and len(rows) > 6:
                del rows[0]
            self._panel(rows, self.T("crash_title"))

        elif self.state == ST_GAMEOVER:
            rows = self._big_or_small(self.T("go_word"), 24,
                                      ("bad", "bad", "flame2", "warn", "warn"))
            rows += [
                ("", dim),
                (self.T("go_msg"), self.C["bad"] | curses.A_BOLD),
                ("", dim),
                (self.T("go_level", self.level), hud),
                (self.T("go_land", self.landings), hud),
                (self.T("go_score", self.score), hi),
                ("", dim),
                (self.T("go_retry"), hud),
            ]
            while len(rows) + 2 > self.h and len(rows) > 6:
                del rows[0]
            self._panel(rows, self.T("go_title"))

    # ---------------------- GAME LOOP -------------------------------------
    def run(self):
        last = time.perf_counter()
        while self.running:
            now = time.perf_counter()
            dt = min(0.10, now - last)      # clamp protege a física contra lag
            last = now

            self.handle_input()             # 1) ENTRADA
            self.update(dt)                 # 2) FÍSICA / LÓGICA
            self.render()                   # 3) DESENHO

            spare = FRAME_TIME - (time.perf_counter() - now)
            if spare > 0:
                time.sleep(spare)


# ---------------------------------------------------------------------------
# 7) BOOTSTRAP  (curses.wrapper + finally => terminal sempre restaurado)
# ---------------------------------------------------------------------------

def main(scr):
    global LAST_LANG
    game = Game(scr)
    try:
        game.run()
    finally:
        LAST_LANG = game.lang


if __name__ == "__main__":
    try:
        curses.wrapper(main)          # restaura o terminal mesmo se der exceção
    except KeyboardInterrupt:
        pass
    print(STRINGS[LAST_LANG]["bye"])
