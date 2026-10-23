# 📦 Guia de Instalação

Este guia explica como instalar e rodar os três jogos do repositório:

- 🚀 **MP Gradius Term**: `terminal-gradius/mp-gradius-term.py`
- 🌙 **MP Lunar Lander**: `terminal-lunarlander/lunar_lander.py`
- 💥 **MP Míssil Comando**: `terminal-misslecomando/missel_comando.py`

Os jogos usam apenas a biblioteca padrão do Python (`curses`). No Linux e no macOS **não é preciso instalar nenhum pacote**.

---

## 1. Requisitos

| Item | Requisito |
|---|---|
| Python | 3.8 ou superior |
| Terminal | Com suporte a cores e UTF-8 (recomendado) |
| Tamanho do terminal | Gradius **80×24** · Lunar Lander **64×22** · Míssil Comando **62×20** |
| Pacotes extras | Nenhum no Linux/macOS · `windows-curses` no Windows |

Confira sua versão do Python:

```bash
python3 --version
```

---

## 2. Baixar o projeto

```bash
git clone https://github.com/mpontes-stack/jogos-terminal.git
cd jogos-terminal
```

Sem git? Na página do repositório, clique em **Code → Download ZIP** e extraia o arquivo.

---

## 3. Instalação por sistema operacional

### 🐧 Linux

O Python e o `curses` geralmente já vêm instalados. Se faltar o Python:

```bash
# Debian / Ubuntu
sudo apt install python3

# Fedora
sudo dnf install python3

# Arch
sudo pacman -S python
```

Pronto. Vá para o [passo 4](#4-rodando-os-jogos).

### 🍎 macOS

O `curses` já faz parte do Python do macOS. Se precisar de uma versão mais nova:

```bash
brew install python
```

Use preferencialmente o **iTerm2** ou o **Terminal.app** com a fonte padrão.

### 🪟 Windows

No Windows o módulo `curses` não vem com o Python, então é preciso instalar um pacote:

1. Instale o Python em [python.org](https://www.python.org/downloads/) e marque **"Add Python to PATH"** durante a instalação.
2. Abra o **Windows Terminal** ou o PowerShell e rode:

   ```powershell
   pip install windows-curses
   ```

3. Nos comandos deste guia, troque `python3` por `python` (ou `py`).

> 💡 **Alternativa:** usando o **WSL** (Ubuntu no Windows), siga as instruções de Linux. Não é preciso `windows-curses`.

---

## 4. Rodando os jogos

A partir da raiz do repositório:

```bash
# 🚀 Gradius
python3 terminal-gradius/mp-gradius-term.py

# 🌙 Lunar Lander
python3 terminal-lunarlander/lunar_lander.py

# 💥 Míssil Comando
python3 terminal-misslecomando/missel_comando.py
```

No Linux/macOS você também pode tornar os arquivos executáveis:

```bash
chmod +x terminal-*/*.py
./terminal-lunarlander/lunar_lander.py
```

Para sair de qualquer jogo, aperte **`Q`**.

---

## 5. (Opcional) Usando um ambiente virtual

Não é obrigatório, porque os jogos não têm dependências. No Windows, porém, um venv evita instalar o `windows-curses` no Python global.

```bash
python3 -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
pip install windows-curses
```

A pasta `.venv/` já está no `.gitignore`.

---

## 6. Dicas para a melhor experiência

- **Aumente o terminal** antes de abrir o jogo. Se ele for pequeno demais, o jogo mostra o tamanho mínimo necessário. Pode redimensionar com o jogo aberto, que ele se ajusta sozinho.
- **Use uma fonte monoespaçada** (Fira Code, JetBrains Mono, Cascadia, DejaVu Sans Mono…).
- **Fundo escuro**: as cores foram pensadas para temas escuros.
- **Gradius sem UTF-8**: se aparecerem caracteres estranhos, ative o modo ASCII puro:

  ```bash
  MP_GRADIUS_ASCII=1 python3 terminal-gradius/mp-gradius-term.py
  ```

  No PowerShell: `$env:MP_GRADIUS_ASCII=1; python terminal-gradius/mp-gradius-term.py`

---

## 7. Solução de problemas

| Problema | Solução |
|---|---|
| `ModuleNotFoundError: No module named '_curses'` | Você está no Windows: rode `pip install windows-curses` |
| `python3: command not found` | No Windows use `python` ou `py`. No Linux, instale o Python (passo 3) |
| A tela pede "Aumente o terminal para pelo menos …" | Maximize a janela ou diminua o zoom da fonte (`Ctrl -`) |
| Caracteres quebrados ou `?` no lugar de símbolos | Configure o terminal para UTF-8 ou use `MP_GRADIUS_ASCII=1` no Gradius |
| Sem cores | Verifique se `TERM` está como `xterm-256color` (`echo $TERM`) |
| O terminal ficou "bagunçado" depois de fechar | Rode `reset` (Linux/macOS) |
| Teclas de seta não respondem no Windows | Use o **Windows Terminal** em vez do `cmd.exe` antigo, ou jogue com `W A S D` |

---

## 8. Recordes e arquivos gerados

- **Gradius** salva o recorde em `~/.mp-gradius-term_hs.json` (na sua pasta de usuário). Apague o arquivo para zerar o placar.
- **Lunar Lander** e **Míssil Comando** não gravam nada em disco.

---

Controles e detalhes de cada jogo estão no **[README](README.md)**. Bom jogo! 🕹️
