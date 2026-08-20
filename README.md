# XMB-PY

Sistema desktop em Python com interface inspirada na **XMB (XrossMediaBar)**
do PlayStation 3.

## Recursos

- Navegação horizontal por categorias e vertical por itens
- Fundo animado com ondas, partículas e **wallpapers personalizados**
- **Login / registro** na categoria Usuários (integrado à loja)
- **Loja Online**: compra, download e instalação automática de jogos
- **Wallpapers da loja**: baixe e aplique como fundo da XMB
- **Menu de pausa** nos jogos (tecla Esc)
- Servidor Flask com contas, uploads, SQLite e interface web

## Como rodar

```bash
# Cliente
pip install -r requirements.txt

# Servidor da loja (outro terminal)
pip install -r server/requirements.txt
python server/app.py
# → http://127.0.0.1:5000

# Sistema XMB
python main.py
```

## Controles (XMB)

| Tecla   | Ação                         |
|---------|------------------------------|
| ← →     | categorias                   |
| ↑ ↓     | itens                        |
| Enter   | detalhes / confirmar         |
| Esc     | voltar / sair                |
| F11     | tela cheia                   |

## Login na XMB

1. Abra a categoria **Usuários**
2. Escolha **Entrar** ou **Criar conta**
3. Preencha o formulário (Tab para alternar campos, Enter para enviar)
4. O nome do usuário aparece no canto superior esquerdo quando logado

A sessão fica salva em `data/session.json`.

## Baixar jogos

1. Faça login (recomendado)
2. Vá em **Loja Online** e selecione um jogo baixável (marcado como “baixável”)
3. Enter → confirmar compra
4. O ZIP é baixado e instalado automaticamente em `games/`
5. O jogo aparece na categoria **Jogos**

Itens de demonstração baixáveis: **Cobrinha (Download)** e **Speed Racer X**.

## Wallpapers personalizados

1. Na **Loja Online**, adquira um item da categoria Tema (ex.: Wallpaper Azul Profundo)
2. Após o download, confirme se deseja aplicar imediatamente
3. Ou vá em **Fotos** e escolha um wallpaper local para aplicar
4. **Fundo padrão (ondas)** restaura o visual original

Wallpapers ficam em `wallpapers/` e a preferência é salva em `config.json`.

## Estrutura

```
jpx3/
├── main.py
├── config.json
├── data/session.json      # sessão do usuário
├── wallpapers/            # papéis de parede locais
├── xmb/                   # engine, tema, diálogos, widgets
├── store/                 # cliente da loja + sessão
├── games/                 # jogos instalados (+ common/pause_menu)
└── server/                # Flask: API + site + uploads + store.db
```

## API (resumo)

```
POST /api/auth/register|login
GET  /api/store/items
GET  /api/store/items/<id>/download
POST /api/store/purchase
POST /api/store/upload
```

## Hospedar a loja online

Instruções detalhadas em `server/DEPLOY.md`.

Resumo rápido:

1. Faça deploy da pasta `server/` (Railway, Render ou VPS).
2. Defina a variável de ambiente `XMB_SECRET` (chave secreta longa).
3. Copie a URL pública (ex.: `https://sua-store.up.railway.app`).
4. No cliente XMB, edite `config.json`:

```json
{
  "store_server_url": "https://sua-store.up.railway.app",
  "store_request_timeout": 10
}
```

5. Teste: `curl https://sua-store.up.railway.app/api/health`
