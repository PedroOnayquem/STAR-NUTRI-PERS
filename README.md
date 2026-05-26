# STAR-NUTRI

SaaS de gestao nutricional com IA para nutricionistas acompanharem pacientes, dietas, treinos, metricas e evolucao.

## Stack

- React + TypeScript + Vite
- Tailwind CSS
- FastAPI
- Supabase

## Documentacao

- [Arquitetura do projeto](docs/ARCHITECTURE.md)
- [Criar o primeiro admin](docs/FIRST_ADMIN_SETUP.md)

## Frontend

```bash
npm install
npm run dev
```

## Backend

```bash
npm run dev:api
```

Use dois terminais: um para `npm run dev` e outro para `npm run dev:api`.
Se a API nao estiver rodando em `http://127.0.0.1:8000`, o frontend vai
mostrar erro de conexao recusada ao cadastrar nutricionistas ou pacientes.

## Docker

Crie os arquivos de ambiente antes de subir os containers:

```bash
cp .env.example .env
cp backend/.env.example backend/.env
```

Preencha:

- `.env` com `VITE_SUPABASE_URL` e `VITE_SUPABASE_ANON_KEY`
- `backend/.env` com `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` e `OPENAI_API_KEY`

Depois suba tudo:

```bash
docker compose up --build
```

A stack fica disponivel em:

- Frontend: `http://localhost:8080`
- Backend: `http://localhost:8000`
- Docs da API: `http://localhost:8000/docs`

Observacoes:

- O `docker-compose.yml` força o frontend a falar com a API pelo proxy `/backend`, entao nao e preciso rebuildar a imagem para acertar a URL da API.
- O Supabase continua sendo externo ao projeto. A pasta `supabase/` guarda migrations e SQL, mas nao sobe a stack completa do Supabase local.
