SCENTIA/
├── auxiliares/ # Son archivos que sirvieron para una tarea especifica durante el desarrollo pero que una vez desplegada la aplicación ya no son necesarios.
├── data/ # son archivos csv de prueba, eran "checkpoints" durante el diseño del scraper, no deben ser tomados en cuenta
├── debug/ # Esta carpeta contiene los notebooks y scripts que fueron necesarios para la implementación de las funcionalidades, el entrenamiento y pruebas de funcionalidad para el despligue
│   ├── buscar_url.py # Busca si existe una url especifica en la base de datos, fue necesaria para identificar los header que devolvian los routers de recomendacion y perfil de usuario
│   ├── data_fixed.csv # Archivo generado tras la exploración de variables y primera aproximación de la ingenieria
│   ├── debug_agente.ipynb # Libreta de Jupyter que contiene funciones para debuguear el funcionamiento del asistente, verifica que llame correctamente a la tool de websearch y que devuelva correctamente el output que usará el LLM
│   ├── debug.ipynb # Este archivo sirve para el debug de la funcionalidad de buscar nuevas fragrancias de forma individual
│   ├── eda_perfume_catalog.ipynb # Contiene el analsis de la información obtenida, el tratamiento de las variables e ingenieria, clustering e inferencia
│   ├── ingenieria_train_profile.py # Se refina el proceso generado durante el eda, adaptando la estructura de los datos contenidos en la base de datos y prepara los archivos de salida que se cargaran al backend como modelos de inferencia
│   ├── pipeline_analisis_reviews.txt # Muestra mediante un diagrama el pipeline usado para el analisis de sentimiento de las reviews de los perfumes
│   ├── test_inference.py # Este script debuguea como se actualizan los pesos del modelo cuando el usuario tiene nuevos elementos en su colecccion y como la verosimilitud de coseno se actualiza para garantizar que las recomendaciones no sean estaticas.
├── docs/ # Contiene la documentación del proyecto
├── modelos/ # Es una carpeta auxiliar, si se volviera a entrenar el modelo aqui apareceria el archivo .plk, el dataset en formato parquet y los artifactos en .npy, aunque sea eliminada, al momento de reentrenar se vuelve a crear el directorio
├── scentia-backend/
│   ├── app/
│   │   ├── __pycache__/
│   │   ├── prompts/
│   │   │   ├── Main_prompt.py # Contiene el prompt engeniering del asistente conversacional, tambien los guardrail y se define el tool de web search
│   │   │   ├── weather_prompts.py # Contiene la estrutura del prompt de recomendaciones basadas en clima
│   │   ├── routers/
│   │   │   ├── auth_router.py # Necesario para log-in / sign-in de usuarios
│   │   │   ├── catalog_routher-py # Contiene los endopoints para la pestaña "Catalogo" incluyendo el scraper para integrar una nueva fragrancia
│   │   │   ├── collection_router.py # Endopoints para identificar que perfumes tiene el usuario en su coleccion
│   │   │   ├── main_agent_router.py # Endopoints para la llamada al asistente principal
│   │   │   ├── profile_router.py # Endopoints para inferir el perfil olfativo del usuario, se actualiza con base a las preferencias del usuario.
│   │   │   ├── router_diag.py # Endpoint auxiliar para validar el estado de la peticion get de la API de open-meteo (validar que no exista bloqueo por IP)
│   │   │   ├── weather_reouter.py # Endpoints para el asistente basado en clima asi como recomendaciones personalizadas.
│   │   ├── services/
│   │   │   ├── inference_service.py # Motor principal de inferencia, contiene la lógica para las recomendaciones on the fly
│   │   │   ├── main_agent.py # Es el insumo que toma el router del asistente, indexa la funcionalidad de texto y audio para peticiones
│   │   │   ├── open_meteo.py # Servicio para obtener los datos de temperatura y os forecasts
│   │   │   ├── weather_agent.py # Identifca la itención valida para proceder a buscar una localización y obtener los pronosticos del clima.
│   │   ├── auth.py # Genera las credenciales de login, incluye encriptación
│   │   ├── config.py # Archivo de configuración global del backend, carga las variables de entorno 
│   │   ├── database.py # Inicia el motor de la base de datos
│   │   ├── limpieza.py # Reglas de limpieza para homogenizar la estructura en las bases de datos
│   │   ├── main.py # Inicializa todos los endpoints de la App, configura los CORS
│   │   ├── models.py # Estructura de la base de datos
│   │   ├── schemas.py # Esquemas para login
│   │   └── utils.py # Funciones varias necesarias para algun proceso
│   ├── data/
│   │   └── fragrantica_data_from_scraper.csv # Data core del proyecto, en crudo, tal cual sale del scraper
│   │   └── perfume_catalog_links.csv # lista de urls sobre la que itera el scraper
│   ├── modelos/
│   │   └── df_master.parquet # Archivo limpio y con variables ingenierizadas y con etique de cluster
│   │   └── profiling_artifacts.pkl # Los pesos del modelo entrenado
│   │   └── X_embedding.npy # Configuración de los embedings entrenados
│   │   └── Snapshot # Datos con los que se entreno el modelo (para trazabilidad)
│   ├── scraper/
│   │   └── scraper_busqueda.py # Es el scraper que toma la app para obtener nuevos perfumes
│   ├── scripts/
│   │   └── init_db.sql # Instrucciones de creacion de las tablas y esquemas
│   │   └── seed_fragrances.py # Script para poblar la tabla de fragrancias
│   ├── DockerFile # Configuracion de Docker
│   └── requirements.txt # Requerimientos para backend
└── scentia-frontend/
    ├── .next/
    ├── app/ # Core principal del frontend, contiene la estrutura html y css para la interfaz
    ├── node_modules/
    ├── public/
    ├── .env.local
    ├── .gitignore
    ├── AGENTS.md
    ├── CLAUDE.md
    ├── jsconfig.json
    ├── next.config.mjs
    ├── package-lock.json
    └── package.json
├── run_proyect.py # Lanza el proyecto en local
├── requerimentes.txt # Requerimientos para el proyecto



