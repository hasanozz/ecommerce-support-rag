from pydantic import BaseModel, EmailStr


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    display_name: str
    avatar_url: str | None
    is_admin: bool
