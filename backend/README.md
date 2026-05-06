# Star Nutri API

Backend em Python com FastAPI.

## Como rodar

Crie e ative um ambiente virtual:

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

Inicie a API:

```bash
fastapi dev backend.app.main:app
```

Endpoints iniciais:

- API: `http://127.0.0.1:8000`
- Health check: `http://127.0.0.1:8000/api/health`
- Swagger: `http://127.0.0.1:8000/docs`
