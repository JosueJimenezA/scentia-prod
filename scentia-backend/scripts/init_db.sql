# Crear la base de datos en PostgreSQL
createdb -U postgres scentia_db

# Ejecutar el script SQL para crear las tablas
psql -U postgres -d scentia_db -f backend/scripts/init_db.sql