#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 MP MISSEL COMANDO  /  MP MISSILE COMMAND
 Um clone jogável do clássico do Atari (1980) rodando 100% em modo texto.
 Bilíngue: português e inglês (tecla T alterna a qualquer momento).
===============================================================================

 DEPENDÊNCIAS
 ------------
   * Python 3.8+
   * Linux / macOS : nenhuma dependência extra (o módulo `curses` já vem na
                     biblioteca padrão).
   * Windows       : pip install windows-curses

 EXECUÇÃO
 --------
   python3 mp_missel_comando.py

 CONTROLES
 ---------
   Setas ou W A S D .... move a mira (crosshair)
   1 / J ............... dispara da bateria ALFA    (esquerda)
   2 / K ............... dispara da bateria BRAVO   (centro)
   3 / L ............... dispara da bateria CHARLIE (direita)
   ESPAÇO .............. dispara da bateria mais próxima da mira
   T ................... alterna PORTUGUÊS <-> ENGLISH
   P ................... pausa
   Q ................... sair

 ARQUITETURA
 -----------
   1) Vec2                      -> sistema de vetores 2D (posição/velocidade)
   2) FONT5 / banner()          -> fonte ASCII 5x5 para os títulos
   3) STRINGS / Game.T()        -> camada de internacionalização (pt/en)
   4) Missile / Explosion /
      City / Turret             -> entidades do jogo
   5) collide()                 -> distância euclidiana corrigida por aspecto
   6) Game.handle_input()       -> entrada
      Game.update(dt)           -> lógica
      Game.render()             -> desenho
   7) Game.run()                -> game loop com controle de framerate
===============================================================================
"""

import curses
import math
import random
import time

# ---------------------------------------------------------------------------
# CONSTANTES GLOBAIS
# ---------------------------------------------------------------------------

FPS = 30                 # quadros por segundo alvo
FRAME_TIME = 1.0 / FPS   # duração ideal de um quadro (segundos)

# Uma célula de terminal é ~2x mais alta do que larga. Para que explosões
# pareçam círculos (e não elipses achatadas) todas as distâncias horizontais
# são divididas por este fator. Chamamos isso de "espaço visual".
ASPECT = 2.0

MIN_W, MIN_H = 62, 20    # tamanho mínimo de terminal suportado

# Velocidades (em unidades visuais por segundo)
INTERCEPTOR_SPEED = 46.0

# Raios de explosão (em unidades visuais / linhas)
R_INTERCEPTOR = 4.2      # explosão do míssil defensivo
R_CHAIN = 2.8            # explosão de um ICBM abatido (gera reação em cadeia)
R_GROUND = 3.2           # explosão de um ICBM que atingiu o solo

AMMO_PER_TURRET = 10     # munição por bateria a cada rodada
NUM_CITIES = 6

TURRET_NAMES = ("ALFA", "BRAVO", "CHARLIE")
TURRET_NAMES_I18N = {
    "pt": ("ALFA", "BRAVO", "CHARLIE"),
    "en": ("ALPHA", "BRAVO", "CHARLIE"),
}

# Estados da máquina de estados do jogo
ST_TITLE, ST_PLAY, ST_PAUSE, ST_WAVE_END, ST_GAMEOVER = range(5)


# ---------------------------------------------------------------------------
# 1-B) FONTE ASCII 5x5 PARA OS TÍTULOS
# ---------------------------------------------------------------------------
# Cada glifo tem 5 linhas de 5 colunas. O gerador `banner()` monta uma palavra
# empilhando os glifos lado a lado com 1 coluna de respiro entre eles.

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
    """Converte um texto em 5 linhas de arte ASCII. Caracteres desconhecidos
    viram espaço, então nunca quebra o desenho."""
    glyphs = [FONT5.get(c.upper(), FONT5[" "]) for c in text]
    return [" ".join(g[row] for g in glyphs) for row in range(GLYPH_H)]


def banner_width(text):
    """Largura em colunas que o banner ocupará (útil para decidir o layout)."""
    return max(0, len(text) * 6 - 1)


# ---------------------------------------------------------------------------
# 1-C) INTERNACIONALIZAÇÃO (PORTUGUÊS / INGLÊS)
# ---------------------------------------------------------------------------
# Todo texto exibido passa por Game.T(chave). Trocar de idioma em tempo real é
# só mudar self.lang -- nada de string solta espalhada pelo código.

LANGS = ("pt", "en")

STRINGS = {
    "pt": {
        "title_1":      "MP MISSEL",
        "title_2":      "COMANDO",
        "title_small":  "MP MISSEL COMANDO",
        "subtitle":     "EDICAO TERMINAL  -  ATARI 1980",
        "briefing":     "BRIEFING",
        "help_move":    "Setas / W A S D ... mover a mira",
        "help_fire":    "1/J  2/K  3/L ..... ALFA / BRAVO / CHARLIE",
        "help_space":   "ESPACO ............ bateria mais proxima",
        "help_lang":    "T ................. idioma (PT / EN)",
        "help_pause":   "P ................. pausa      Q ... sair",
        "help_goal":    "Defenda as 6 cidades. Boa sorte, Comandante.",
        "start":        "[ESPACO] PARA COMECAR",
        "hud_score":    "PONTOS",
        "hud_wave":     "ONDA",
        "hud_cities":   "CIDADES",
        "wave_start":   "ONDA %d  -  MULTIPLICADOR x%d",
        "city_lost":    "CIDADE DESTRUIDA!",
        "turret_lost":  "BATERIA %s FORA DE COMBATE!",
        "turret_dead":  "BATERIA %s DESTRUIDA!",
        "no_ammo":      "BATERIA %s SEM MUNICAO!",
        "all_dead":     "TODAS AS BATERIAS INOPERANTES!",
        "aim_low":      "MIRA MUITO BAIXA!",
        "bonus_city":   "*** CIDADE BONUS RECONSTRUIDA ***",
        "lang_set":     "IDIOMA: PORTUGUES",
        "bonus_title":  "BONUS",
        "wave_done":    "ONDA %d COMPLETA",
        "b_ammo":       "MUNICAO RESTANTE : %2d  x %3d pts  = %6d",
        "b_cities":     "CIDADES SALVAS   : %2d  x %3d pts  = %6d",
        "b_acc":        "PRECISAO GERAL   : %.1f%%",
        "b_total":      "PONTUACAO TOTAL  : %d",
        "b_next":       "[ESPACO] para iniciar a onda %d",
        "pause_title":  "PAUSA",
        "pause_word":   "PAUSA",
        "pause_help":   "[P] continuar    [Q] sair",
        "go_title":     "FIM DE JOGO",
        "go_word":      "GAME OVER",
        "go_msg":       "Todas as cidades foram destruidas.",
        "go_waves":     "ONDAS SOBREVIVIDAS : %d",
        "go_acc":       "PRECISAO           : %.1f%%",
        "go_score":     "PONTUACAO FINAL    : %d",
        "go_retry":     "[R] jogar novamente     [Q] sair",
        "too_small":    "Aumente o terminal para pelo menos %dx%d",
        "bye":          "Obrigado por jogar MP MISSEL COMANDO!",
    },
    "en": {
        "title_1":      "MP MISSILE",
        "title_2":      "COMMAND",
        "title_small":  "MP MISSILE COMMAND",
        "subtitle":     "TERMINAL EDITION  -  ATARI 1980",
        "briefing":     "BRIEFING",
        "help_move":    "Arrows / W A S D .. move the crosshair",
        "help_fire":    "1/J  2/K  3/L ..... ALPHA / BRAVO / CHARLIE",
        "help_space":   "SPACE ............. nearest battery",
        "help_lang":    "T ................. language (PT / EN)",
        "help_pause":   "P ................. pause      Q ... quit",
        "help_goal":    "Defend all 6 cities. Good luck, Commander.",
        "start":        "[SPACE] TO START",
        "hud_score":    "SCORE",
        "hud_wave":     "WAVE",
        "hud_cities":   "CITIES",
        "wave_start":   "WAVE %d  -  MULTIPLIER x%d",
        "city_lost":    "CITY DESTROYED!",
        "turret_lost":  "BATTERY %s KNOCKED OUT!",
        "turret_dead":  "BATTERY %s DESTROYED!",
        "no_ammo":      "BATTERY %s OUT OF AMMO!",
        "all_dead":     "ALL BATTERIES DOWN!",
        "aim_low":      "AIM TOO LOW!",
        "bonus_city":   "*** BONUS CITY REBUILT ***",
        "lang_set":     "LANGUAGE: ENGLISH",
        "bonus_title":  "BONUS",
        "wave_done":    "WAVE %d COMPLETE",
        "b_ammo":       "AMMO REMAINING : %2d  x %3d pts  = %6d",
        "b_cities":     "CITIES SAVED   : %2d  x %3d pts  = %6d",
        "b_acc":        "OVERALL ACCURACY : %.1f%%",
        "b_total":      "TOTAL SCORE      : %d",
        "b_next":       "[SPACE] to start wave %d",
        "pause_title":  "PAUSE",
        "pause_word":   "PAUSED",
        "pause_help":   "[P] resume    [Q] quit",
        "go_title":     "GAME OVER",
        "go_word":      "GAME OVER",
        "go_msg":       "Every city has been destroyed.",
        "go_waves":     "WAVES SURVIVED : %d",
        "go_acc":       "ACCURACY       : %.1f%%",
        "go_score":     "FINAL SCORE    : %d",
        "go_retry":     "[R] play again     [Q] quit",
        "too_small":    "Please resize the terminal to at least %dx%d",
        "bye":          "Thanks for playing MP MISSILE COMMAND!",
    },
}

# Idioma escolhido na última sessão (usado na mensagem de despedida).
LAST_LANG = "pt"


# ---------------------------------------------------------------------------
# 1) SISTEMA DE VETORES 2D
# ---------------------------------------------------------------------------

class Vec2:
    """Vetor 2D mínimo usado para posição, alvo e velocidade."""

    __slots__ = ("x", "y")

    def __init__(self, x=0.0, y=0.0):
        self.x = float(x)
        self.y = float(y)

    # --- operadores aritméticos -------------------------------------------
    def __add__(self, o):
        return Vec2(self.x + o.x, self.y + o.y)

    def __sub__(self, o):
        return Vec2(self.x - o.x, self.y - o.y)

    def __mul__(self, k):
        return Vec2(self.x * k, self.y * k)

    __rmul__ = __mul__

    def __repr__(self):
        return "Vec2(%.2f, %.2f)" % (self.x, self.y)

    # --- utilidades --------------------------------------------------------
    def copy(self):
        return Vec2(self.x, self.y)

    def length(self):
        """Comprimento bruto em células do terminal."""
        return math.hypot(self.x, self.y)

    def vlength(self):
        """Comprimento no 'espaço visual' (corrige o aspecto do caractere)."""
        return math.hypot(self.x / ASPECT, self.y)

    def scaled_to(self, speed):
        """Retorna um vetor na mesma direção cuja velocidade visual == speed."""
        L = self.vlength()
        if L < 1e-9:
            return Vec2(0.0, 0.0)
        return Vec2(self.x * speed / L, self.y * speed / L)


def vdist(a, b):
    """Distância euclidiana entre dois pontos no espaço visual."""
    return math.hypot((a.x - b.x) / ASPECT, a.y - b.y)


def bresenham(x0, y0, x1, y1):
    """Gera os pontos inteiros de uma reta (usado para desenhar rastros)."""
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        yield x0, y0
        if x0 == x1 and y0 == y1:
            return
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


# ---------------------------------------------------------------------------
# 2) ENTIDADES
# ---------------------------------------------------------------------------

class Missile:
    """
    Míssil genérico que viaja em linha reta de `start` até `target`.
    `hostile=True`  -> ICBM inimigo (desce)
    `hostile=False` -> interceptador amigo (sobe)
    """

    __slots__ = ("start", "pos", "target", "vel", "hostile",
                 "alive", "arrived", "total", "split_at", "splits")

    def __init__(self, start, target, speed, hostile, split_at=None, splits=0):
        self.start = start.copy()
        self.pos = start.copy()
        self.target = target.copy()
        self.hostile = hostile
        self.alive = True
        self.arrived = False
        delta = target - start
        self.total = delta.vlength()
        self.vel = delta.scaled_to(speed)
        self.split_at = split_at   # altura (y) em que o MIRV se divide
        self.splits = splits       # quantas ogivas ainda pode liberar

    def update(self, dt):
        """Integra a posição e sinaliza quando o alvo é alcançado."""
        self.pos.x += self.vel.x * dt
        self.pos.y += self.vel.y * dt
        if (self.pos - self.start).vlength() >= self.total:
            self.pos = self.target.copy()
            self.arrived = True

    def head(self):
        """Coordenada inteira da cabeça do míssil (para render/colisão)."""
        return int(round(self.pos.x)), int(round(self.pos.y))


class Explosion:
    """
    Esfera de plasma em expansão -> sustentação -> contração.
    Qualquer ICBM cuja cabeça entre no raio é destruído.
    """

    __slots__ = ("pos", "radius", "max_radius", "phase", "timer",
                 "grow_rate", "hold_time", "age", "friendly")

    def __init__(self, pos, max_radius, friendly=True):
        self.pos = pos.copy()
        self.radius = 0.35
        self.max_radius = max_radius
        self.grow_rate = max_radius / 0.32   # atinge o raio máximo em ~0,32 s
        self.hold_time = 0.30
        self.phase = 0                       # 0=cresce 1=sustenta 2=encolhe
        self.timer = 0.0
        self.age = 0.0
        self.friendly = friendly

    @property
    def alive(self):
        return not (self.phase == 2 and self.radius <= 0.2)

    def update(self, dt):
        self.age += dt
        if self.phase == 0:
            self.radius += self.grow_rate * dt
            if self.radius >= self.max_radius:
                self.radius = self.max_radius
                self.phase = 1
        elif self.phase == 1:
            self.timer += dt
            if self.timer >= self.hold_time:
                self.phase = 2
        else:
            self.radius -= self.grow_rate * 0.75 * dt


class City:
    """Uma das 6 cidades a serem defendidas."""

    __slots__ = ("x", "y", "alive")

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.alive = True

    def center(self):
        return Vec2(self.x, self.y)


class Turret:
    """Bateria antiaérea (Alfa, Bravo, Charlie)."""

    __slots__ = ("x", "y", "ammo", "alive", "name", "letter")

    def __init__(self, x, y, name):
        self.x = x
        self.y = y
        self.name = name
        self.letter = name[0]
        self.ammo = AMMO_PER_TURRET
        self.alive = True

    def center(self):
        return Vec2(self.x, self.y)

    def muzzle(self):
        """Ponto de onde o interceptador sai (topo da bateria)."""
        return Vec2(self.x, self.y - 1)


# ---------------------------------------------------------------------------
# 3) DETECÇÃO DE COLISÃO
# ---------------------------------------------------------------------------

def collide(missile, explosion):
    """True se a cabeça do míssil estiver dentro do raio da explosão."""
    return vdist(missile.pos, explosion.pos) <= explosion.radius


# ---------------------------------------------------------------------------
# 4) O JOGO
# ---------------------------------------------------------------------------

class Game:

    # ---------------------- inicialização ---------------------------------
    def __init__(self, stdscr):
        self.scr = stdscr
        self._init_curses()
        self._init_colors()

        self.state = ST_TITLE
        self.lang = "pt"                 # idioma inicial (T alterna)
        self.score = 0
        self.wave = 1
        self.bonus_lines = []
        self.b_ammo_left = self.b_cities_left = 0
        self.b_ammo_pts = self.b_city_pts = 0
        self.state_timer = 0.0
        self.message = ""
        self.message_timer = 0.0
        self.next_bonus_city = 10000     # cidade extra a cada 10.000 pontos
        self.shots_fired = 0
        self.shots_hit = 0
        self.running = True

        self._layout()
        self._build_base(reset=True)
        self._start_wave(1)
        self.state = ST_TITLE        # a onda 1 fica "armada" atrás do briefing

    # ---------------------- idioma ----------------------------------------
    def T(self, key, *args):
        """Retorna a string traduzida (com % formatação opcional)."""
        s = STRINGS[self.lang].get(key) or STRINGS["pt"].get(key, key)
        return (s % args) if args else s

    def tname(self, index):
        """Nome da bateria no idioma corrente."""
        return TURRET_NAMES_I18N[self.lang][index]

    def toggle_lang(self):
        global LAST_LANG
        self.lang = LANGS[(LANGS.index(self.lang) + 1) % len(LANGS)]
        LAST_LANG = self.lang
        self._flash(self.T("lang_set"), 1.4)
        if self.state == ST_WAVE_END:    # regera o painel de bônus traduzido
            self._build_bonus_lines()

    def _init_curses(self):
        try:
            curses.curs_set(0)           # esconde o cursor do terminal
        except curses.error:
            pass
        self.scr.nodelay(True)           # entrada NÃO bloqueante
        self.scr.keypad(True)            # habilita KEY_UP, KEY_LEFT, ...
        self.scr.timeout(0)

    def _init_colors(self):
        """Cria os pares de cor. Degrada para monocromático se preciso."""
        self.C = {}
        try:
            curses.start_color()
            curses.use_default_colors()
            has = curses.has_colors()
        except curses.error:
            has = False
        self.has_color = has
        if not has:
            for k in ("hud", "city", "rubble", "turret", "dead", "enemy",
                      "etrail", "ally", "atrail", "cross", "ground",
                      "e1", "e2", "e3", "e4", "title", "warn"):
                self.C[k] = 0
            return

        defs = [
            ("hud",    curses.COLOR_WHITE),
            ("city",   curses.COLOR_CYAN),
            ("rubble", curses.COLOR_BLUE),
            ("turret", curses.COLOR_GREEN),
            ("dead",   curses.COLOR_BLACK),
            ("enemy",  curses.COLOR_RED),
            ("etrail", curses.COLOR_MAGENTA),
            ("ally",   curses.COLOR_CYAN),
            ("atrail", curses.COLOR_BLUE),
            ("cross",  curses.COLOR_YELLOW),
            ("ground", curses.COLOR_GREEN),
            ("e1",     curses.COLOR_YELLOW),
            ("e2",     curses.COLOR_RED),
            ("e3",     curses.COLOR_MAGENTA),
            ("e4",     curses.COLOR_WHITE),
            ("title",  curses.COLOR_YELLOW),
            ("warn",   curses.COLOR_RED),
        ]
        for i, (name, fg) in enumerate(defs, start=1):
            try:
                curses.init_pair(i, fg, -1)
                self.C[name] = curses.color_pair(i)
            except curses.error:
                self.C[name] = 0

    # ---------------------- layout / cenário ------------------------------
    def _layout(self):
        """Recalcula as dimensões da tela e as faixas do cenário."""
        self.h, self.w = self.scr.getmaxyx()
        self.too_small = (self.w < MIN_W or self.h < MIN_H)
        self.sky_top = 2                 # linhas 0 e 1 são o HUD
        self.base_y = self.h - 2         # linha onde ficam cidades/baterias
        self.ground_y = self.h - 1       # linha do solo

    def _base_positions(self):
        """Posições X das 3 baterias e das 6 cidades."""
        tx = [max(2, self.w // 10),
              self.w // 2,
              min(self.w - 3, self.w - self.w // 10)]
        cx = []
        for a, b in ((tx[0], tx[1]), (tx[1], tx[2])):
            span = b - a
            for i in (1, 2, 3):
                cx.append(a + span * i // 4)
        return tx, cx

    def _build_base(self, reset=False):
        """Cria (ou reposiciona, após resize) cidades e baterias."""
        tx, cx = self._base_positions()
        if reset:
            self.turrets = [Turret(tx[i], self.base_y, TURRET_NAMES[i])
                            for i in range(3)]
            self.cities = [City(x, self.base_y) for x in cx]
        else:                                   # preserva o estado ao redimensionar
            for t, x in zip(self.turrets, tx):
                t.x, t.y = x, self.base_y
            for c, x in zip(self.cities, cx):
                c.x, c.y = x, self.base_y

    # ---------------------- configuração de onda --------------------------
    def _wave_config(self, wave):
        """Dificuldade progressiva: mais mísseis, mais rápidos, com MIRV."""
        return {
            "count":       min(34, 6 + wave * 2),
            "speed":       min(9.5, 2.2 + 0.50 * wave),
            "interval":    max(0.22, 1.55 - 0.085 * wave),
            "mirv_chance": 0.0 if wave < 3 else min(0.40, 0.06 * (wave - 2)),
        }

    def _start_wave(self, wave):
        self.wave = wave
        cfg = self._wave_config(wave)
        self.cfg = cfg
        self.to_spawn = cfg["count"]
        self.spawn_timer = 0.6
        self.missiles = []       # ICBMs inimigos
        self.allies = []         # interceptadores
        self.explosions = []
        self.multiplier = min(6, 1 + (wave - 1) // 2)
        for t in self.turrets:               # recarrega e reconstrói baterias
            t.ammo = AMMO_PER_TURRET
            t.alive = True
        self.cross = Vec2(self.w // 2, max(self.sky_top + 2, self.h // 2))
        self.state = ST_PLAY
        self._flash(self.T("wave_start", wave, self.multiplier), 2.0)

    def _flash(self, text, secs=1.4):
        self.message = text
        self.message_timer = secs

    # ---------------------- spawn de inimigos -----------------------------
    def _spawn_enemy(self):
        """Lança um ICBM do topo da tela em direção a uma cidade/bateria."""
        targets = [c for c in self.cities if c.alive] + \
                  [t for t in self.turrets if t.alive]
        if not targets:
            return
        tgt = random.choice(targets)
        start = Vec2(random.randint(1, max(1, self.w - 2)), float(self.sky_top))
        goal = Vec2(tgt.x + random.uniform(-1.0, 1.0), float(self.base_y))
        speed = self.cfg["speed"] * random.uniform(0.85, 1.2)

        split_at = None
        splits = 0
        if random.random() < self.cfg["mirv_chance"]:
            splits = random.choice((1, 2))
            split_at = random.uniform(self.sky_top + 3,
                                      self.sky_top + (self.base_y - self.sky_top) * 0.55)
        self.missiles.append(Missile(start, goal, speed, True, split_at, splits))

    def _split_mirv(self, m):
        """Um MIRV libera ogivas independentes com novos alvos."""
        targets = [c for c in self.cities if c.alive] + \
                  [t for t in self.turrets if t.alive]
        if not targets:
            m.split_at = None
            return
        for _ in range(m.splits):
            tgt = random.choice(targets)
            goal = Vec2(tgt.x + random.uniform(-1.0, 1.0), float(self.base_y))
            speed = self.cfg["speed"] * random.uniform(0.9, 1.25)
            child = Missile(m.pos.copy(), goal, speed, True)
            self.missiles.append(child)
        m.split_at = None
        m.splits = 0

    # ---------------------- disparo ---------------------------------------
    def _fire(self, index):
        """Dispara um interceptador da bateria `index` até a mira."""
        if self.state != ST_PLAY:
            return
        t = self.turrets[index]
        if not t.alive:
            self._flash(self.T("turret_dead", self.tname(index)), 0.8)
            return
        if t.ammo <= 0:
            self._flash(self.T("no_ammo", self.tname(index)), 0.8)
            return
        target = Vec2(self.cross.x, self.cross.y)
        if target.y >= self.base_y - 0.5:      # não permite mirar no próprio solo
            self._flash(self.T("aim_low"), 0.7)
            return
        t.ammo -= 1
        self.shots_fired += 1
        self.allies.append(Missile(t.muzzle(), target, INTERCEPTOR_SPEED, False))

    def _fire_nearest(self):
        """ESPAÇO: escolhe automaticamente a bateria útil mais próxima."""
        cands = [(abs(t.x - self.cross.x), i)
                 for i, t in enumerate(self.turrets) if t.alive and t.ammo > 0]
        if not cands:
            self._flash(self.T("all_dead"), 1.0)
            return
        cands.sort()
        self._fire(cands[0][1])

    # ---------------------- ENTRADA ---------------------------------------
    def handle_input(self):
        """Consome TODAS as teclas pendentes do buffer (não bloqueante)."""
        while True:
            ch = self.scr.getch()
            if ch == -1:
                break

            if ch == curses.KEY_RESIZE:
                self._layout()
                self._build_base(reset=False)
                continue

            k = chr(ch).lower() if 32 <= ch < 127 else ''

            # --- comandos globais ---
            if k == 'q':
                self.running = False
                return
            if k == 't':                        # troca de idioma em qualquer tela
                self.toggle_lang()
                continue
            if self.state == ST_TITLE:
                if k == ' ':
                    self.state = ST_PLAY
                continue
            if self.state == ST_GAMEOVER:
                if k == 'r':
                    lang = self.lang            # o idioma sobrevive ao restart
                    self.__init__(self.scr)     # reinicia a partida
                    self.lang = lang
                    self.state = ST_PLAY
                    return
                continue
            if self.state == ST_WAVE_END:
                if k == ' ':
                    self._start_wave(self.wave + 1)
                continue
            if k == 'p':
                self.state = ST_PAUSE if self.state == ST_PLAY else ST_PLAY
                continue
            if self.state != ST_PLAY:
                continue

            # --- movimento da mira ---
            if ch in (curses.KEY_LEFT,) or k == 'a':
                self.cross.x -= 2
            elif ch in (curses.KEY_RIGHT,) or k == 'd':
                self.cross.x += 2
            elif ch in (curses.KEY_UP,) or k == 'w':
                self.cross.y -= 1
            elif ch in (curses.KEY_DOWN,) or k == 's':
                self.cross.y += 1
            # --- disparo ---
            elif k in ('1', 'j'):
                self._fire(0)
            elif k in ('2', 'k'):
                self._fire(1)
            elif k in ('3', 'l'):
                self._fire(2)
            elif k == ' ':
                self._fire_nearest()

            # mantém a mira dentro da área jogável
            self.cross.x = max(1, min(self.w - 2, self.cross.x))
            self.cross.y = max(self.sky_top, min(self.base_y - 1, self.cross.y))

    # ---------------------- LÓGICA ----------------------------------------
    def update(self, dt):
        if self.message_timer > 0 and self.state == ST_PLAY:
            self.message_timer -= dt

        if self.state == ST_WAVE_END:
            self.state_timer += dt
            return
        if self.state != ST_PLAY:
            return

        self._update_spawner(dt)
        self._update_allies(dt)
        self._update_enemies(dt)
        self._update_explosions(dt)
        self._resolve_collisions()
        self._check_end_conditions()

    def _update_spawner(self, dt):
        if self.to_spawn <= 0:
            return
        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self._spawn_enemy()
            self.to_spawn -= 1
            self.spawn_timer = self.cfg["interval"] * random.uniform(0.55, 1.35)

    def _update_allies(self, dt):
        for m in self.allies:
            m.update(dt)
            if m.arrived:
                m.alive = False
                self.explosions.append(Explosion(m.pos, R_INTERCEPTOR, True))
        self.allies = [m for m in self.allies if m.alive]

    def _update_enemies(self, dt):
        for m in self.missiles:
            m.update(dt)
            if m.split_at is not None and m.pos.y >= m.split_at:
                self._split_mirv(m)
            if m.arrived:                      # atingiu o solo
                m.alive = False
                self.explosions.append(Explosion(m.pos, R_GROUND, False))
                self._ground_damage(m.pos)
        self.missiles = [m for m in self.missiles if m.alive]

    def _update_explosions(self, dt):
        for e in self.explosions:
            e.update(dt)
        self.explosions = [e for e in self.explosions if e.alive]

    def _ground_damage(self, pos):
        """Destrói cidades/baterias dentro do raio do impacto no solo."""
        for c in self.cities:
            if c.alive and vdist(pos, c.center()) <= R_GROUND * 0.85:
                c.alive = False
                self._flash(self.T("city_lost"), 1.2)
        for i, t in enumerate(self.turrets):
            if t.alive and vdist(pos, t.center()) <= R_GROUND * 0.75:
                t.alive = False
                t.ammo = 0
                self._flash(self.T("turret_lost", self.tname(i)), 1.2)

    def _resolve_collisions(self):
        """
        Núcleo da mecânica: qualquer ICBM dentro do raio de QUALQUER explosão
        é destruído e gera uma nova explosão -> reação em cadeia.
        """
        survivors = []
        for m in self.missiles:
            hit = False
            for e in self.explosions:
                if collide(m, e):
                    hit = True
                    break
            if hit:
                m.alive = False
                self.shots_hit += 1
                self.explosions.append(Explosion(m.pos, R_CHAIN, True))
                self._add_score(25 * self.multiplier)
            else:
                survivors.append(m)
        self.missiles = survivors

    def _add_score(self, pts):
        self.score += pts
        if self.score >= self.next_bonus_city:
            self.next_bonus_city += 10000
            dead = [c for c in self.cities if not c.alive]
            if dead:
                random.choice(dead).alive = True
                self._flash(self.T("bonus_city"), 2.0)

    def _check_end_conditions(self):
        if not any(c.alive for c in self.cities):
            self.state = ST_GAMEOVER
            return
        wave_clear = (self.to_spawn == 0 and not self.missiles
                      and not self.allies and not self.explosions)
        if wave_clear:
            self._finish_wave()

    def _finish_wave(self):
        """Tela de bônus: munição e cidades sobreviventes valem pontos."""
        self.b_ammo_left = sum(t.ammo for t in self.turrets if t.alive)
        self.b_cities_left = sum(1 for c in self.cities if c.alive)
        self.b_ammo_pts = self.b_ammo_left * 5 * self.multiplier
        self.b_city_pts = self.b_cities_left * 100 * self.multiplier
        self._add_score(self.b_ammo_pts + self.b_city_pts)
        self._build_bonus_lines()
        self.state = ST_WAVE_END
        self.state_timer = 0.0

    def _build_bonus_lines(self):
        """Monta o painel de bônus no idioma corrente (recriado ao trocar T)."""
        acc = (100.0 * self.shots_hit / self.shots_fired) if self.shots_fired else 0.0
        self.bonus_lines = [
            self.T("wave_done", self.wave),
            "",
            self.T("b_ammo", self.b_ammo_left, 5 * self.multiplier, self.b_ammo_pts),
            self.T("b_cities", self.b_cities_left, 100 * self.multiplier, self.b_city_pts),
            self.T("b_acc", acc),
            "",
            self.T("b_total", self.score),
            "",
            self.T("b_next", self.wave + 1),
        ]

    # ---------------------- RENDERIZAÇÃO ----------------------------------
    def _put(self, y, x, text, attr=0):
        """addstr seguro: ignora escritas fora da tela / canto inferior."""
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
                      self.C["warn"] | curses.A_BOLD)
            self.scr.refresh()
            return

        self._draw_hud()
        self._draw_ground()
        self._draw_cities()
        self._draw_turrets()
        self._draw_trails(self.missiles, enemy=True)
        self._draw_trails(self.allies, enemy=False)
        self._draw_explosions()
        if self.state == ST_PLAY:
            self._draw_crosshair()
        self._draw_overlays()
        self.scr.refresh()

    def _draw_hud(self):
        a = self.C["hud"] | curses.A_BOLD
        left = " %s %07d   %s %02d   x%d" % (self.T("hud_score"), self.score,
                                             self.T("hud_wave"), self.wave,
                                             self.multiplier)
        self._put(0, 0, left.ljust(self.w - 1), a)

        parts = []
        for i, t in enumerate(self.turrets):
            if not t.alive:
                parts.append("%d.%s:XXXX" % (i + 1, t.letter))
            else:
                parts.append("%d.%s:%s%s" % (i + 1, t.letter, "|" * t.ammo,
                                             "." * (AMMO_PER_TURRET - t.ammo)))
        cities_left = sum(1 for c in self.cities if c.alive)
        line = " " + "  ".join(parts) + "   %s:%d/%d" % (self.T("hud_cities"),
                                                         cities_left, NUM_CITIES)
        self._put(1, 0, line.ljust(self.w - 1), self.C["hud"])

    def _draw_ground(self):
        self._put(self.ground_y, 0, "^" * (self.w - 1),
                  self.C["ground"] | curses.A_BOLD)

    def _draw_cities(self):
        for c in self.cities:
            if c.alive:
                self._put(c.y, c.x - 1, "[#]", self.C["city"] | curses.A_BOLD)
            else:
                self._put(c.y, c.x - 1, "...", self.C["rubble"])

    def _draw_turrets(self):
        for t in self.turrets:
            if t.alive:
                attr = self.C["turret"] | curses.A_BOLD
                if t.ammo == 0:
                    attr = self.C["rubble"]
                self._put(t.y, t.x - 1, "/%s\\" % t.letter, attr)
            else:
                self._put(t.y, t.x - 1, "_x_", self.C["rubble"])

    def _draw_trails(self, missiles, enemy):
        """Desenha o rastro (linha) e a cabeça brilhante de cada míssil."""
        if enemy:
            trail_attr = self.C["etrail"]
            head_attr = self.C["enemy"] | curses.A_BOLD
            trail_ch, head_ch = ':', '@'
        else:
            trail_attr = self.C["atrail"]
            head_attr = self.C["ally"] | curses.A_BOLD
            trail_ch, head_ch = '.', '^'

        for m in missiles:
            hx, hy = m.head()
            sx, sy = int(round(m.start.x)), int(round(m.start.y))
            for (x, y) in bresenham(sx, sy, hx, hy):
                if y < self.sky_top or y > self.base_y:
                    continue
                if (x, y) == (hx, hy):
                    continue
                self._put(y, x, trail_ch, trail_attr)
            if self.sky_top <= hy <= self.base_y:
                self._put(hy, hx, head_ch, head_attr)

    def _draw_explosions(self):
        """Preenche um disco (elipse corrigida por aspecto) com textura."""
        palette = ("e1", "e2", "e3", "e4")
        for e in self.explosions:
            r = e.radius
            if r <= 0:
                continue
            base = palette[int(e.age * 18) % len(palette)]
            attr = self.C[base] | curses.A_BOLD
            cy, cx = e.pos.y, e.pos.x
            y0 = max(self.sky_top, int(math.floor(cy - r)))
            y1 = min(self.base_y, int(math.ceil(cy + r)))
            for y in range(y0, y1 + 1):
                dy = y - cy
                if abs(dy) > r:
                    continue
                half = math.sqrt(max(0.0, r * r - dy * dy)) * ASPECT
                x0 = int(math.floor(cx - half))
                x1 = int(math.ceil(cx + half))
                for x in range(max(0, x0), min(self.w - 1, x1) + 1):
                    d = math.hypot((x - cx) / ASPECT, dy)
                    if d > r:
                        continue
                    ch = '@' if d < r * 0.45 else ('o' if d < r * 0.8 else '*')
                    self._put(y, x, ch, attr)

    def _draw_crosshair(self):
        x, y = int(self.cross.x), int(self.cross.y)
        a = self.C["cross"] | curses.A_BOLD
        self._put(y, x, "+", a)
        self._put(y, x - 2, "-", a)
        self._put(y, x + 2, "-", a)
        self._put(y - 1, x, "|", a)
        self._put(y + 1, x, "|", a)

    # ---------------------- telas sobrepostas -----------------------------
    def _box(self, lines, title=None):
        """Painel simples: todas as linhas com o mesmo atributo."""
        self._panel([(s, self.C["hud"] | curses.A_BOLD) for s in lines], title)

    def _panel(self, rows, title=None):
        """
        Painel centralizado com moldura, onde cada linha carrega seu próprio
        atributo de cor -> permite o degradê do banner ASCII.
        `rows` = lista de tuplas (texto, atributo).
        """
        if not rows:
            return
        wid = min(max(len(s) for s, _ in rows) + 4, self.w - 2)
        hei = len(rows) + 2
        top = max(0, (self.h - hei) // 2)
        left = max(0, (self.w - wid) // 2)
        frame = self.C["hud"] | curses.A_BOLD
        self._put(top, left, "+" + "-" * (wid - 2) + "+", frame)
        for i, (s, attr) in enumerate(rows):
            y = top + 1 + i
            self._put(y, left, "|", frame)
            self._put(y, left + wid - 1, "|", frame)
            pad = s.center(wid - 2)[:wid - 2]
            self._put(y, left + 1, pad, attr)
        self._put(top + hei - 1, left, "+" + "-" * (wid - 2) + "+", frame)
        if title:
            self._put(top, left + 2, "[ %s ]" % title,
                      self.C["title"] | curses.A_BOLD)

    def _banner_rows(self, text, palette=("e1", "e1", "e2", "e2", "e3")):
        """Gera as linhas do banner ASCII já com o degradê de cores."""
        return [(line, self.C[palette[i % len(palette)]] | curses.A_BOLD)
                for i, line in enumerate(banner(text))]

    def _title_rows(self):
        """
        Monta a abertura adaptando-se ao tamanho do terminal:
          - grande  : duas palavras em arte ASCII 5x5
          - médio   : só a segunda palavra em arte ASCII
          - pequeno : título em texto espaçado
        """
        dim = self.C["hud"]
        hi = self.C["title"] | curses.A_BOLD
        t1, t2 = self.T("title_1"), self.T("title_2")
        big = max(banner_width(t1), banner_width(t2)) + 6

        rows = []
        if self.w >= big and self.h >= 27:
            rows += self._banner_rows(t1)
            rows += self._banner_rows(t2)
        elif self.w >= banner_width(t2) + 6 and self.h >= 22:
            rows += [(" " + t1 + " ", hi)]
            rows += self._banner_rows(t2)
        else:
            rows += [(" ".join(self.T("title_small")), hi)]

        rows += [("", dim), (self.T("subtitle"), self.C["ally"])]
        rows += [("", dim)]
        for key in ("help_move", "help_fire", "help_space",
                    "help_lang", "help_pause"):
            rows.append((self.T(key), dim))
        rows += [("", dim), (self.T("help_goal"), self.C["city"])]
        rows += [("", dim), (self.T("start"), hi)]

        # Se ainda assim não couber na altura, corta a ajuda menos essencial.
        while len(rows) + 2 > self.h and len(rows) > 4:
            del rows[-4]
        return rows

    def _draw_overlays(self):
        if self.message_timer > 0 and self.state == ST_PLAY:
            self._put(self.sky_top, max(0, (self.w - len(self.message)) // 2),
                      self.message, self.C["title"] | curses.A_BOLD)

        if self.state == ST_TITLE:
            self._panel(self._title_rows(), self.T("briefing"))

        elif self.state == ST_PAUSE:
            dim = self.C["hud"]
            rows = [("", dim)]
            if self.w >= banner_width(self.T("pause_word")) + 6 and self.h >= 14:
                rows += self._banner_rows(self.T("pause_word"),
                                          ("e4", "e1", "e1", "e2", "e2"))
            else:
                rows += [(" ".join(self.T("pause_word")),
                          self.C["title"] | curses.A_BOLD)]
            rows += [("", dim), (self.T("pause_help"), dim), ("", dim)]
            self._panel(rows, self.T("pause_title"))

        elif self.state == ST_WAVE_END:
            self._panel([(s, self.C["hud"] | curses.A_BOLD)
                         for s in self.bonus_lines], self.T("bonus_title"))

        elif self.state == ST_GAMEOVER:
            acc = (100.0 * self.shots_hit / self.shots_fired) if self.shots_fired else 0.0
            dim = self.C["hud"] | curses.A_BOLD
            word = self.T("go_word")
            rows = []
            if self.w >= banner_width(word) + 6 and self.h >= 24:
                rows += self._banner_rows(word, ("e2", "e2", "e3", "e3", "e3"))
            else:
                rows += [(" ".join(word), self.C["enemy"] | curses.A_BOLD)]
            rows += [
                ("", dim),
                (self.T("go_msg"), self.C["warn"] | curses.A_BOLD),
                ("", dim),
                (self.T("go_waves", self.wave), dim),
                (self.T("go_acc", acc), dim),
                (self.T("go_score", self.score), self.C["title"] | curses.A_BOLD),
                ("", dim),
                (self.T("go_retry"), dim),
            ]
            self._panel(rows, self.T("go_title"))

    # ---------------------- GAME LOOP -------------------------------------
    def run(self):
        last = time.perf_counter()
        while self.running:
            now = time.perf_counter()
            dt = now - last
            last = now
            if dt > 0.1:            # protege a física contra travadas/lag
                dt = 0.1

            self.handle_input()     # 1) ENTRADA
            self.update(dt)         # 2) LÓGICA
            self.render()           # 3) RENDER

            # controle de framerate
            spare = FRAME_TIME - (time.perf_counter() - now)
            if spare > 0:
                time.sleep(spare)


# ---------------------------------------------------------------------------
# 5) BOOTSTRAP
# ---------------------------------------------------------------------------

def main(stdscr):
    global LAST_LANG
    random.seed()
    g = Game(stdscr)
    g.run()
    LAST_LANG = g.lang


if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
    print(STRINGS[LAST_LANG]["bye"])
