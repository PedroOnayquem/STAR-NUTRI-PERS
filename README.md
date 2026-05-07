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
