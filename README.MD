# 🌸 SCENTIA — Arquitectura y Estructura del Proyecto

![Logo de Scentia](imagenes/logo.svg)

> **Scentia** es un sistema inteligente de recomendación olfativa impulsado por IA, agentes conversacionales, análisis de sentimiento y recomendaciones contextuales basadas en el clima y colección del usuario.

---

## 📁 Estructura del Repositorio

```text
SCENTIA/
├── 🗂️ auxiliares/                       # Archivos temporales de soporte utilizados durante el desarrollo
├── 📊 data/                             # Checkpoints de datos crudos (archivos CSV de prueba)
├── 🧪 debug/                            # Entornos de prueba, prototipado de modelos y libretas Jupyter
│   ├── 🔍 buscar_url.py                 # Validación de URLs y headers devueltos por routers
│   ├── 📄 data_fixed.csv                # Dataset refinado tras la exploración inicial
│   ├── 🤖 debug_agente.ipynb            # Pruebas de integración del agente conversacional y WebSearch
│   ├── 🧪 debug.ipynb                   # Búsqueda e inspección individual de fragancias
│   ├── 📊 eda_perfume_catalog.ipynb     # Análisis exploratorio, clustering, ingeniería de características e inferencia
│   ├── ⚙️ ingenieria_train_profile.py    # Refinamiento del pipeline de datos y preparación de modelos para el backend
│   ├── 🗺️ pipeline_analisis_reviews.txt # Diagrama de flujo del análisis de sentimiento de reseñas
│   └── 📈 test_inference.py             # Pruebas de actualización dinámica de pesos y similitud coseno
├── 📑 docs/                             # Documentación técnica y académica del proyecto
├── 📦 modelos/                          # Directorio dinámico para artefactos de reentrenamiento (.pkl, .parquet, .npy)
├── ⚙️ scentia-backend/                   # API RestFul desarrollada en FastAPI y motor de Inteligencia Artificial
│   ├── 🚀 app/                          # Núcleo de la aplicación FastAPI
│   │   ├── 🧠 prompts/                  # Ingeniería de prompts, guardrails e instrucciones de sistema
│   │   │   ├── 💬 Main_prompt.py        # Prompt principal del asistente conversacional, guardrails y tool WebSearch
│   │   │   └── 🌤️ weather_prompts.py    # Prompts estructurados para recomendación olfativa por clima
│   │   ├── 🛣️ routers/                  # Controladores y endpoints organizados por módulos
│   │   │   ├── 🔑 auth_router.py        # Autenticación, registro e inicio de sesión de usuarios
│   │   │   ├── 📚 catalog_routher-py    # Gestión del catálogo de perfumes e integración del scraper
│   │   │   ├── 🧴 collection_router.py # Gestión de la colección personal de fragancias del usuario
│   │   │   ├── 🤖 main_agent_router.py  # Endpoint del asistente conversacional multicriterio
│   │   │   ├── 🧬 profile_router.py     # Inferencia dinámica del perfil olfativo del usuario
│   │   │   ├── 🩺 router_diag.py        # Diagnóstico de conectividad con la API de Open-Meteo
│   │   │   └── 🌡️ weather_reouter.py    # Endpoint para recomendaciones adaptadas al clima actual/pronóstico
│   │   ├── 🛠️ services/                 # Servicios de lógica de negocio y agentes
│   │   │   ├── 🧠 inference_service.py  # Motor de inferencia y cálculo de recomendaciones en tiempo real
│   │   │   ├── 🗣️ main_agent.py         # Orquestador del asistente conversacional (procesamiento de texto y audio)
│   │   │   ├── 🌦️ open_meteo.py         # Cliente para la API de clima y pronósticos meteorológicos
│   │   │   └── 🧭 weather_agent.py      # Agente para detección de intención geográfica y extracción del clima
│   │   ├── 🔒 auth.py                   # Cifrado de contraseñas y emisión de tokens JWT
│   │   ├── ⚙️ config.py                 # Variables de entorno y configuración global
│   │   ├── 🗄️ database.py               # Configuración del ORM y conexión a la base de datos
│   │   ├── 🧹 limpieza.py               # Funciones de homogeneización y limpieza de cadenas/datos
│   │   ├── 🏁 main.py                   # Punto de entrada de la aplicación FastAPI y políticas CORS
│   │   ├── 📐 models.py                 # Definición de modelos de base de datos (ORM)
│   │   ├── 📝 schemas.py                # Esquemas Pydantic para validación de entrada/salida
│   │   └── 🔧 utils.py                  # Utilidades generales y helpers
│   ├── 📂 data/                         # Datasets base cargados en el backend
│   │   ├── 📄 fragrantica_data_from_scraper.csv # Catálogo crudo extraído mediante Web Scraping
│   │   └── 🔗 perfume_catalog_links.csv # URLs de referencia para extracción continua
│   ├── 🤖 modelos/                      # Artefactos y modelos listos para inferencia
│   │   ├── 📊 df_master.parquet         # Dataset optimizado con ingeniería de variables y clusters
│   │   ├── ⚖️ profiling_artifacts.pkl   # Pesos ajustados del modelo de perfilaría
│   │   ├── 🧮 X_embedding.npy           # Representaciones vectoriales (Embeddings) de las fragancias
│   │   └── 📸 Snapshot/                 # Histórico y traza de los datos de entrenamiento
│   ├── 🕷️ scraper/                      # Módulo de extracción web
│   │   └── 🔎 scraper_busqueda.py       # Scraper en tiempo real para incorporar nuevas fragancias al sistema
│   ├── 📜 scripts/                      # Scripts de base de datos e inicialización
│   │   ├── 🛢️ init_db.sql              # Esquema SQL de la base de datos
│   │   └── 🌱 seed_fragrances.py        # Poblamiento automático inicial del catálogo
│   ├── 🐳 DockerFile                     # Configuración de contenedorización Docker para el backend
│   └── 📄 requirements.txt              # Librerías y dependencias de Python del servidor backend
├── 💻 scentia-frontend/                 # Aplicación web interactiva construida en Next.js
│   ├── 📁 app/                          # Enrutamiento basado en App Router, páginas y componentes React
│   ├── 🖼️ public/                       # Recursos multimedia, logos y archivos estáticos
│   ├── ⚙️ .env.local                     # Variables de entorno para el entorno de cliente
│   ├── 🚫 .gitignore                    # Reglas de exclusión para control de versiones Git
│   ├── 🤖 AGENTS.md                     # Directrices de arquitectura y diseño de agentes
│   ├── 📜 CLAUDE.md                     # Guía de estilo e instrucciones del proyecto
│   ├── ⚙️ jsconfig.json                 # Mapeo de rutas absolutas para JavaScript
│   ├── ⚡ next.config.mjs               # Ajustes y optimización de compilación Next.js
│   ├── 🔒 package-lock.json             # Registro exacto de versiones instaladas de npm
│   └── 📄 package.json                  # Definición del proyecto Node.js y dependencias
├── 🚀 run_proyect.py                    # Script de automatización para despliegue y ejecución local
└── 📄 requerimentes.txt                 # Dependencias globales del proyecto