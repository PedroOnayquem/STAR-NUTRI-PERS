# Star Nutri API

Backend em Python com FastAPI.

## Como rodar

Pela raiz do projeto, a opcao recomendada sobe a API em Docker e nao exige
Python ou ambiente virtual instalados localmente:

```bash
npm run dev:api
```

Para desenvolvimento local sem Docker, crie e ative um ambiente virtual:

```bash
python -m venv .venv
```

No Windows PowerShell:

```bash
.venv\Scripts\Activate.ps1
```

Instale as dependencias:

```bash
pip install -r backend/requirements.txt
```

Crie `backend/.env` a partir de `backend/.env.example` e preencha:

```bash
SUPABASE_URL=https://seu-project-ref.supabase.co
SUPABASE_SERVICE_ROLE_KEY=sua-service-role-key
```

Essa chave fica somente no backend. Sem ela, o cadastro de nutricionistas e
pacientes retorna erro de configuracao, porque ambos criam usuarios no Supabase
Auth pelo servidor.

Inicie a API local:

```bash
npm run dev:api:local
```

O script local executa o comando equivalente:

```bash
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Deixe esse terminal aberto enquanto usa o frontend. Se a API nao estiver
rodando, o navegador mostrara `ERR_CONNECTION_REFUSED` ao chamar
`http://127.0.0.1:8000`.

Observacao para Windows: `fastapi dev` espera um caminho de arquivo, nao
`backend.app.main:app`. Em alguns terminais Windows ele tambem pode falhar por
encoding ao imprimir emojis. O comando com `uvicorn` acima e o mais estavel.

Endpoints iniciais:

- API: `http://127.0.0.1:8000`
- Health check: `http://127.0.0.1:8000/api/health`
- Swagger: `http://127.0.0.1:8000/docs`
