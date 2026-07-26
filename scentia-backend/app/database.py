from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

# Motor de conexión a la base de datos
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

# Sesión local para ejecutar queries
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Clase base para la definición de modelos ORM
Base = declarative_base()

# Inyección de dependencia para obtener la sesión en cada endpoint
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()