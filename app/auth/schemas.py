from pydantic import BaseModel, EmailStr, validator
from typing import Optional

class UserRegister(BaseModel):
    email: Optional[EmailStr] = None  # email optionnel si inscription par téléphone
    phone: Optional[str] = None       # téléphone optionnel si inscription par email
    password: str
    password_confirm: str
    first_name: str
    last_name: str

    @validator('password_confirm')
    def passwords_match(cls, v, values, **kwargs):
        if 'password' in values and v != values['password']:
            raise ValueError('Les mots de passe ne correspondent pas')
        return v

    @validator('phone')
    def validate_phone_or_email(cls, v, values, **kwargs):
        email = values.get('email')
        phone = v
        if not email and not phone:
            raise ValueError('Email ou téléphone est requis')
        return v

    @validator('phone')
    def validate_phone_format(cls, v):
        if v and not v.startswith('+'):
            # Optionnel: validation basique du format téléphone
            if not v.replace(' ', '').replace('-', '').isdigit():
                raise ValueError('Format de téléphone invalide')
        return v


class UserLogin(BaseModel):
    identifier: str  # email ou téléphone
    password: str

    @validator('identifier')
    def identifier_required(cls, v):
        if not v or v.strip() == "":
            raise ValueError("Email ou téléphone est requis")
        return v.strip()


class LogoutResponse(BaseModel):
    msg: str


class ForgotPasswordRequest(BaseModel):
    identifier: str  # Changé de 'email' à 'identifier' pour supporter email ET téléphone

    @validator('identifier')
    def identifier_required(cls, v):
        if not v or v.strip() == "":
            raise ValueError("Email ou téléphone est requis")
        return v.strip()


class VerifyCodeRequest(BaseModel):
    code: str
    @validator('code')
    def code_required(cls, v):
        if not v or v.strip() == "":
            raise ValueError("Code de vérification requis")
        return v.strip()


class ResetPasswordRequest(BaseModel):
    newPassword: str  # Changé de 'email' à 'identifier'
    confirmPassword: str

    @validator('confirmPassword')
    def passwords_match(cls, v, values):
        new_password = values.get('newPassword')
        if new_password and v != new_password:
            raise ValueError('Les mots de passe ne correspondent pas')
        if len(v) < 6:
            raise ValueError("Le mot de passe doit contenir au moins 6 caractères")
        return v
        

class SocialLoginRequest(BaseModel):
    platform: str  # "google" ou "facebook"
    access_token: str