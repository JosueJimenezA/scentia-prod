import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Importar el modelo Fragrance
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../scentia-backend')))
from app.models import Fragrance

def check_url_in_db(target_url: str):
    RENDER_DATABASE_URL = "postgresql://scentia_admin:m6TZWG6R3AyxqKtJ6cU2sSJS5ogFXf91@dpg-d9iquh37uimc73c12plg-a.oregon-postgres.render.com/scentia_db?sslmode=require"
    
    engine = create_engine(RENDER_DATABASE_URL, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # Aseguramos limpiar espacios accidentales
        clean_url = target_url.strip()

        # Consulta directa por la columna fragrantica_url
        fragrance = db.query(Fragrance).filter(Fragrance.fragrantica_url == clean_url).first()

        if fragrance:
            print(f"✅ LA FRAGANCIA EXISTE EN LA BASE DE DATOS")
            print(f"   • ID (UUID):  {fragrance.id}")
            print(f"   • Nombre:     {fragrance.name}")
            print(f"   • Diseñador:  {fragrance.designer}")
            print(f"   • URL:        {fragrance.fragrantica_url}")
            return True
        else:
            print(f"❌ NO SE ENCONTRÓ NINGÚN REGISTRO con la URL:")
            print(f"   '{clean_url}'")
            return False

    except Exception as e:
        print(f"💥 Error al consultar la BD: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    # Reemplaza con la URL exacta que deseas verificar
    URL_A_BUSCAR = "https://www.fragrantica.es/perfume/Armaf/Club-de-Nuit-Sillage-64105.html"
    check_url_in_db(URL_A_BUSCAR)