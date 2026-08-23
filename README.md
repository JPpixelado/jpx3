# XMB-PY 4.1

Sistema desktop em Python com interface inspirada na **XMB** (barra de mídia horizontal).

## Novidades 3.1

- **Entrar na Store** — interface completa em tela cheia (visual da XMB Store)
- **Atualizações automáticas** — compara ZIPs no servidor (`2.0.zip` vs `4.0.zip`) e instala a mais nova
- Extração automática de jogos baixados
- Login, wallpapers e menu de pausa (Esc)

## Como rodar

```bash
pip install -r requirements.txt
python main.py
```

A loja padrão aponta para `https://p1xelado.pythonanywhere.com`.

## Atualizações

1. No servidor, coloque pacotes em `server/updates/` com nomes versionados:
   - `3.1.0.zip`, `4.0.zip`, `4.2.1.zip` …
2. O cliente lista `GET /api/updates`, escolhe a versão **mais alta** e compara com o arquivo local `VERSION`.
3. Em **Configurações → Atualizações**, confirme o download e a instalação.
4. Na inicialização, se houver versão nova, um aviso é exibido.

## Loja

- Categoria **Loja Online → Entrar na Store** abre o catálogo em grid.
- Navegue com as setas, Enter para detalhes/comprar, Esc para voltar.
- Itens com arquivo ZIP são extraídos automaticamente em `games/`.

## Controles

| Tecla | XMB | Store |
|-------|-----|-------|
| ← →   | categorias | cards |
| ↑ ↓   | itens | cards |
| Enter | confirmar | detalhes / comprar |
| Esc   | voltar / sair | voltar |
| F11   | tela cheia | — |
