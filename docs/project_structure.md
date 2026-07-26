scentia-project/
├── data/
│   └── fragrantica_data_from_scraper.csv   # Tu CSV original de scraping
│
├── backend/                                # Código de Python (FastAPI + Base de Datos + IA)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                         # Punto de entrada de FastAPI
│   │   ├── config.py                       # Carga de variables de entorno (.env)
│   │   ├── database.py                     # Conexión a PostgreSQL (SQLAlchemy)
│   │   ├── models.py                       # Modelos ORM de PostgreSQL (Users, Fragrances, etc.)
│   │   ├── schemas.py                      # Validadores Pydantic (Login, DTOs)
│   │   ├── auth.py                         # Lógica de Hashing y Generación de JWT
│   │   └── routers/
│   │       ├── auth_router.py              # Endpoints: /api/v1/auth/login, /me
│   │       ├── collection_router.py        # Endpoints: /api/v1/collection
│   │       ├── catalog_router.py           # Endpoints: /api/v1/fragrances
│   │       └── assistant_router.py         # Endpoints: /api/v1/assistant
│   ├── scripts/
│   │   ├── init_db.sql                     # Script SQL con el DDL de PostgreSQL
│   │   └── seed_fragrances.py              # Script para importar el CSV a PostgreSQL
│   ├── .env                                # VARIABLES DE SESIÓN Y SECRETOS (NO SUBIR A GIT)
│   ├── .env.example                        # Plantilla pública de variables
│   └── requirements.txt                    # Dependencias de Python (fastapi, uvicorn, psycopg2, etc.)
│
├── frontend/                               # Código de React / Next.js + Tailwind
│   ├── app/
│   │   ├── layout.jsx
│   │   ├── page.jsx                        # Tu dashboard modular de React
│   │   └── globals.css
│   ├── public/                             # Imágenes, logo y favicon de SCENTIA
│   ├── .env.local                          # Variables de entorno del Frontend
│   ├── package.json
│   └── tailwind.config.js
│
├── .gitignore                              # Archivos a ignorar por Git (.env, node_modules, __pycache__)
└── README.md                               # Documentación general de instalación