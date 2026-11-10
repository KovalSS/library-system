"""Хешування паролів (REQ-NF-003) і генерація токенів."""
import hashlib
import hmac
import secrets

# Навмисно повільне хешування ускладнює перебір паролів, якщо базу вкрадуть (рекомендація OWASP).
DEFAULT_ITERATIONS = 200_000


def hash_password(password: str, iterations: int = DEFAULT_ITERATIONS) -> str:
    """Хешує пароль за стандартом PBKDF2-HMAC-SHA256 з криптографічною сіллю (REQ-NF-003)."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    """Перевіряє відповідність пароля збереженому хешу з константним часом порівняння."""
    _, iterations, salt, digest = stored.split("$")
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations)).hex()
    return hmac.compare_digest(candidate, digest)


def new_token() -> str:
    """Генерує безпечний псевдовипадковий криптографічний токен для сесій і пошти."""
    return secrets.token_urlsafe(32)
