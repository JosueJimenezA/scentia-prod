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



# Reproducibilidad de Resultados y Ejecución en Local

Con el objetivo de garantizar la validez, auditoría y correcta ejecución de la plataforma fuera de los servidores de producción, se describen los pasos secuenciales necesarios para desplegar la arquitectura completa en un entorno local.

## Guía Paso a Paso para el Despliegue Local

1. **Clonación del Repositorio Oficial:**  
   Obtener el código fuente del proyecto ejecutando el comando de clonación desde la terminal:
   ```bash
   git clone https://github.com/JosueJimenezA/scentia-prod.git
   ```

2. **Cambio a la Rama de Producción Estable:**  
   Acceder al directorio del proyecto y cambiar hacia la rama refactorizada y probada:
   ```bash
   cd scentia-prod
   git checkout estabilizar-refactor
   git pull origin estabilizar-refactor
   ```

3. **Instalación de Dependencias del Sistema:**  
   Las dependencias pueden gestionarse mediante dos vías equivalentes:
   * *Entorno Python Virtual:* Instalación del archivo de requerimientos mediante pip:
     ```bash
     pip install -r requirements.txt
     ```

4. **Configuración de Archivos de Variables de Entorno (`.env`):**  
   Es indispensable crear dos archivos de configuración local para inyectar las credenciales secretas y llaves de API (las cuales se proporcionarán de forma privada):
   * Crear un archivo `.env` en la ruta `scentia-backend/.env` con las claves del servidor y base de datos.
   * Crear un archivo `.env.local` en la ruta `scentia-frontend/.env.local` con las claves de entorno de la interfaz web.

5. **Ejecución Unificada de la Aplicación:**  
   Ejecutar el script principal de orquestación en Python:
   ```bash
   python run_proyect.py
   ```
   Este script lanzará simultáneamente los servicios de *Backend* (FastAPI) y *Frontend* (Next.js/React), proporcionando en la consola la dirección de puerto local (`http://localhost:3000`) para acceder e interactuar con la interfaz completa de manera estable.


   ## Archivos Críticos del Desarrollo

A continuación se detallan los módulos, scripts y artefactos clave que conforman la arquitectura y la lógica de negocio de la plataforma:

### 1. Fase de Análisis Exploratorio y Modelado
* `debug/eda_perfume_catalog.ipynb`: Cuaderno de Jupyter que contiene el análisis exploratorio de datos (EDA), la fase de ingeniería pre-producción, la definición y entrenamiento de modelos, la justificación técnica de las variables seleccionadas y los principales hallazgos del proyecto.

### 2. Pipelines de Datos y Entrenamiento ML
* `debug/ingenieria_train.py`: Script principal encargado del pipeline completo de Machine Learning: extracción de datos desde PostgreSQL, procesamiento y limpieza, ingeniería de características, análisis léxico-bayesiano de reseñas, vectorización mediante TF-IDF, reducción de dimensionalidad por Descomposición en Valores Singulares (SVD) y agrupamiento mediante K-Means.
  > **Nota de versión:** El archivo `debug/ingenieria_train_profile.py` corresponde a una iteración anterior y debe descartarse.

### 3. Motor de Inferencia y Backend (FastAPI)
* `scentia-backend/app/services/inference_v2.py`: Motor *Singleton* que mantiene cargados en memoria los artefactos del modelo ML. Realiza el cálculo de vectores, asignación de clusters y generación de recomendaciones en tiempo real. Incluye soporte para inferencia *on-the-fly* para fragancias que no se encuentran en el conjunto de datos de entrenamiento original.
  > **Nota de versión:** El archivo `scentia-backend/app/services/inference_service.py` es una versión obsoleta y no debe considerarse.
* `scentia-backend/app/main.py`: Punto de entrada del servidor FastAPI. Configura las políticas de CORS y orquesta los routers de la aplicación.
* `scentia-backend/app/models.py` y `scentia-backend/app/schemas.py`: Módulos que definen el modelo relacional de la base de datos (ORM con SQLAlchemy) y las validaciones de esquemas de datos (Pydantic), respectivamente.

### 4. Artefactos del Modelo de Machine Learning
* `scentia-backend/app/modelos/`: Directorio que almacena los artefactos consumidos por el motor de inferencia:
  * `df_master`: Conjunto de datos procesado con las variables de ingeniería y etiquetas finales de clusters.
  * `profiling_artifacts.pkl`: Pesos, transformadores y parámetros entrenados del modelo.
  * `X_embeding.npy`: Matriz con las representaciones vectoriales (*embeddings*) de las fragancias.

### 5. Ingesta y Poblado de Datos
* `scentia-backend/app/scraper/scraper_busqueda.py`: Módulo especializado en la extracción y web scraping para la ingesta masiva de datos.
* `scentia-backend/app/scripts/seed_fragrances.py`: Script de sembrado que procesa el archivo de datos crudos para poblar la tabla principal de fragancias en la base de datos relacional.