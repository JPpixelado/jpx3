"""Itens de exemplo usados como fallback quando o servidor online da loja
não está acessível. Mantém o mesmo formato retornado pela API real
(server/app.py), para que a troca seja transparente para a UI."""

MOCK_ITEMS = [
    {
        "id": 1,
        "name": "Speed Racer X",
        "price": "R$ 19,90",
        "description": "Corrida arcade em pistas futuristas. (dados de exemplo, sem conexão com o servidor)",
        "category": "Jogo",
        "icon": "game",
    },
    {
        "id": 2,
        "name": "Trilha Sonora Retrowave",
        "price": "R$ 9,90",
        "description": "Álbum synthwave para acompanhar suas sessões. (dados de exemplo, sem conexão com o servidor)",
        "category": "Música",
        "icon": "music",
    },
    {
        "id": 3,
        "name": "Tema XMB Azul Profundo",
        "price": "Grátis",
        "description": "Personalização visual para o sistema. (dados de exemplo, sem conexão com o servidor)",
        "category": "Tema",
        "icon": "photo",
    },
]
