# Criar o primeiro admin

Hoje o banco do Star Nutri esta vazio:

- `auth.users`: 0 usuarios
- `public.profiles`: 0 perfis

Por isso, acessar `/admin` redireciona para `/login`: a rota esta protegida e ainda nao existe uma conta admin autenticada.

## Passo 1: criar usuario no Supabase Auth

No painel do Supabase:

1. Abra o projeto `DB STAR NUTRI`.
2. Va em `Authentication`.
3. Clique em `Add user`.
4. Cadastre o email e senha do desenvolvedor/admin.
5. Marque o email como confirmado, se essa opcao aparecer.

## Passo 2: criar profile admin

Depois de criar o usuario, copie o `User UID` dele no Supabase Auth e rode no SQL Editor:

```sql
insert into public.profiles (
  id,
  full_name,
  email,
  role,
  is_active
)
values (
  'COLE_AQUI_O_USER_UID',
  'Admin Star Nutri',
  'email-do-admin@exemplo.com',
  'admin',
  true
)
on conflict (id) do update
set
  full_name = excluded.full_name,
  email = excluded.email,
  role = excluded.role,
  is_active = excluded.is_active;
```

## Passo 3: acessar o painel admin

1. Rode o backend:

```bash
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

2. Rode o frontend:

```bash
npm run dev
```

3. Entre em `/login` com o email e senha do admin.
4. O sistema redirecionara automaticamente para `/admin`.

## Observacao

Nutricionistas nao devem ser criados pelo cadastro publico. Depois que o admin
entrar em `/admin`, ele podera cadastrar nutricionistas pela interface
administrativa.
