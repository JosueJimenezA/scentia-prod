from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
from app.routers import auth_router, catalog_router, collection_router, weather_router, profile_router, main_agent_router

# Crear las tablas en la base de datos si no existen
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="Backend API para la plataforma SCENTIA (High-End Perfumery Intelligence)"
)

# Configuración de CORS para permitir solicitudes desde React/Next.js
#app.add_middleware(
    #CORSMiddleware,
    #allow_origins=["*"],  # En producción se sustituye por el dominio de Vercel
    #allow_credentials=True,
    #allow_methods=["*"],
    #allow_headers=["*"],
#)

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://scentia-prod.vercel.app",  # Tu URL de producción en Vercel
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar Routers
app.include_router(auth_router.router)
app.include_router(catalog_router.router)
app.include_router(collection_router.router)
app.include_router(weather_router.router)  # agente de clima
app.include_router(profile_router.router)  # agente de perfil olfativo
app.include_router(main_agent_router.router)  # agente de perfumería

@app.get("/")
def root():
    return {
        "message": "Bienvenido a SCENTIA API",
        "version": settings.PROJECT_VERSION,
        "status": "online"
    }

from sqlalchemy import inspect

@app.get("/test-db")
def test_db():
    inspector = inspect(engine)
    tablas = inspector.get_table_names()
    return {
        "status": "connected",
        "tables": tablas
    }