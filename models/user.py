from pydantic import BaseModel
class UserRegister(BaseModel):
    username: str
    email: str
    password: str
class Token(BaseModel):
    access_token: str
    token_type: str
