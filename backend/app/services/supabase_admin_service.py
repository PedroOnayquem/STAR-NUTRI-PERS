import httpx
from fastapi import HTTPException, status

from ..core.config import settings
from ..schemas.admin import CreateNutritionistRequest


class SupabaseAdminService:
    def __init__(self) -> None:
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Backend Supabase nao configurado. Defina SUPABASE_URL e "
                    "SUPABASE_SERVICE_ROLE_KEY em backend/.env e reinicie a API."
                ),
            )

        self.supabase_url = settings.supabase_url.rstrip("/")
        self.service_key = settings.supabase_service_role_key

    @property
    def service_headers(self) -> dict[str, str]:
        return {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json",
        }

    async def get_user_from_access_token(self, token: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(
                    f"{self.supabase_url}/auth/v1/user",
                    headers={
                        "apikey": self.service_key,
                        "Authorization": f"Bearer {token}",
                    },
                )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Não foi possível validar o acesso. Tente novamente em instantes.",
            ) from None

        if response.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token.",
            )

        return response.json()

    async def assert_admin(self, token: str) -> dict:
        auth_user = await self.get_user_from_access_token(token)
        user_id = auth_user.get("id")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuário não encontrado.",
            )

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(
                    f"{self.supabase_url}/rest/v1/profiles",
                    headers=self.service_headers,
                    params={
                        "id": f"eq.{user_id}",
                        "select": "id,email,role,is_active",
                        "limit": "1",
                    },
                )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Nao foi possivel validar o perfil no Supabase.",
            ) from None

        if response.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "Nao foi possivel validar o perfil admin no Supabase: "
                    f"{self._extract_error(response)}"
                ),
            )

        rows = response.json()
        profile = rows[0] if rows else None

        if not profile or profile.get("role") != "admin" or profile.get("is_active") is False:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only active admins can create nutritionists.",
            )

        return profile

    async def create_nutritionist(self, payload: CreateNutritionistRequest) -> dict:
        created_user_id: str | None = None

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                auth_response = await client.post(
                    f"{self.supabase_url}/auth/v1/admin/users",
                    headers=self.service_headers,
                    json={
                        "email": payload.email,
                        "password": payload.password,
                        "email_confirm": True,
                        "user_metadata": {
                            "full_name": payload.full_name,
                            "role": "nutritionist",
                            "must_change_password": True,
                        },
                    },
                )

                if auth_response.status_code >= 400:
                    self._raise_supabase_error(auth_response)

                auth_user = auth_response.json()
                created_user_id = auth_user["id"]

                profile_response = await client.post(
                    f"{self.supabase_url}/rest/v1/profiles",
                    headers={
                        **self.service_headers,
                        "Prefer": "resolution=merge-duplicates,return=representation",
                    },
                    params={"on_conflict": "id"},
                    json={
                        "id": created_user_id,
                        "full_name": payload.full_name,
                        "email": payload.email,
                        "role": "nutritionist",
                        "is_active": True,
                    },
                )

                if profile_response.status_code >= 400:
                    await self._delete_auth_user(client, created_user_id)
                    self._raise_supabase_error(profile_response)

                nutritionist_response = await client.post(
                    f"{self.supabase_url}/rest/v1/nutritionists",
                    headers={
                        **self.service_headers,
                        "Prefer": "resolution=merge-duplicates,return=representation",
                    },
                    params={"on_conflict": "user_id"},
                    json={
                        "user_id": created_user_id,
                        "crn": payload.crn,
                        "specialty": payload.specialty,
                        "bio": payload.bio,
                    },
                )

                if nutritionist_response.status_code >= 400:
                    await self._delete_auth_user(client, created_user_id)
                    self._raise_supabase_error(nutritionist_response)
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Não foi possível concluir o cadastro. Tente novamente em instantes.",
            ) from None

        nutritionist = nutritionist_response.json()[0]

        return {
            "profile_id": created_user_id,
            "nutritionist_id": nutritionist["id"],
            "email": payload.email,
            "full_name": payload.full_name,
            "role": "nutritionist",
        }

    async def _delete_auth_user(self, client: httpx.AsyncClient, user_id: str) -> None:
        await client.delete(
            f"{self.supabase_url}/auth/v1/admin/users/{user_id}",
            headers=self.service_headers,
        )

    def _raise_supabase_error(self, response: httpx.Response) -> None:
        detail = self._extract_error(response)
        status_code = status.HTTP_400_BAD_REQUEST
        normalized = detail.lower()

        if (
            "already been registered" in normalized
            or "already registered" in normalized
            or "already exists" in normalized
            or "duplicate" in normalized
        ):
            status_code = status.HTTP_409_CONFLICT
            detail = "Este e-mail já está cadastrado. Use outro e-mail."

        raise HTTPException(status_code=status_code, detail=detail)

    def _extract_error(self, response: httpx.Response) -> str:
        try:
            body = response.json()
        except ValueError:
            return response.text or "Supabase request failed."

        return (
            body.get("msg")
            or body.get("message")
            or body.get("error_description")
            or body.get("error")
            or "Supabase request failed."
        )
