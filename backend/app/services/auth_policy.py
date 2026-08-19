from fastapi import HTTPException, status


PASSWORD_CHANGE_REQUIRED_DETAIL = (
    "Troque a senha provisória antes de continuar."
)


def requires_password_change(auth_user: dict) -> bool:
    app_metadata = auth_user.get("app_metadata") or {}
    if "must_change_password" in app_metadata:
        return _is_true(app_metadata.get("must_change_password"))

    # Compatibility for accounts created before the flag became server-owned.
    user_metadata = auth_user.get("user_metadata") or {}
    return _is_true(user_metadata.get("must_change_password"))


def assert_password_change_complete(auth_user: dict) -> None:
    if requires_password_change(auth_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=PASSWORD_CHANGE_REQUIRED_DETAIL,
        )


def _is_true(value: object) -> bool:
    return value is True or value == "true"
