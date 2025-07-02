from fastapi import Depends, HTTPException, status
from app.auth.dependencies import get_current_user

def require_role(role: str):
    def wrapper(user = Depends(get_current_user)):
        if user.role != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès interdit (rôle requis)"
            )
        return user
    return wrapper
