# XMB-PY 5.1

XMB-PY 5.1

Sistema desktop em Python com interface inspirada na **XMB** (barra de mídia horizontal).

## Novidades 5.1

- **Teclado Virtual** — agora você pode digitar pelo controle (login e cadastro)
- **Aba Wallpapers** — agora você pode mudar o wallpaper (de novo)
- **Ícones das Abas** — agora as abas tem ícones 👍
- **Nova Aba "Biblioteca"** — agora você pode ir até a sua Biblioteca de Jogos na Store

## Como rodar

```bash
pip install -r requirements.txt
python main.py
```

A loja padrão aponta para `https://p1xelado.pythonanywhere.com`.

## Atualizações

1. O cliente lista `GET /api/updates`, escolhe a versão **mais alta** e compara com o arquivo local `VERSION`.
2. Em **Configurações → Atualizações**, confirme o download e a instalação.
3. Na inicialização, se houver versão nova, um aviso é exibido.

## Loja

- Categoria **Loja Online → Entrar na Store** abre o catálogo em grid.
- Navegue com as setas/setas do controle, Enter/X para detalhes/comprar, O para voltar.
- Itens com arquivo ZIP são extraídos automaticamente em `games/`.

## Controles

| Tecla | XMB | Store |
|-------|-----|-------|
| ← →   | categorias | cards |
| ↑ ↓   | itens | cards |
| Enter/X | confirmar | detalhes / comprar |
| Esc/O   | voltar / sair | voltar |
| F11   | tela cheia | — |

# Requisitos (Importante!)

|  Recurso  |  Mínimo razoável  |  Recomendado  |
|-----------|-------------------|---------------|
|  SO       | "Windows 10, Linux ou macOS recentes" |  Windows 10/11 ou Linux atual  |
|  Python   | 3.10+  |  3.11 ou 3.12 |
|  CPU      | "Dual-core ~1,5 GHz" | Quad-core |
| RAM       | ~512 MB livres (1 GB total) | 2 GB+ livres |
| GPU / vídeo | Qualquer com aceleração OpenGL/SDL básica |Integrada moderna ok |
| Disco | ~50–100 MB (app + jogos simples) | 1 GB+ (Mais se houver muitos jogos/wallpapers) |
| Rede  | Opcional (só para loja e atualizações) | Conexão estável (se usar a store) |
| Dependências | "pygame, requests" | "pygame, requests" também |
