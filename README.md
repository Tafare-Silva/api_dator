# Restaurante API

Backend FastAPI para controle de mesas e comandas, integrado ao banco PostgreSQL do ERP Delphi.

## Estrutura do Projeto

```
restaurante_api/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── mesas.py          # CRUD de mesas
│   │       │   ├── itens_mesa.py     # Lançamento/gestão de itens
│   │       │   └── produtos.py       # Consulta de produtos (somente leitura)
│   │       └── __init__.py           # Agrega todos os routers
│   ├── core/
│   │   ├── config.py                 # Configurações via .env
│   │   └── exceptions.py            # Exceções customizadas
│   ├── db/
│   │   └── session.py               # Engine async + get_db dependency
│   ├── models/                       # Models SQLAlchemy (refletem tabelas do banco)
│   │   ├── mesa.py
│   │   ├── item_mesa.py
│   │   └── produto.py
│   ├── schemas/                      # Schemas Pydantic (validação e serialização)
│   │   ├── mesa.py
│   │   ├── item_mesa.py
│   │   └── produto.py
│   ├── services/                     # Lógica de negócio (separada dos endpoints)
│   │   ├── mesa_service.py
│   │   ├── item_mesa_service.py
│   │   └── produto_service.py
│   └── main.py                       # App FastAPI + middlewares + handlers
├── alembic/                          # Migrations de banco
├── requirements.txt
└── .env.example
```

## Instalação

```bash
# 1. Clone o projeto e entre na pasta
cd restaurante_api

# 2. Crie um ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure o .env
cp .env.example .env
# Edite o .env com a URL do seu banco PostgreSQL:
# DATABASE_URL=postgresql+asyncpg://usuario:senha@localhost:5432/nome_do_banco
```

## Rodando o servidor

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Acesse a documentação interativa em: http://localhost:8000/api/v1/docs

## Principais Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | /api/v1/mesas | Lista todas as mesas |
| POST | /api/v1/mesas | Cria uma mesa |
| GET | /api/v1/mesas/{nome}/itens | Lista itens da mesa |
| GET | /api/v1/mesas/{nome}/itens/conta | Resumo da conta (para impressão) |
| POST | /api/v1/mesas/{nome}/itens | Adiciona produto à mesa |
| PATCH | /api/v1/mesas/{nome}/itens/{id} | Atualiza item |
| DELETE | /api/v1/mesas/{nome}/itens/{id} | Remove item |
| POST | /api/v1/mesas/{nome}/itens/{id}/desdobrar | Desdobra item |
| GET | /api/v1/produtos | Lista produtos ativos |

## Decisões de Arquitetura

- **Somente leitura em produtos**: O cadastro de produtos continua sendo feito pelo ERP Delphi. A API apenas consulta.
- **Services separados dos endpoints**: Toda regra de negócio fica em `services/`, os endpoints só recebem/retornam dados. Facilita testes e manutenção.
- **SQLAlchemy async**: Melhor performance para múltiplas requisições simultâneas (vários garçons lançando ao mesmo tempo).
- **Exceções tipadas**: `NotFoundError` e `BusinessRuleError` são convertidas automaticamente em respostas HTTP padronizadas.
- **Schemas distintos (Create/Update/Response)**: Cada operação tem seu schema, evitando expor campos desnecessários.
