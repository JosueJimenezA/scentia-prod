import os
from dotenv import load_dotenv

# Cargar variables desde el archivo .env
load_dotenv()

class Settings:
    PROJECT_NAME: str = "SCENTIA API"
    PROJECT_VERSION: str = "1.0.0"
    
    # Base de datos (por defecto usa PostgreSQL en localhost)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://postgres:postgres@localhost:5432/scentia_db"
    )
    
    # Secretos para firma de tokens JWT
    SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "scentia_super_secret_jwt_key_2026_x89a")
    ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "43200"))

settings = Settings()