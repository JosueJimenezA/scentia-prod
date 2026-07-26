import sys
import os
import pandas as pd
import json
import ast
import re

# Agregar el directorio raíz de scentia-backend al path de Python
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from app.models import Fragrance, UserCollection
from app.limpieza import (
    parse_notes_list_clean,
    separate_distributions_from_dict,
    parse_dict,
    safe_int,
    safe_float
)

def reseed_fragrances():
    db = SessionLocal()
    csv_path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__), 
        "../data/fragrantica_data_from_scraper.csv"
    )
)
    if not os.path.exists(csv_path):
        print(f"❌ Error: No se encontró el archivo en {csv_path}")
        return

    print("⚠️ Vaciando tablas 'user_collections' y 'fragrances'...")
    db.query(UserCollection).delete()
    db.query(Fragrance).delete()
    db.commit()

    print(f"📦 Leyendo datos desde {csv_path}...")
    df = pd.read_csv(csv_path, sep='|')
    print(f"🔄 Insertando {len(df)} registros procesados...")

    inserted_count = 0
    for _, row in df.iterrows():
        row_dict = row.to_dict()
        longevity_dist, sillage_dist, gender_voted_dist, price_value_dist = separate_distributions_from_dict(row_dict)

        fragrance = Fragrance(
            fragrantica_url=str(row_dict['url']),
            bottle_image_url=str(row_dict.get('bottle_image_url')) if pd.notna(row_dict.get('bottle_image_url')) else None,
            name=str(row_dict.get('name_raw', '')).strip() if pd.notna(row_dict.get('name_raw')) else 'Sin Nombre',
            designer=str(row_dict.get('designer_raw', '')).strip().title() if pd.notna(row_dict.get('designer_raw')) else 'Desconocido',
            global_rating=safe_float(row_dict.get('global_rating')),
            global_rating_count=safe_int(row_dict.get('global_rating_count')),
            
            top_notes=parse_notes_list_clean(row_dict.get('top_notes_raw')),
            heart_notes=parse_notes_list_clean(row_dict.get('heart_notes_raw')),
            base_notes=parse_notes_list_clean(row_dict.get('base_notes_raw')),
            perfumers=parse_notes_list_clean(row_dict.get('perfumers_raw')),
            
            seasons_dist=parse_dict(row_dict.get('seasons_raw_dist')),
            time_of_day_dist=parse_dict(row_dict.get('time_of_day_raw_dist')),
            longevity_dist=longevity_dist,
            sillage_dist=sillage_dist,
            price_value_dist=price_value_dist,
            gender_voted_dist=gender_voted_dist,
            
            reviews_corpus=str(row_dict.get('reviews_text_corpus', '')) if pd.notna(row_dict.get('reviews_text_corpus')) else ""
        )
        db.add(fragrance)
        inserted_count += 1

        if inserted_count % 100 == 0:
            db.commit()
            print(f"  ✓ {inserted_count} perfumes procesados y guardados...")

    db.commit()
    db.close()
    print(f"✅ Proceso finalizado. Se cargaron {inserted_count} fragancias homogenizadas.")

if __name__ == "__main__":
    reseed_fragrances()