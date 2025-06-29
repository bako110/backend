from pydantic import BaseModel
from typing import Optional

class UserProfileIn(BaseModel):
    first_name: Optional[str]
    last_name: Optional[str]
    avatar_url: Optional[str]
    bio: Optional[str]

class UserProfileOut(UserProfileIn):
    user_email: str
