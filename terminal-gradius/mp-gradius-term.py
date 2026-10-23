#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MP-GRADIUS-TERM
===============
Shoot'em up horizontal estilo Gradius (Konami) rodando inteiramente no terminal.
Usa apenas Python 3 + biblioteca padrao (curses).

Execucao:
    python3 mp-gradius-term.py

Variaveis de ambiente opcionais:
    MP_GRADIUS_ASCII=1   -> forca modo 100% ASCII (terminais sem UTF-8)

Controles: veja o README.md ou a tela de menu.
"""

import curses
import json
import locale
import math
import os
import random
import time
from collections import deque

# =====================================================================
#  CONSTANTES DE BALANCEAMENTO  (ajuste livremente para calibrar o jogo)
# =====================================================================

FPS_ALVO = 45                 # quadros por segundo desejados
LARGURA_MIN, ALTURA_MIN = 80, 24
ASPECTO = 2.0                 # 1 linha "vale" 2 colunas (celulas do terminal sao altas)

# --- Jogador ---
VIDAS_INICIAIS = 3
VEL_BASE_X = 32.0             # colunas/segundo
VEL_BASE_Y = 16.0             # linhas/segundo
BONUS_SPEED = 0.22            # +22% de velocidade por nivel de Speed
MAX_SPEED = 5                 # niveis maximos de Speed
TEMPO_INVENCIVEL = 2.5        # segundos piscando apos ser atingido
TEMPO_IMPULSO = 0.13          # "memoria" da tecla (emula tecla pressionada)

# --- Armas ---
CD_VULCAN = [0.17, 0.13, 0.10]   # cooldown por nivel de Vulcan (1,2,3)
DANO_VULCAN = [1, 1, 2]
VEL_TIRO = 74.0
CD_DOUBLE = 0.17
CD_LASER = 0.30
VEL_LASER = 135.0
DANO_LASER = 2
CD_MISSIL = 0.60
VEL_MISSIL_X = 34.0
VEL_MISSIL_Y = 20.0
DANO_MISSIL = 3
RAIO_EXPLOSAO_X = 5           # meia-largura da explosao do missil
RAIO_EXPLOSAO_Y = 2           # meia-altura
MAX_OPTIONS = 2
ATRASO_OPTION = 9             # quadros de atraso entre a nave e cada Option
LIMITE_TIROS = 160            # teto de projeteis simultaneos (performance)

# Pontuacao necessaria para subir o nivel do canhao padrao (Vulcan)
LIMIARES_VULCAN = [5000, 14000]

# --- Inimigos ---
VEL_SCROLL = 11.0             # velocidade do cenario/estruturas fixas
VEL_TIRO_INIMIGO = 24.0
DIFICULDADE_MAX = 1.8         # multiplicador maximo de cadencia inimiga

# --- Chefe ---
CHEFE_HP = 300
CHEFE_DANO_NUCLEO = 4         # multiplicador de dano no ponto fraco
CHEFE_VEL_Y = 5.0
CHEFE_FASE2 = 0.5             # fracao de HP que dispara a segunda fase
CD_ATAQUE_CHEFE = 2.0

# --- Fase ---
DURACAO_FASE = 105.0          # segundos de ondas antes do aviso de chefe
TEMPO_WARNING = 3.4

ARQUIVO_RECORDE = os.path.join(os.path.expanduser("~"), ".mp-gradius-term_hs.json")

# =====================================================================
#  GLIFOS (com fallback ASCII)
# =====================================================================

ASCII_PURO = (os.environ.get("MP_GRADIUS_ASCII", "0") == "1"
              or os.environ.get("GRADIUS_ASCII", "0") == "1")


def g(uni, asc):
    """Devolve o glifo unicode ou o equivalente ASCII conforme o modo."""
    return asc if ASCII_PURO else uni


GLIFO_ESTRELA = [".", g("·", "."), "*", "+", g("°", "o")]
GLIFO_CHAO = g("▄", "_")
GLIFO_PICO = g("▲", "^")
GLIFO_VIDA = g("♥", "*")
GLIFO_BALA_INIMIGA = g("•", "o")
GLIFO_LASER = g("═", "=")
GLIFO_CAPSULA = "?"

TITULO_UNI = [
    " ██████╗ ██████╗  █████╗ ██████╗ ██╗██╗   ██╗███████╗",
    "██╔════╝ ██╔══██╗██╔══██╗██╔══██╗██║██║   ██║██╔════╝",
    "██║  ███╗██████╔╝███████║██║  ██║██║██║   ██║███████╗",
    "██║   ██║██╔══██╗██╔══██║██║  ██║██║██║   ██║╚════██║",
    "╚██████╔╝██║  ██║██║  ██║██████╔╝██║╚██████╔╝███████║",
    " ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚═╝ ╚═════╝ ╚══════╝",
]
TITULO_ASC = [
    " #####  ####    ##   ####   ##  #    #  ####",
    "#       #   #  #  #  #   #  ##  #    # #    ",
    "#  ###  ####  ######  #  #  ##  #    #  ###  ",
    "#    #  #  #  #    #  #  #  ##  #    #     # ",
    " ####   #   # #    # ####   ##   ####   ####  ",
]

# indices dos pares de cor (a inicializacao real acontece em iniciar_cores)
C_BRANCO, C_CIANO, C_VERDE, C_AMARELO, C_VERMELHO, C_MAGENTA, C_AZUL, C_CINZA = range(1, 9)


# =====================================================================
#  NAVES JOGAVEIS
#  Cada nave usa o MESMO sistema de upgrades, mas muda estatisticas-base
#  e ganha um traco exclusivo. "glifos" = (cauda, cauda_speed3, corpo,
#  corpo_double, nariz, nariz_laser) usados para montar o sprite.
# =====================================================================

NAVES = [
    {
        "id": "VIC-01",
        "cor": C_VERDE,
        "lema": "Equilibrada: nenhum bonus, nenhuma penalidade. A referencia.",
        "traco": "Sem bonus e sem penalidade: o arsenal classico do Gradius.",
        "vel": 1.00, "vidas": 3, "cd_vulcan": 1.00, "perda_speed": 1,
        "missile_inicial": False, "raio_x": RAIO_EXPLOSAO_X, "raio_y": RAIO_EXPLOSAO_Y,
        "dano_laser": DANO_LASER, "options_fixos": False, "tiro_traseiro": False,
        "laser_atrasado": False,
        "glifos": ("-", g("\u00ab", "<"), "=", "^", ">", g("\u00bb", ")")),
    },
    {
        "id": "FALCAO",
        "cor": C_CIANO,
        "lema": "Rapida e fragil: para quem confia no desvio.",
        "traco": "+25% de velocidade e cadencia; perde 2 Speed ao ser atingida.",
        "vel": 1.25, "vidas": 2, "cd_vulcan": 0.75, "perda_speed": 2,
        "missile_inicial": False, "raio_x": RAIO_EXPLOSAO_X, "raio_y": RAIO_EXPLOSAO_Y,
        "dano_laser": DANO_LASER, "options_fixos": False, "tiro_traseiro": False,
        "laser_atrasado": False,
        "glifos": ("~", g("\u2248", "="), "-", "^", ">", g("\u00bb", ")")),
    },
    {
        "id": "MARTELO",
        "cor": C_VERMELHO,
        "lema": "Blindada e lenta: dominio de area pelo chao.",
        "traco": "Nasce com MISSILE e explosao maior; LASER so na 2a volta da barra.",
        "vel": 0.80, "vidas": 4, "cd_vulcan": 1.00, "perda_speed": 1,
        "missile_inicial": True, "raio_x": 7, "raio_y": 3,
        "dano_laser": DANO_LASER, "options_fixos": False, "tiro_traseiro": False,
        "laser_atrasado": True,
        "glifos": ("#", g("\u00ab", "<"), "=", "^", "D", ")"),
    },
    {
        "id": "ESPECTRO",
        "cor": C_MAGENTA,
        "lema": "Posicionamento: muro de tiro vertical e laser reforcado.",
        "traco": "Options fixos acima/abaixo; LASER 3; DOUBLE vira tiro traseiro.",
        "vel": 1.00, "vidas": 3, "cd_vulcan": 1.00, "perda_speed": 1,
        "missile_inicial": False, "raio_x": RAIO_EXPLOSAO_X, "raio_y": RAIO_EXPLOSAO_Y,
        "dano_laser": 3, "options_fixos": True, "tiro_traseiro": True,
        "laser_atrasado": False,
        "glifos": ("<", g("\u00ab", "<"), "-", "^", ">", g("\u00bb", ")")),
    },
]


def sprite_nave(cfg, missile=False, double=False, laser=False, speed=0):
    """Monta o sprite de 3 caracteres de uma nave conforme o arsenal equipado."""
    cauda, cauda_spd, corpo, corpo_dbl, nariz, nariz_laser = cfg["glifos"]
    c0 = cauda_spd if speed >= 3 else ("*" if missile else cauda)
    c1 = corpo_dbl if double else corpo
    c2 = nariz_laser if laser else nariz
    return c0 + c1 + c2


def stats_nave(cfg):
    """Linha curta de estatisticas para a tela de selecao."""
    return (f"VEL {int(cfg['vel'] * 100):3d}%   VIDAS {cfg['vidas']}   "
            f"CADENCIA {int(100 / cfg['cd_vulcan']):3d}%   LASER {cfg['dano_laser']}")


# =====================================================================
#  CORES
# =====================================================================

CORES_OK = False


def iniciar_cores():
    """Inicializa os pares de cores; silenciosamente ignora terminais monocromaticos."""
    global CORES_OK
    try:
        curses.start_color()
        curses.use_default_colors()
    except curses.error:
        return
    if not curses.has_colors():
        return
    pares = {
        C_BRANCO: curses.COLOR_WHITE,
        C_CIANO: curses.COLOR_CYAN,
        C_VERDE: curses.COLOR_GREEN,
        C_AMARELO: curses.COLOR_YELLOW,
        C_VERMELHO: curses.COLOR_RED,
        C_MAGENTA: curses.COLOR_MAGENTA,
        C_AZUL: curses.COLOR_BLUE,
        C_CINZA: curses.COLOR_WHITE,
    }
    for par, cor_fg in pares.items():
        try:
            curses.init_pair(par, cor_fg, -1)
        except curses.error:
            pass
    CORES_OK = True


def cor(par, negrito=False):
    """Atributo de cor seguro (0 se o terminal nao suporta cores)."""
    attr = curses.color_pair(par) if CORES_OK else 0
    if negrito:
        attr |= curses.A_BOLD
    return attr


# =====================================================================
#  UTILITARIOS
# =====================================================================


def colide(ax, ay, al, aa, bx, by, bl, ba):
    """Colisao AABB entre dois retangulos (x, y, largura, altura)."""
    return ax < bx + bl and bx < ax + al and ay < by + ba and by < ay + aa


def direcao(dx, dy):
    """Normaliza um vetor compensando o fato de as celulas do terminal serem altas."""
    dyv = dy * ASPECTO
    mag = math.hypot(dx, dyv)
    if mag < 1e-6:
        return 1.0, 0.0
    return dx / mag, (dyv / mag) / ASPECTO


def blit(tela, x, y, linhas, attr=0, topo=0, base=None, esq=0, dire=None):
    """Desenha uma lista de linhas na tela; espacos sao transparentes; recorta nas bordas."""
    alt_tela, larg_tela = tela.getmaxyx()
    if base is None:
        base = alt_tela - 1
    if dire is None:
        dire = larg_tela - 1
    base = min(base, alt_tela - 1)
    dire = min(dire, larg_tela - 1)
    ix, iy = int(round(x)), int(round(y))
    for i, linha in enumerate(linhas):
        ly = iy + i
        if ly < topo or ly > base:
            continue
        for j, ch in enumerate(linha):
            if ch == " ":
                continue
            cx = ix + j
            if cx < esq or cx > dire:
                continue
            if ly == alt_tela - 1 and cx == larg_tela - 1:
                continue  # escrever no canto inferior direito quebra o curses
            try:
                tela.addstr(ly, cx, ch, attr)
            except curses.error:
                pass


def escrever(tela, x, y, texto, attr=0):
    """Escreve um texto inteiro (espacos inclusive) - usado em barras destacadas."""
    alt, larg = tela.getmaxyx()
    if not (0 <= y < alt):
        return
    texto = texto[: max(0, larg - x - (1 if y == alt - 1 else 0))]
    try:
        tela.addstr(y, x, texto, attr)
    except curses.error:
        pass


def texto_centralizado(tela, y, texto, attr=0):
    alt, larg = tela.getmaxyx()
    x = max(0, (larg - len(texto)) // 2)
    escrever(tela, x, y, texto[: larg - 1], attr)


def carregar_recorde():
    try:
        with open(ARQUIVO_RECORDE, "r", encoding="utf-8") as fp:
            return int(json.load(fp).get("recorde", 0))
    except Exception:
        return 0


def salvar_recorde(valor):
    try:
        with open(ARQUIVO_RECORDE, "w", encoding="utf-8") as fp:
            json.dump({"recorde": int(valor)}, fp)
    except Exception:
        pass  # sem permissao de escrita: apenas ignora


# =====================================================================
#  ENTIDADES BASE
# =====================================================================


class Entidade:
    """Qualquer coisa desenhavel com posicao em ponto flutuante e sprite multilinha."""

    def __init__(self, x, y, sprite, attr=0):
        self.x = float(x)
        self.y = float(y)
        self.sprite = list(sprite)
        self.attr = attr
        self.vivo = True

    @property
    def larg(self):
        return max((len(l) for l in self.sprite), default=1)

    @property
    def alt(self):
        return len(self.sprite)

    @property
    def cx(self):
        return self.x + self.larg / 2.0

    @property
    def cy(self):
        return self.y + self.alt / 2.0

    def caixa(self):
        return (self.x, self.y, self.larg, self.alt)

    def desenhar(self, tela, jogo):
        blit(tela, self.x, self.y, self.sprite, self.attr, topo=jogo.topo, base=jogo.base)


# ---------------------------------------------------------------------
#  PROJETEIS
# ---------------------------------------------------------------------


class Tiro(Entidade):
    """Projetil generico (do jogador ou do inimigo)."""

    def __init__(self, x, y, vx, vy, sprite, attr, dano=1, do_jogador=True,
                 perfurante=False, teleguiado=False, vida=6.0):
        super().__init__(x, y, sprite, attr)
        self.vx = vx
        self.vy = vy
        self.dano = dano
        self.do_jogador = do_jogador
        self.perfurante = perfurante
        self.teleguiado = teleguiado
        self.tempo = vida
        self.atingidos = set()   # ids ja acertados (para o laser perfurante)

    def atualizar(self, dt, jogo):
        if self.teleguiado and jogo.jogador and jogo.jogador.ativo:
            nx, ny = direcao(jogo.jogador.cx - self.cx, jogo.jogador.cy - self.cy)
            vel = math.hypot(self.vx, self.vy * ASPECTO)
            # curva suave em direcao ao jogador
            self.vx += (nx * vel - self.vx) * min(1.0, dt * 1.6)
            self.vy += (ny * vel - self.vy) * min(1.0, dt * 1.6)
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.tempo -= dt
        if (self.tempo <= 0 or self.x < -8 or self.x > jogo.larg + 8
                or self.y < jogo.topo - 2 or self.y > jogo.base + 2):
            self.vivo = False


class Missil(Entidade):
    """Missil em arco: desce ate o chao, depois desliza rente ao solo e explode em area."""

    def __init__(self, x, y, attr, do_jogador=True,
                 raio_x=RAIO_EXPLOSAO_X, raio_y=RAIO_EXPLOSAO_Y):
        super().__init__(x, y, [g("◣", ">") + "="], attr)
        self.raio_x = raio_x
        self.raio_y = raio_y
        self.vx = VEL_MISSIL_X
        self.vy = VEL_MISSIL_Y
        self.no_chao = False
        self.do_jogador = do_jogador
        self.dano = DANO_MISSIL
        self.perfurante = False
        self.teleguiado = False
        self.atingidos = set()

    def atualizar(self, dt, jogo):
        if not self.no_chao and self.y >= jogo.base - 1:
            self.no_chao = True
            self.y = jogo.base - 1
            self.vy = 0.0
            self.vx = VEL_MISSIL_X * 1.15
            self.sprite = ["=" + g("◢", ">")]
        self.x += self.vx * dt
        self.y += self.vy * dt
        if self.x > jogo.larg + 4 or self.y > jogo.base + 1:
            self.vivo = False

    def explodir(self, jogo):
        """Detona causando dano em area a todos os inimigos proximos."""
        self.vivo = False
        jogo.criar_explosao(self.cx, self.cy, grande=True)
        for ini in jogo.inimigos:
            if not ini.vivo:
                continue
            if colide(self.cx - self.raio_x, self.cy - self.raio_y,
                      self.raio_x * 2, self.raio_y * 2, *ini.caixa()):
                ini.levar_dano(DANO_MISSIL, jogo)
        if jogo.chefe and jogo.chefe.vivo:
            b = jogo.chefe
            if colide(self.cx - self.raio_x, self.cy - self.raio_y,
                      self.raio_x * 2, self.raio_y * 2, *b.caixa()):
                b.levar_dano(DANO_MISSIL, jogo, nucleo=False)


class Explosao(Entidade):
    """Efeito visual temporario."""

    QUADROS_P = [["*"], [g("¤", "o")], ["+"], ["."]]
    QUADROS_G = [
        [" * ", "*#*", " * "],
        ["\\|/", "-@-", "/|\\"],
        [" + ", "+.+", " + "],
        ["   ", " . ", "   "],
    ]

    def __init__(self, x, y, grande=False):
        self.grande = grande
        quadros = self.QUADROS_G if grande else self.QUADROS_P
        super().__init__(x - (1 if grande else 0), y - (1 if grande else 0), quadros[0])
        self.t = 0.0
        self.dur = 0.34 if grande else 0.20

    def atualizar(self, dt, jogo):
        self.t += dt
        quadros = self.QUADROS_G if self.grande else self.QUADROS_P
        idx = min(len(quadros) - 1, int(self.t / self.dur * len(quadros)))
        self.sprite = quadros[idx]
        self.attr = cor(C_AMARELO if idx < 2 else C_VERMELHO, True)
        if self.t >= self.dur:
            self.vivo = False


# ---------------------------------------------------------------------
#  POWER-UP (capsula)
# ---------------------------------------------------------------------


class PowerUp(Entidade):
    """Capsula '?' que flutua pela tela ate ser capturada pelo toque da nave."""

    def __init__(self, x, y):
        super().__init__(x, y, [GLIFO_CAPSULA])
        self.vx = -VEL_SCROLL * 1.1
        self.fase = random.uniform(0, math.tau)
        self.t = 0.0

    def atualizar(self, dt, jogo):
        self.t += dt
        self.x += self.vx * dt
        self.y += math.sin(self.t * 2.2 + self.fase) * 4.5 * dt
        self.y = max(jogo.topo, min(jogo.base - 1, self.y))
        if self.x < -2:
            self.vivo = False

    def desenhar(self, tela, jogo):
        pisca = int(self.t * 8) % 2 == 0
        attr = cor(C_AMARELO, True) if pisca else cor(C_VERMELHO, True)
        blit(tela, self.x, self.y, [GLIFO_CAPSULA], attr, topo=jogo.topo, base=jogo.base)


# =====================================================================
#  POWER METER  (barra de upgrades estilo Gradius)
# =====================================================================


class PowerMeter:
    """
    Barra incremental e nao destrutiva.
    Cada capsula avanca a selecao: MISSILE -> DOUBLE -> LASER -> OPTION -> SPEED -> (volta).
    A tecla ESPACO aplica o upgrade selecionado.
    """

    SLOTS = ["MISSILE", "DOUBLE", "LASER", "OPTION", "SPEED"]

    def __init__(self, nave=None):
        self.selecao = -1        # -1 = nenhum slot aceso
        self.flash = 0.0         # brilho apos ativar
        self.voltas = 0          # quantas vezes a barra ja deu a volta completa
        # o MARTELO so libera o LASER a partir da segunda volta da barra
        self.laser_atrasado = bool(nave and nave.get("laser_atrasado"))

    def bloqueado(self, nome):
        """Slots que ainda nao estao disponiveis para esta nave."""
        return nome == "LASER" and self.laser_atrasado and self.voltas < 1

    def capturar(self):
        """Avanca um slot (volta ao inicio depois do Speed), pulando slots bloqueados."""
        for _ in range(len(self.SLOTS)):
            if self.selecao < 0:
                self.selecao = 0
            else:
                self.selecao = (self.selecao + 1) % len(self.SLOTS)
                if self.selecao == 0:
                    self.voltas += 1
            if not self.bloqueado(self.SLOTS[self.selecao]):
                break

    def atualizar(self, dt):
        if self.flash > 0:
            self.flash = max(0.0, self.flash - dt)

    def ativar(self, jogador, jogo):
        """Aplica o upgrade aceso. Retorna True se algo mudou."""
        if self.selecao < 0:
            return False
        nome = self.SLOTS[self.selecao]
        ok = jogador.aplicar_upgrade(nome, jogo)
        if ok:
            self.selecao = -1
            self.flash = 0.35
        return ok


# =====================================================================
#  OPTION  (nave-fantasma que repete o disparo do jogador)
# =====================================================================


class Option(Entidade):
    """
    Nave-fantasma que repete a arma equipada no momento.
    Modo padrao: segue o rastro da nave com atraso.
    Modo fixo (ESPECTRO): fica travada acima/abaixo da nave, formando um muro de tiro.
    """

    OFFSETS_FIXOS = [-2, 2, -4, 4]

    def __init__(self, indice, fixo=False):
        super().__init__(0, 0, [g("◉", "O")], cor(C_AMARELO, True))
        self.indice = indice
        self.fixo = fixo

    def atualizar(self, dt, jogo):
        p = jogo.jogador
        if self.fixo:
            dy = self.OFFSETS_FIXOS[self.indice % len(self.OFFSETS_FIXOS)]
            self.x = p.x
            self.y = max(jogo.topo, min(jogo.base - 1, p.y + dy))
            return
        hist = p.rastro
        idx = len(hist) - 1 - ATRASO_OPTION * (self.indice + 1)
        if 0 <= idx < len(hist):
            self.x, self.y = hist[idx]


# =====================================================================
#  JOGADOR
# =====================================================================


class Jogador(Entidade):
    """Nave do jogador: movimento em 8 direcoes, arsenal acumulativo e invencibilidade."""

    def __init__(self, jogo, nave=None):
        self.nave = nave or NAVES[0]
        super().__init__(6, jogo.topo + (jogo.base - jogo.topo) // 2,
                         [sprite_nave(self.nave)])
        self.vidas = self.nave["vidas"]
        self.rastro = deque(maxlen=ATRASO_OPTION * (MAX_OPTIONS + 1) + 4)
        self.impulso = {"cima": 0.0, "baixo": 0.0, "esq": 0.0, "dir": 0.0}
        self.resetar_arsenal()
        self.invencivel = TEMPO_INVENCIVEL
        self.ativo = True
        self.t = 0.0

    # ---------------- arsenal ----------------
    def resetar_arsenal(self):
        self.nivel_vulcan = 1
        self.tem_missile = False
        self.tem_double = False
        self.tem_laser = False
        self.nivel_speed = 0
        self.options = []
        if self.nave["missile_inicial"]:      # MARTELO ja nasce com misseis
            self.tem_missile = True
        self.cd_tiro = 0.0
        self.cd_missil = 0.0
        self.cd_laser = 0.0

    def aplicar_upgrade(self, nome, jogo):
        """Cada upgrade SOMA ao arsenal existente (nunca substitui)."""
        if nome == "MISSILE":
            if self.tem_missile:
                return False
            self.tem_missile = True
        elif nome == "DOUBLE":
            if self.tem_double:
                return False
            self.tem_double = True
        elif nome == "LASER":
            if self.tem_laser:
                return False
            self.tem_laser = True
        elif nome == "OPTION":
            if len(self.options) >= MAX_OPTIONS:
                return False
            self.options.append(Option(len(self.options), self.nave["options_fixos"]))
        elif nome == "SPEED":
            if self.nivel_speed >= MAX_SPEED:
                return False
            self.nivel_speed += 1
        jogo.mensagem(f"{nome} ATIVADO!", 1.4)
        return True

    # ---------------- aparencia ----------------
    def atualizar_sprite(self):
        """A nave muda visualmente conforme as armas equipadas (glifos proprios de cada nave)."""
        self.sprite = [sprite_nave(self.nave, self.tem_missile, self.tem_double,
                                   self.tem_laser, self.nivel_speed)]

    # ---------------- movimento ----------------
    def pressionar(self, direcao_nome):
        self.impulso[direcao_nome] = TEMPO_IMPULSO

    def atualizar(self, dt, jogo):
        self.t += dt
        for k in self.impulso:
            self.impulso[k] = max(0.0, self.impulso[k] - dt)

        mult = (1.0 + BONUS_SPEED * self.nivel_speed) * self.nave["vel"]
        dx = (1 if self.impulso["dir"] > 0 else 0) - (1 if self.impulso["esq"] > 0 else 0)
        dy = (1 if self.impulso["baixo"] > 0 else 0) - (1 if self.impulso["cima"] > 0 else 0)
        if dx and dy:            # diagonal: normaliza para nao ficar mais rapido
            mult *= 0.78
        self.x += dx * VEL_BASE_X * mult * dt
        self.y += dy * VEL_BASE_Y * mult * dt

        # limites da tela
        self.x = max(0, min(jogo.larg - self.larg, self.x))
        self.y = max(jogo.topo, min(jogo.base - 1, self.y))

        self.rastro.append((self.x, self.y))
        for op in self.options:
            op.atualizar(dt, jogo)

        if self.invencivel > 0:
            self.invencivel = max(0.0, self.invencivel - dt)

        # cooldowns
        self.cd_tiro = max(0.0, self.cd_tiro - dt)
        self.cd_missil = max(0.0, self.cd_missil - dt)
        self.cd_laser = max(0.0, self.cd_laser - dt)

        # nivel do Vulcan sobe conforme a pontuacao
        nivel = 1
        for lim in LIMIARES_VULCAN:
            if jogo.score >= lim:
                nivel += 1
        self.nivel_vulcan = nivel
        self.atualizar_sprite()

    # ---------------- disparo ----------------
    def atirar(self, jogo):
        """Dispara todas as armas cujo cooldown estiver pronto (nave + Options)."""
        pontos = [(self.x + self.larg, self.cy)]
        for op in self.options:
            pontos.append((op.x + 1, op.y))

        if self.cd_tiro <= 0:
            self.cd_tiro = CD_VULCAN[self.nivel_vulcan - 1] * self.nave["cd_vulcan"]
            dano = DANO_VULCAN[self.nivel_vulcan - 1]
            for px, py in pontos:
                jogo.add_tiro(Tiro(px, py, VEL_TIRO, 0, ["-"], cor(C_BRANCO, True), dano))
                if self.tem_double:
                    if self.nave["tiro_traseiro"]:
                        # ESPECTRO: em vez da diagonal, um tiro para tras
                        jogo.add_tiro(Tiro(px - self.larg - 1, py, -VEL_TIRO, 0,
                                           ["-"], cor(C_MAGENTA, True), dano))
                    else:
                        # Double classico: tiro extra em diagonal para cima
                        nx, ny = direcao(1.0, -1.0)
                        jogo.add_tiro(Tiro(px, py, nx * VEL_TIRO, ny * VEL_TIRO,
                                           ["/"], cor(C_CIANO, True), dano))

        if self.tem_laser and self.cd_laser <= 0:
            self.cd_laser = CD_LASER
            for px, py in pontos:
                jogo.add_tiro(Tiro(px, py, VEL_LASER, 0, [GLIFO_LASER * 6],
                                   cor(C_CIANO, True), self.nave["dano_laser"],
                                   perfurante=True))

        if self.tem_missile and self.cd_missil <= 0:
            self.cd_missil = CD_MISSIL
            for px, py in pontos:
                jogo.add_tiro(Missil(px, py + 1, cor(C_VERMELHO, True),
                                     raio_x=self.nave["raio_x"], raio_y=self.nave["raio_y"]))

    # ---------------- dano ----------------
    def atingido(self, jogo):
        if self.invencivel > 0 or not self.ativo:
            return
        self.vidas -= 1
        jogo.criar_explosao(self.cx, self.cy, grande=True)
        if self.vidas <= 0:
            self.ativo = False
            jogo.game_over()
            return
        # penalidade classica: perde Options e volta ao inicio da tela
        self.options = []
        self.nivel_speed = max(0, self.nivel_speed - self.nave["perda_speed"])
        self.x = 6
        self.y = jogo.topo + (jogo.base - jogo.topo) // 2
        self.invencivel = TEMPO_INVENCIVEL
        jogo.mensagem("NAVE ATINGIDA!", 1.2)

    def desenhar(self, tela, jogo):
        # pisca durante a invencibilidade
        if self.invencivel > 0 and int(self.t * 12) % 2 == 0:
            return
        attr = cor(self.nave["cor"], True)
        blit(tela, self.x, self.y, self.sprite, attr, topo=jogo.topo, base=jogo.base)
        for op in self.options:
            blit(tela, op.x + 1, op.y, op.sprite, cor(C_AMARELO, True),
                 topo=jogo.topo, base=jogo.base)


# =====================================================================
#  INIMIGOS
# =====================================================================

# tipo: (sprite, hp, pontos, cor, solta_capsula)
TIPOS_INIMIGO = {
    "BATEDOR":    (["<*>"], 1, 100, C_CIANO, False),
    "CACADOR":    ([">@<"], 2, 200, C_AMARELO, False),
    "RASTEJANTE": (["(o)"], 3, 250, C_VERDE, False),
    "CANHAO":     ([" ^ ", "[=]"], 3, 300, C_MAGENTA, False),
    "GRANDE":     ([" /===\\", "<[###]>", " \\===/"], 12, 800, C_VERMELHO, True),
    "VILA":       (["[^^^]", "|:::|", "'---'"], 8, 600, C_BRANCO, True),
}


class Inimigo(Entidade):
    """Inimigo com padrao de movimento fixo definido pelo tipo."""

    def __init__(self, tipo, x, y, jogo, formacao=None):
        sprite, hp, pontos, c, capsula = TIPOS_INIMIGO[tipo]
        super().__init__(x, y, sprite, cor(c, True))
        self.tipo = tipo
        self.hp = hp
        self.hp_max = hp
        self.pontos = pontos
        self.solta_capsula = capsula
        self.formacao = formacao
        self.t = random.uniform(0, 6.28)
        self.cd_tiro = random.uniform(1.0, 2.5)
        self.y0 = float(y)
        self.flash = 0.0

    # ------------- padroes de movimento -------------
    def atualizar(self, dt, jogo):
        self.t += dt
        self.flash = max(0.0, self.flash - dt)
        jog = jogo.jogador

        if self.tipo == "BATEDOR":              # zigue-zague rapido
            self.x -= 27.0 * dt
            self.y = self.y0 + math.sin(self.t * 3.4) * 4.0

        elif self.tipo == "CACADOR":            # persegue a linha do jogador
            self.x -= 17.0 * dt
            if jog and jog.ativo:
                alvo = jog.cy - self.alt / 2.0
                self.y += max(-9.0 * dt, min(9.0 * dt, (alvo - self.y) * dt * 2.6))
            self.tentar_atirar(dt, jogo, intervalo=2.4)

        elif self.tipo == "RASTEJANTE":         # rasteja pelo chao
            self.x -= 13.0 * dt
            self.y = jogo.base - self.alt
            self.tentar_atirar(dt, jogo, intervalo=3.0)

        elif self.tipo == "CANHAO":             # fixo no cenario, so atira
            self.x -= VEL_SCROLL * dt
            self.y = jogo.base - self.alt
            self.tentar_atirar(dt, jogo, intervalo=2.1)

        elif self.tipo == "GRANDE":             # nave-mae com leque de tiros
            self.x -= 9.0 * dt
            self.y = self.y0 + math.sin(self.t * 0.9) * 3.0
            self.tentar_atirar(dt, jogo, intervalo=2.2, leque=3)

        elif self.tipo == "VILA":               # estrutura flutuante do cenario
            self.x -= VEL_SCROLL * dt
            self.y = self.y0 + math.sin(self.t * 0.6) * 1.2
            self.tentar_atirar(dt, jogo, intervalo=3.2)

        self.y = max(jogo.topo, min(jogo.base - self.alt, self.y))
        if self.x < -self.larg - 2:
            self.vivo = False
            if self.formacao is not None:
                jogo.formacoes.pop(self.formacao, None)  # formacao escapou: sem bonus

    def tentar_atirar(self, dt, jogo, intervalo=2.5, leque=1):
        if not jogo.jogador or not jogo.jogador.ativo:
            return
        self.cd_tiro -= dt * jogo.dificuldade
        if self.cd_tiro > 0:
            return
        self.cd_tiro = intervalo * random.uniform(0.8, 1.3)
        nx, ny = direcao(jogo.jogador.cx - self.cx, jogo.jogador.cy - self.cy)
        angs = [0.0] if leque == 1 else [-0.35, 0.0, 0.35][:leque]
        for a in angs:
            ca, sa = math.cos(a), math.sin(a)
            vx = (nx * ca - ny * ASPECTO * sa)
            vy = (nx * sa / ASPECTO + ny * ca)
            jogo.add_tiro(Tiro(self.cx, self.cy, vx * VEL_TIRO_INIMIGO,
                               vy * VEL_TIRO_INIMIGO, [GLIFO_BALA_INIMIGA],
                               cor(C_VERMELHO, True), 1, do_jogador=False, vida=9.0))

    # ------------- dano / morte -------------
    def levar_dano(self, dano, jogo):
        if not self.vivo:
            return
        self.hp -= dano
        self.flash = 0.08
        if self.hp <= 0:
            self.vivo = False
            jogo.score += self.pontos
            jogo.criar_explosao(self.cx, self.cy, grande=self.larg > 4)
            if self.solta_capsula:
                jogo.soltar_capsula(self.cx, self.cy)
            if self.formacao is not None:
                # destruir a formacao inteira tambem solta uma capsula
                jogo.formacoes[self.formacao] = jogo.formacoes.get(self.formacao, 0) - 1
                if jogo.formacoes[self.formacao] <= 0:
                    jogo.formacoes.pop(self.formacao, None)
                    jogo.soltar_capsula(self.cx, self.cy)

    def desenhar(self, tela, jogo):
        attr = cor(C_BRANCO, True) if self.flash > 0 else self.attr
        blit(tela, self.x, self.y, self.sprite, attr, topo=jogo.topo, base=jogo.base)


# =====================================================================
#  CHEFE DE FASE
# =====================================================================


class Chefe(Entidade):
    """Chefe com barra de HP, ponto fraco (nucleo) e tres padroes de ataque."""

    SPRITE_F1 = [
        "   /------\\",
        "  /########\\",
        " |###/--\\###|",
        "=[O]#|##|###|",
        " |###\\--/###|",
        "  \\########/",
        "   \\------/",
    ]
    SPRITE_F2 = [l.replace("#", "%") for l in SPRITE_F1]

    def __init__(self, jogo):
        super().__init__(jogo.larg + 4, jogo.topo + 2, list(Chefe.SPRITE_F1),
                         cor(C_MAGENTA, True))
        self.hp = CHEFE_HP
        self.hp_max = CHEFE_HP
        self.entrando = True
        self.fase2 = False
        self.vy = CHEFE_VEL_Y
        self.cd_ataque = 2.0
        self.padrao = 0
        self.t = 0.0
        self.flash = 0.0
        self.morrendo = 0.0

    # nucleo (ponto fraco): "[O]" na linha 3, colunas 1..3
    def caixa_nucleo(self):
        return (self.x + 1, self.y + 3, 3, 1)

    def atualizar(self, dt, jogo):
        self.t += dt
        self.flash = max(0.0, self.flash - dt)

        if self.morrendo > 0:
            self.morrendo -= dt
            if random.random() < 0.6:
                jogo.criar_explosao(self.x + random.uniform(0, self.larg),
                                    self.y + random.uniform(0, self.alt), grande=True)
            if self.morrendo <= 0:
                self.vivo = False
                jogo.vitoria()
            return

        alvo_x = jogo.larg - self.larg - 3
        if self.entrando:
            self.x -= 14.0 * dt
            if self.x <= alvo_x:
                self.x = alvo_x
                self.entrando = False
            return

        # oscila verticalmente
        self.y += self.vy * dt * (1.5 if self.fase2 else 1.0)
        if self.y < jogo.topo:
            self.y, self.vy = float(jogo.topo), abs(self.vy)
        if self.y + self.alt > jogo.base:
            self.y, self.vy = float(jogo.base - self.alt), -abs(self.vy)

        self.cd_ataque -= dt
        if self.cd_ataque <= 0:
            self.cd_ataque = CD_ATAQUE_CHEFE * (0.6 if self.fase2 else 1.0)
            self.executar_ataque(jogo)

    def executar_ataque(self, jogo):
        """Alterna entre rajada circular, leque e tiros teleguiados."""
        self.padrao = (self.padrao + 1) % 3
        ox, oy = self.x, self.cy
        if self.padrao == 0:                       # rajada circular
            n = 16 if self.fase2 else 12
            for i in range(n):
                a = math.tau * i / n
                jogo.add_tiro(Tiro(self.cx, self.cy,
                                   math.cos(a) * VEL_TIRO_INIMIGO,
                                   math.sin(a) * VEL_TIRO_INIMIGO / ASPECTO,
                                   [GLIFO_BALA_INIMIGA], cor(C_MAGENTA, True), 1,
                                   do_jogador=False, vida=10.0))
        elif self.padrao == 1:                     # leque frontal
            n = 7 if self.fase2 else 5
            for i in range(n):
                a = math.pi + (i - (n - 1) / 2) * 0.22
                jogo.add_tiro(Tiro(ox, oy,
                                   math.cos(a) * VEL_TIRO_INIMIGO * 1.2,
                                   math.sin(a) * VEL_TIRO_INIMIGO / ASPECTO,
                                   [GLIFO_BALA_INIMIGA], cor(C_VERMELHO, True), 1,
                                   do_jogador=False, vida=10.0))
        else:                                      # teleguiados
            for dy in (-2, 0, 2):
                jogo.add_tiro(Tiro(ox, oy + dy, -VEL_TIRO_INIMIGO * 0.75, 0,
                                   [g("◆", "*")], cor(C_AMARELO, True), 1,
                                   do_jogador=False, teleguiado=True, vida=9.0))

    def levar_dano(self, dano, jogo, nucleo=False):
        if self.morrendo > 0:
            return
        self.hp -= dano * (CHEFE_DANO_NUCLEO if nucleo else 1)
        self.flash = 0.06
        if not self.fase2 and self.hp <= self.hp_max * CHEFE_FASE2:
            # segunda fase: fica vermelho, acelera e ataca com mais frequencia
            self.fase2 = True
            self.sprite = list(Chefe.SPRITE_F2)
            self.attr = cor(C_VERMELHO, True)
            jogo.mensagem("O CHEFE ESTA ENFURECIDO!", 1.8)
        if self.hp <= 0:
            self.hp = 0
            self.morrendo = 1.8
            jogo.score += 10000

    def desenhar(self, tela, jogo):
        attr = cor(C_BRANCO, True) if self.flash > 0 else self.attr
        blit(tela, self.x, self.y, self.sprite, attr, topo=jogo.topo, base=jogo.base)
        # nucleo destacado (ponto fraco)
        blit(tela, self.x + 1, self.y + 3, ["[O]"], cor(C_CIANO, True) | curses.A_BOLD,
             topo=jogo.topo, base=jogo.base)


# =====================================================================
#  CENARIO (parallax + chao)
# =====================================================================


class Starfield:
    """Duas camadas de estrelas em velocidades diferentes + planetas ocasionais."""

    PLANETA = [" .-. ", "(   )", " `-' "]

    def __init__(self, jogo):
        self.jogo = jogo
        self.camada1 = []   # distante (lenta)
        self.camada2 = []   # proxima (rapida)
        self.planetas = []
        self.repovoar(inicial=True)

    def repovoar(self, inicial=False):
        j = self.jogo
        self.camada1 = [[random.uniform(0, j.larg), random.uniform(j.topo, j.base - 1),
                         random.choice(GLIFO_ESTRELA[:2])] for _ in range(int(j.larg * 0.55))]
        self.camada2 = [[random.uniform(0, j.larg), random.uniform(j.topo, j.base - 1),
                         random.choice(GLIFO_ESTRELA[2:])] for _ in range(int(j.larg * 0.22))]
        if inicial:
            self.planetas = []

    def atualizar(self, dt):
        j = self.jogo
        for e in self.camada1:
            e[0] -= 5.0 * dt
            if e[0] < 0:
                e[0] = j.larg - 1
                e[1] = random.uniform(j.topo, j.base - 1)
        for e in self.camada2:
            e[0] -= 16.0 * dt
            if e[0] < 0:
                e[0] = j.larg - 1
                e[1] = random.uniform(j.topo, j.base - 1)
        for p in self.planetas:
            p[0] -= 3.0 * dt
        self.planetas = [p for p in self.planetas if p[0] > -6]
        if random.random() < dt * 0.12:
            self.planetas.append([float(j.larg), random.uniform(j.topo, j.base - 4)])

    def desenhar(self, tela):
        j = self.jogo
        for p in self.planetas:
            blit(tela, p[0], p[1], self.PLANETA, cor(C_AZUL), topo=j.topo, base=j.base)
        for e in self.camada1:
            blit(tela, e[0], e[1], [e[2]], cor(C_AZUL), topo=j.topo, base=j.base)
        for e in self.camada2:
            blit(tela, e[0], e[1], [e[2]], cor(C_BRANCO, True), topo=j.topo, base=j.base)


class Chao:
    """Solo com relevo simples que rola horizontalmente (alvo dos misseis)."""

    def __init__(self, jogo):
        self.jogo = jogo
        self.offset = 0.0

    def atualizar(self, dt):
        self.offset = (self.offset + VEL_SCROLL * dt) % 8

    def desenhar(self, tela):
        j = self.jogo
        linha = []
        base_off = int(self.offset)
        for i in range(j.larg):
            k = (i + base_off) % 8
            linha.append(GLIFO_PICO if k == 3 else GLIFO_CHAO)
        blit(tela, 0, j.base, ["".join(linha)], cor(C_VERDE), topo=j.topo, base=j.base)


# =====================================================================
#  HUD
# =====================================================================


class HUD:
    """Placar no topo e barra de power-up na base da tela."""

    def __init__(self, jogo):
        self.jogo = jogo

    def desenhar(self, tela):
        j = self.jogo
        p = j.jogador
        # ---- linha superior ----
        esq = f" SCORE {j.score:07d}  HI {j.recorde:07d}  "
        vidas = GLIFO_VIDA * max(0, p.vidas) if p else ""
        meio = f"VIDAS {vidas:<5}  FASE 1"
        armas = []
        if p:
            if p.tem_missile:
                armas.append("MSL")
            if p.tem_double:
                armas.append("DBL")
            if p.tem_laser:
                armas.append("LSR")
            if p.options:
                armas.append(f"OPTx{len(p.options)}")
            if p.nivel_speed:
                armas.append(f"SPDx{p.nivel_speed}")
            armas.append(f"VUL{p.nivel_vulcan}")
        dir_txt = " ".join(armas)
        linha = (esq + meio).ljust(max(0, j.larg - len(dir_txt) - 1)) + dir_txt
        blit(tela, 0, 0, [linha[: j.larg - 1]], cor(C_CIANO, True), topo=0, base=0)

        # ---- barra de power-up (base) ----
        y = j.alt_tela - 1
        x = 1
        for i, nome in enumerate(PowerMeter.SLOTS):
            aceso = (i == j.power.selecao)
            possui = j.tem_upgrade(nome)
            if aceso:
                attr = curses.A_REVERSE | cor(C_AMARELO, True)
            elif possui:
                attr = cor(C_VERDE, True)
            elif j.power.bloqueado(nome):
                attr = cor(C_VERMELHO) | curses.A_DIM     # ainda indisponivel p/ esta nave
            else:
                attr = cor(C_CINZA) | curses.A_DIM
            txt = f"[{nome}]"
            blit(tela, x, y, [txt], attr, topo=y, base=y)
            x += len(txt) + 1
        dica = f"{j.nave['id']} | ESPACO=ativar  P=pause"
        if x + len(dica) + 2 < j.larg:
            blit(tela, j.larg - len(dica) - 1, y, [dica], cor(C_CINZA) | curses.A_DIM,
                 topo=y, base=y)

        # ---- barra de HP do chefe ----
        if j.chefe and j.chefe.vivo:
            larg_barra = min(40, j.larg - 22)
            frac = max(0.0, j.chefe.hp / j.chefe.hp_max)
            cheio = int(larg_barra * frac)
            barra = g("█", "#") * cheio + g("░", "-") * (larg_barra - cheio)
            c = C_VERMELHO if frac < 0.5 else C_AMARELO
            blit(tela, max(0, (j.larg - larg_barra - 8) // 2), 1,
                 ["BOSS [" + barra + "]"], cor(c, True), topo=1, base=1)


# =====================================================================
#  ONDAS DE INIMIGOS
# =====================================================================


def montar_script():
    """
    Roteiro da fase: lista de (tempo, tipo_de_onda, parametros).
    A dificuldade cresce com o tempo (mais inimigos, ondas mais frequentes).
    """
    script = []
    t = 3.0
    intervalo = 5.0
    rodada = 0
    while t < DURACAO_FASE:
        rodada += 1
        r = rodada % 6
        if r == 1:
            script.append((t, "formacao", {"tipo": "BATEDOR", "n": 5}))
        elif r == 2:
            script.append((t, "linha", {"tipo": "CACADOR", "n": 2 + rodada // 6}))
        elif r == 3:
            script.append((t, "chao", {"tipo": "RASTEJANTE", "n": 2}))
        elif r == 4:
            script.append((t, "chao", {"tipo": "CANHAO", "n": 1 + rodada // 8}))
            script.append((t + 1.5, "formacao", {"tipo": "BATEDOR", "n": 4}))
        elif r == 5:
            script.append((t, "vila", {}))
        else:
            script.append((t, "grande", {}))
        t += intervalo
        intervalo = max(2.6, intervalo * 0.94)
    return script


# =====================================================================
#  JOGO  (maquina de estados + loop principal)
# =====================================================================


class Jogo:
    """Controla estados (menu, jogo, pause, game over, vitoria) e o loop principal."""

    def __init__(self, tela):
        self.tela = tela
        self.rodando = True
        self.estado = "MENU"
        self.menu_idx = 0
        self.recorde = carregar_recorde()
        self.autofire = True
        self.msg = ""
        self.msg_t = 0.0
        self.alt_tela, self.larg = tela.getmaxyx()
        self.atualizar_dimensoes()
        self.starfield = Starfield(self)
        self.chao = Chao(self)
        self.hud = HUD(self)
        self.jogador = None
        self.nave_idx = 0        # nave escolhida na tela de selecao
        self.sel_nave = 0        # cursor da tela de selecao
        self.reiniciar_partida()

    # ---------------- dimensoes ----------------
    def atualizar_dimensoes(self):
        self.alt_tela, self.larg = self.tela.getmaxyx()
        self.topo = 1                      # linha 0 = HUD
        self.base = self.alt_tela - 2      # ultima linha = barra de power-up

    # ---------------- ciclo de vida da partida ----------------
    def reiniciar_partida(self):
        self.score = 0
        self.tempo_fase = 0.0
        self.dificuldade = 1.0
        self.nave = NAVES[self.nave_idx]
        self.jogador = Jogador(self, self.nave)
        self.power = PowerMeter(self.nave)
        self.inimigos = []
        self.tiros = []
        self.powerups = []
        self.efeitos = []
        self.formacoes = {}
        self.prox_formacao = 0
        self.chefe = None
        self.script = montar_script()
        self.idx_script = 0
        self.warning_t = 0.0
        self.fase_encerrada = False
        self.msg = ""
        self.msg_t = 0.0
        self.mensagem(f"NAVE: {self.nave['id']}", 1.6)

    def mensagem(self, texto, dur=1.5):
        self.msg = texto
        self.msg_t = dur

    def add_tiro(self, tiro):
        if len(self.tiros) < LIMITE_TIROS:
            self.tiros.append(tiro)

    def criar_explosao(self, x, y, grande=False):
        self.efeitos.append(Explosao(x, y, grande))

    def soltar_capsula(self, x, y):
        self.powerups.append(PowerUp(x, y))

    def tem_upgrade(self, nome):
        p = self.jogador
        if not p:
            return False
        return {
            "MISSILE": p.tem_missile,
            "DOUBLE": p.tem_double,
            "LASER": p.tem_laser,
            "OPTION": len(p.options) > 0,
            "SPEED": p.nivel_speed > 0,
        }.get(nome, False)

    def game_over(self):
        self.estado = "GAMEOVER"
        if self.score > self.recorde:
            self.recorde = self.score
            salvar_recorde(self.recorde)

    def vitoria(self):
        self.estado = "VITORIA"
        if self.score > self.recorde:
            self.recorde = self.score
            salvar_recorde(self.recorde)

    # =================================================================
    #  ENTRADA
    # =================================================================
    def ler_entrada(self):
        for _ in range(40):                 # esvazia o buffer de teclas do quadro
            ch = self.tela.getch()
            if ch == -1:
                break
            self.tratar_tecla(ch)

    def tratar_tecla(self, ch):
        if ch == curses.KEY_RESIZE:
            self.atualizar_dimensoes()
            self.starfield.repovoar()
            return

        if self.estado == "MENU":
            if ch in (curses.KEY_UP, ord('w'), ord('W'), curses.KEY_DOWN, ord('s'), ord('S')):
                self.menu_idx = 1 - self.menu_idx
            elif ch in (10, 13, curses.KEY_ENTER, ord(' ')):
                if self.menu_idx == 0:
                    self.sel_nave = self.nave_idx
                    self.estado = "SELECAO"
                else:
                    self.rodando = False
            elif ch in (ord('q'), ord('Q'), 27):
                self.rodando = False
            return

        if self.estado == "SELECAO":
            if ch in (curses.KEY_UP, ord('w'), ord('W'), curses.KEY_LEFT, ord('a'), ord('A')):
                self.sel_nave = (self.sel_nave - 1) % len(NAVES)
            elif ch in (curses.KEY_DOWN, ord('s'), ord('S'), curses.KEY_RIGHT,
                        ord('d'), ord('D')):
                self.sel_nave = (self.sel_nave + 1) % len(NAVES)
            elif ch in (10, 13, curses.KEY_ENTER, ord(' ')):
                self.nave_idx = self.sel_nave
                self.reiniciar_partida()
                self.estado = "JOGO"
            elif ch in (ord('q'), ord('Q'), 27):
                self.estado = "MENU"
            return

        if self.estado == "JOGO":
            if ch in (curses.KEY_UP, ord('w'), ord('W')):
                self.jogador.pressionar("cima")
            elif ch in (curses.KEY_DOWN, ord('s'), ord('S')):
                self.jogador.pressionar("baixo")
            elif ch in (curses.KEY_LEFT, ord('a'), ord('A')):
                self.jogador.pressionar("esq")
            elif ch in (curses.KEY_RIGHT, ord('d'), ord('D')):
                self.jogador.pressionar("dir")
            elif ch == ord(' '):
                if not self.power.ativar(self.jogador, self):
                    self.mensagem("SEM UPGRADE DISPONIVEL", 0.8)
            elif ch in (ord('z'), ord('Z')):
                self.jogador.atirar(self)          # disparo manual
            elif ch in (ord('f'), ord('F')):
                self.autofire = not self.autofire
                self.mensagem("AUTOFIRE " + ("ON" if self.autofire else "OFF"), 1.0)
            elif ch in (ord('p'), ord('P')):
                self.estado = "PAUSE"
            elif ch in (ord('q'), ord('Q'), 27):
                self.estado = "MENU"
            return

        if self.estado == "PAUSE":
            if ch in (ord('p'), ord('P'), 10, 13, curses.KEY_ENTER):
                self.estado = "JOGO"
            elif ch in (ord('q'), ord('Q'), 27):
                self.estado = "MENU"
            return

        if self.estado in ("GAMEOVER", "VITORIA"):
            if ch in (ord('r'), ord('R')):
                self.reiniciar_partida()
                self.estado = "JOGO"
            elif ch in (ord('n'), ord('N')):
                self.sel_nave = self.nave_idx
                self.estado = "SELECAO"
            elif ch in (10, 13, curses.KEY_ENTER, ord(' '), ord('q'), ord('Q'), 27):
                self.estado = "MENU"
            return

    # =================================================================
    #  ATUALIZACAO
    # =================================================================
    def atualizar(self, dt):
        self.atualizar_dimensoes()
        if self.msg_t > 0:
            self.msg_t = max(0.0, self.msg_t - dt)

        if self.estado in ("MENU", "SELECAO"):
            self.starfield.atualizar(dt)
            self.chao.atualizar(dt)
            return
        if self.estado in ("PAUSE", "GAMEOVER", "VITORIA"):
            return

        # ---- cenario ----
        self.starfield.atualizar(dt)
        self.chao.atualizar(dt)
        self.power.atualizar(dt)

        # ---- jogador ----
        p = self.jogador
        if p and p.ativo:
            p.atualizar(dt, self)
            if self.autofire:
                p.atirar(self)

        # ---- roteiro da fase ----
        if not self.fase_encerrada:
            self.tempo_fase += dt
            self.dificuldade = min(DIFICULDADE_MAX, 1.0 + self.tempo_fase / DURACAO_FASE)
            while (self.idx_script < len(self.script)
                   and self.script[self.idx_script][0] <= self.tempo_fase):
                _, tipo, par = self.script[self.idx_script]
                self.spawn_onda(tipo, par)
                self.idx_script += 1
            if self.tempo_fase >= DURACAO_FASE and self.chefe is None and self.warning_t <= 0:
                self.warning_t = TEMPO_WARNING
                self.inimigos.clear()

        # ---- aviso e entrada do chefe ----
        if self.warning_t > 0:
            self.warning_t -= dt
            if self.warning_t <= 0:
                self.chefe = Chefe(self)
                self.fase_encerrada = True

        # ---- entidades ----
        for e in self.inimigos:
            e.atualizar(dt, self)
        for t in self.tiros:
            t.atualizar(dt, self)
        for pu in self.powerups:
            pu.atualizar(dt, self)
        for ef in self.efeitos:
            ef.atualizar(dt, self)
        if self.chefe:
            self.chefe.atualizar(dt, self)

        self.checar_colisoes()

        # ---- limpeza ----
        self.inimigos = [e for e in self.inimigos if e.vivo]
        self.tiros = [t for t in self.tiros if t.vivo]
        self.powerups = [pu for pu in self.powerups if pu.vivo]
        self.efeitos = [ef for ef in self.efeitos if ef.vivo]
        if self.chefe and not self.chefe.vivo:
            self.chefe = None

    # ---------------- spawn ----------------
    def spawn_onda(self, tipo, par):
        alt = self.base - self.topo
        if tipo == "formacao":
            self.prox_formacao += 1
            fid = self.prox_formacao
            n = par["n"]
            self.formacoes[fid] = n
            y0 = random.uniform(self.topo + 1, self.base - 5)
            for i in range(n):
                self.inimigos.append(
                    Inimigo(par["tipo"], self.larg + 3 + i * 5, y0, self, formacao=fid))
        elif tipo == "linha":
            for i in range(par["n"]):
                y = random.uniform(self.topo, self.base - 2)
                self.inimigos.append(Inimigo(par["tipo"], self.larg + 3 + i * 8, y, self))
        elif tipo == "chao":
            for i in range(par["n"]):
                self.inimigos.append(
                    Inimigo(par["tipo"], self.larg + 3 + i * 10, self.base - 2, self))
        elif tipo == "vila":
            self.inimigos.append(Inimigo("VILA", self.larg + 3,
                                         random.uniform(self.topo + 1, self.base - 5), self))
        elif tipo == "grande":
            self.inimigos.append(Inimigo("GRANDE", self.larg + 3,
                                         random.uniform(self.topo + 1, self.base - 5), self))

    # ---------------- colisoes ----------------
    def checar_colisoes(self):
        p = self.jogador

        for t in self.tiros:
            if not t.vivo:
                continue
            if t.do_jogador:
                # missil explode ao tocar o chao
                if isinstance(t, Missil) and t.no_chao and t.x > self.larg:
                    t.vivo = False
                    continue
                for e in self.inimigos:
                    if not e.vivo:
                        continue
                    if id(e) in t.atingidos:
                        continue
                    if colide(*t.caixa(), *e.caixa()):
                        if isinstance(t, Missil):
                            t.explodir(self)
                            break
                        e.levar_dano(t.dano, self)
                        self.criar_explosao(t.cx, t.cy)
                        if t.perfurante:
                            t.atingidos.add(id(e))
                        else:
                            t.vivo = False
                            break
                if t.vivo and self.chefe and self.chefe.vivo and self.chefe.morrendo <= 0:
                    b = self.chefe
                    if colide(*t.caixa(), *b.caixa()) and id(b) not in t.atingidos:
                        no_nucleo = colide(*t.caixa(), *b.caixa_nucleo())
                        if isinstance(t, Missil):
                            t.explodir(self)
                        else:
                            b.levar_dano(t.dano, self, nucleo=no_nucleo)
                            self.criar_explosao(t.cx, t.cy)
                            if t.perfurante:
                                t.atingidos.add(id(b))
                            else:
                                t.vivo = False
            else:
                # ---- tiro inimigo x jogador (unica forma de tomar dano) ----
                if p and p.ativo and p.invencivel <= 0 and colide(*t.caixa(), *p.caixa()):
                    t.vivo = False
                    p.atingido(self)

        # ---- captura de capsulas ----
        if p and p.ativo:
            for pu in self.powerups:
                if pu.vivo and colide(*pu.caixa(), *p.caixa()):
                    pu.vivo = False
                    self.power.capturar()
                    self.score += 50

    # =================================================================
    #  DESENHO
    # =================================================================
    def desenhar(self):
        tela = self.tela
        tela.erase()
        if self.larg < LARGURA_MIN or self.alt_tela < ALTURA_MIN:
            texto_centralizado(tela, max(0, self.alt_tela // 2 - 1),
                               "TERMINAL PEQUENO DEMAIS", cor(C_VERMELHO, True))
            texto_centralizado(tela, max(1, self.alt_tela // 2),
                               f"Redimensione para pelo menos {LARGURA_MIN}x{ALTURA_MIN} "
                               f"(atual {self.larg}x{self.alt_tela})")
            tela.noutrefresh()
            curses.doupdate()
            return

        if self.estado == "MENU":
            self.desenhar_menu()
        elif self.estado == "SELECAO":
            self.desenhar_selecao()
        else:
            self.desenhar_jogo()
            if self.estado == "PAUSE":
                self.desenhar_pause()
            elif self.estado == "GAMEOVER":
                self.desenhar_gameover()
            elif self.estado == "VITORIA":
                self.desenhar_vitoria()

        tela.noutrefresh()
        curses.doupdate()

    def desenhar_jogo(self):
        tela = self.tela
        self.starfield.desenhar(tela)
        self.chao.desenhar(tela)
        for pu in self.powerups:
            pu.desenhar(tela, self)
        for e in self.inimigos:
            e.desenhar(tela, self)
        if self.chefe:
            self.chefe.desenhar(tela, self)
        for t in self.tiros:
            t.desenhar(tela, self)
        if self.jogador and self.jogador.ativo:
            self.jogador.desenhar(tela, self)
        for ef in self.efeitos:
            ef.desenhar(tela, self)
        self.hud.desenhar(tela)

        if self.warning_t > 0 and int(self.warning_t * 4) % 2 == 0:
            y = (self.topo + self.base) // 2
            texto_centralizado(tela, y - 1, "!!  W A R N I N G  !!", cor(C_VERMELHO, True))
            texto_centralizado(tela, y + 1, "GRANDE NAVE INIMIGA SE APROXIMANDO",
                               cor(C_AMARELO, True))
        if self.msg_t > 0:
            texto_centralizado(tela, self.topo + 1, self.msg, cor(C_AMARELO, True))

    def desenhar_menu(self):
        tela = self.tela
        self.starfield.desenhar(tela)
        self.chao.desenhar(tela)
        titulo = TITULO_ASC if ASCII_PURO else TITULO_UNI
        y = max(1, self.alt_tela // 2 - 9)
        larg_t = max(len(l) for l in titulo)
        x = max(0, (self.larg - larg_t) // 2)
        blit(tela, x, y, titulo, cor(C_CIANO, True))
        y += len(titulo) + 1
        texto_centralizado(tela, y, "M P - G R A D I U S - T E R M", cor(C_MAGENTA, True))
        y += 2
        opcoes = ["JOGAR", "SAIR"]
        for i, op in enumerate(opcoes):
            sel = (i == self.menu_idx)
            attr = curses.A_REVERSE | cor(C_AMARELO, True) if sel else cor(C_BRANCO, True)
            rotulo = f"  {op}  "
            escrever(tela, max(0, (self.larg - len(rotulo)) // 2), y + i, rotulo, attr)
        y += len(opcoes) + 2
        texto_centralizado(tela, y, f"HIGH SCORE: {self.recorde:07d}", cor(C_VERDE, True))
        y += 2
        for linha in [
            "SETAS / WASD ... mover (8 direcoes)      ESPACO ... ativar upgrade da barra",
            "Z ... tiro manual   F ... autofire       P ... pause    Q ... sair",
            "Capture as capsulas ? e ative: MISSILE > DOUBLE > LASER > OPTION > SPEED",
            "4 naves jogaveis: VIC-01, FALCAO, MARTELO e ESPECTRO",
        ]:
            texto_centralizado(tela, y, linha, cor(C_CINZA) | curses.A_DIM)
            y += 1
        texto_centralizado(tela, min(self.alt_tela - 2, y + 1),
                           "ENTER para comecar", cor(C_BRANCO, True))

    def desenhar_selecao(self):
        """Tela de escolha de nave: preview do sprite, estatisticas e traco exclusivo."""
        tela = self.tela
        self.starfield.desenhar(tela)
        self.chao.desenhar(tela)
        topo = max(1, (self.alt_tela - 4 * 3 - 6) // 2)
        texto_centralizado(tela, topo, "E S C O L H A   S U A   N A V E", cor(C_CIANO, True))
        y = topo + 2
        larg_bloco = min(self.larg - 4, 70)
        x0 = max(1, (self.larg - larg_bloco) // 2)
        for i, cfg in enumerate(NAVES):
            sel = (i == self.sel_nave)
            marcador = g("\u25b6", ">") if sel else " "
            preview = sprite_nave(cfg, missile=cfg["missile_inicial"])
            cabecalho = f"{marcador} {cfg['id']:<9} {preview}   {stats_nave(cfg)}"
            if sel:
                escrever(tela, x0, y, cabecalho.ljust(larg_bloco)[:larg_bloco],
                         curses.A_REVERSE | cor(C_AMARELO, True))
            else:
                escrever(tela, x0, y, cabecalho[:larg_bloco], cor(cfg["cor"], True))
            attr2 = cor(C_BRANCO, True) if sel else cor(C_CINZA) | curses.A_DIM
            escrever(tela, x0 + 2, y + 1, cfg["traco"][:larg_bloco - 2], attr2)
            y += 3
        y = min(self.alt_tela - 2, y)
        texto_centralizado(tela, y, "SETAS = escolher    ENTER = decolar    Q = voltar",
                           cor(C_BRANCO, True))

    def desenhar_pause(self):
        y = (self.topo + self.base) // 2
        texto_centralizado(self.tela, y, "===  P A U S A  ===", cor(C_AMARELO, True))
        texto_centralizado(self.tela, y + 1, "P para continuar - Q para o menu",
                           cor(C_BRANCO))

    def desenhar_gameover(self):
        y = (self.topo + self.base) // 2 - 2
        texto_centralizado(self.tela, y, "G A M E   O V E R", cor(C_VERMELHO, True))
        texto_centralizado(self.tela, y + 2, f"SCORE FINAL: {self.score:07d}", cor(C_BRANCO, True))
        texto_centralizado(self.tela, y + 3, f"RECORDE: {self.recorde:07d}", cor(C_VERDE, True))
        texto_centralizado(self.tela, y + 5, "R - jogar de novo    N - trocar de nave    ENTER - menu",
                           cor(C_AMARELO, True))

    def desenhar_vitoria(self):
        y = (self.topo + self.base) // 2 - 3
        texto_centralizado(self.tela, y, "*** FASE 1 CONCLUIDA ***", cor(C_AMARELO, True))
        texto_centralizado(self.tela, y + 2, "V I T O R I A !", cor(C_VERDE, True))
        texto_centralizado(self.tela, y + 4, f"SCORE FINAL: {self.score:07d}", cor(C_BRANCO, True))
        texto_centralizado(self.tela, y + 5, f"RECORDE: {self.recorde:07d}", cor(C_CIANO, True))
        texto_centralizado(self.tela, y + 7, "R - jogar de novo    N - trocar de nave    ENTER - menu",
                           cor(C_AMARELO, True))

    # =================================================================
    #  LOOP PRINCIPAL
    # =================================================================
    def executar(self):
        quadro = 1.0 / FPS_ALVO
        anterior = time.perf_counter()
        while self.rodando:
            inicio = time.perf_counter()
            dt = min(inicio - anterior, 0.08)   # limita dt apos travadas
            anterior = inicio
            self.ler_entrada()
            self.atualizar(dt)
            self.desenhar()
            resto = quadro - (time.perf_counter() - inicio)
            if resto > 0:
                time.sleep(resto)


# =====================================================================
#  BOOTSTRAP
# =====================================================================


def main(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.keypad(True)
    try:
        curses.noecho()
        curses.cbreak()
    except curses.error:
        pass
    iniciar_cores()
    Jogo(stdscr).executar()


if __name__ == "__main__":
    locale.setlocale(locale.LC_ALL, "")
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
    print("Obrigado por jogar MP-GRADIUS-TERM!")
