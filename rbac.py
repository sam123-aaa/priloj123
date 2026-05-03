from fastapi import HTTPException


def require_any_role(user, allowed_roles):
    role_code = user["role_code"]
    if role_code == "admin":
        return user
    if role_code not in allowed_roles:
        raise HTTPException(status_code=403, detail="Нет доступа")
    return user


def require_owner_or_admin(user, owner_id):
    if user["role_code"] == "admin":
        return
    if owner_id != user["user_id"]:
        raise HTTPException(status_code=403, detail="Нет доступа к чужим данным")
