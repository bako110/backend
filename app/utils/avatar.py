# app/utils/avatar.py
from urllib.parse import quote

def generate_default_avatar_url(first_name: str, last_name: str) -> str:
    name = f"{first_name} {last_name}"
    return f"https://ui-avatars.com/api/?name={quote(name)}&background=0D8ABC&color=fff&size=128"
