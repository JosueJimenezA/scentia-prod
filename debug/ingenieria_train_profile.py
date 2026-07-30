import os
import sys
import json
import random
import pickle
from datetime import datetime
import numpy as np
import pandas as pd

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler
from scipy.sparse import hstack
from sklearn.decomposition import TruncatedSVD
from sklearn.cluster import KMeans

# Agregar la raíz del backend al PATH para importar los módulos de la aplicación
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../scentia-backend')))

from app.database import SessionLocal
from app.models import Fragrance
from app.limpieza import parse_notes_list_clean, parse_dict

# ==============================================================================
# CONFIGURACIÓN GLOBAL
# ==============================================================================
APPLY_SYNTHETIC_INJECTION: bool = False

PERFUMERS_POOL = [
    "Olivier Polge", "Dominique Ropion", "Francis Kurkdjian",
    "Quentin Bisch", "Alberto Morillas", "Christine Nagel",
    "Jacques Cavallier", "Jean-Claude Ellena", "Thierry Wasser"
]

# ==============================================================================
# FUNCIONES AUXILIARES
# ==============================================================================
def load_fragrances_from_db() -> pd.DataFrame:
    """Consulta la tabla 'fragrances' en PostgreSQL y la convierte en DataFrame."""
    db = SessionLocal()
    try:
        print("🔍 Consultando la tabla 'fragrances' en PostgreSQL...")
        fragrance_records = db.query(Fragrance).all()
        
        if not fragrance_records:
            raise ValueError("❌ No se encontraron registros en la tabla 'fragrances'.")

        data = []
        for f in fragrance_records:
            data.append({
                'id': str(f.id),
                'url': f.fragrantica_url,
                'bottle_image_url': f.bottle_image_url,
                'name_raw': f.name,
                'designer_raw': f.designer,
                'global_rating': float(f.global_rating) if f.global_rating is not None else 0.0,
                'global_rating_count': f.global_rating_count,
                'top_notes_raw': f.top_notes,
                'heart_notes_raw': f.heart_notes,
                'base_notes_raw': f.base_notes,
                'perfumers_raw': f.perfumers,
                'seasons_raw_dist': f.seasons_dist,
                'time_of_day_raw_dist': f.time_of_day_dist,
                'longevity_fixed_dist': f.longevity_dist,
                'sillage_fixed_dist': f.sillage_dist,
                'price_value_fixed_dist': f.price_value_dist,
                'gender_fixed_dist': f.gender_voted_dist,
                'reviews_text_corpus': f.reviews_corpus
            })
            
        df = pd.DataFrame(data)
        print(f"✅ Se cargaron {len(df)} registros desde la base de datos.")
        return df
    finally:
        db.close()

def save_data_snapshot(df: pd.DataFrame, output_dir: str):
    """Guarda un CSV de snapshot para auditoría del dataset utilizado en el entrenamiento."""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_filename = f"training_snapshot_fragrances_{timestamp}.csv"
    snapshot_path = os.path.join(output_dir, snapshot_filename)
    
    # También guardar un alias 'latest' para fácil referencia
    latest_path = os.path.join(output_dir, "training_snapshot_fragrances_latest.csv")
    
    df.to_csv(snapshot_path, index=False, encoding='utf-8-sig')
    df.to_csv(latest_path, index=False, encoding='utf-8-sig')
    print(f"💾 Snapshot de entrenamiento guardado en:\n  - {snapshot_path}\n  - {latest_path}")

def format_count(val: int) -> str:
    if val >= 1000:
        formatted = f"{val / 1000:.1f}k"
        return formatted.replace(".0k", "k")
    return str(val)

def generate_synthetic_perfume_metrics():
    """Generador multinomial de métricas sintéticas condicionales."""
    profiles = ["fresh_citrus", "heavy_oriental", "mass_pleaser", "niche_polarizing"]
    profile = random.choice(profiles)

    if profile == "mass_pleaser":
        base_votes = random.randint(5000, 30000)
        weights_rating = [0.50, 0.30, 0.12, 0.05, 0.03]
    elif profile == "niche_polarizing":
        base_votes = random.randint(800, 8000)
        weights_rating = [0.35, 0.10, 0.05, 0.20, 0.30]
    else:
        base_votes = random.randint(10, 5000)
        weights_rating = [0.25, 0.35, 0.20, 0.12, 0.08]

    counts_rating = np.random.multinomial(base_votes, weights_rating)
    vibe_dict = {
        "love": format_count(counts_rating[0]),
        "like": format_count(counts_rating[1]),
        "ok": format_count(counts_rating[2]),
        "dislike": format_count(counts_rating[3]),
        "hate": format_count(counts_rating[4]),
    }

    if profile == "fresh_citrus":
        season_weights = [0.05, 0.35, 0.45, 0.15]
        tod_weights = [0.75, 0.25]
    elif profile == "heavy_oriental":
        season_weights = [0.50, 0.10, 0.05, 0.35]
        tod_weights = [0.20, 0.80]
    else:
        season_weights = [0.25, 0.25, 0.25, 0.25]
        tod_weights = [0.50, 0.50]

    season_votes = random.randint(int(base_votes * 0.6), int(base_votes * 1.2) + 1)
    counts_season = np.random.multinomial(season_votes, season_weights)
    tod_votes = random.randint(int(base_votes * 0.5), int(base_votes * 1.1) + 1)
    counts_tod = np.random.multinomial(tod_votes, tod_weights)

    seasons_dict = {
        "winter": format_count(counts_season[0]),
        "spring": format_count(counts_season[1]),
        "summer": format_count(counts_season[2]),
        "fall": format_count(counts_season[3]),
    }
    day_time_dict = {
        "day": format_count(counts_tod[0]),
        "night": format_count(counts_tod[1]),
    }

    perfumers_raw = ", ".join(random.sample(PERFUMERS_POOL, random.choice([1, 2]))) if random.random() < 0.85 else None

    return {
        "vibe_reactions_raw_dist": json.dumps(vibe_dict),
        "seasons_raw_dist": json.dumps(seasons_dict),
        "time_of_day_raw_dist": json.dumps(day_time_dict),
        "perfumers_raw": perfumers_raw
    }

# ==============================================================================
# PIPELINE DE ENTRENAMIENTO DE INGENIERÍA DE VARIABLES
# ==============================================================================
def run_feature_engineering_pipeline(df_raw: pd.DataFrame) -> tuple:
    df = df_raw.copy()

    # 1. Asignación de ID entero incremental
    if 'url' in df.columns:
        df['perfume_id'] = df.groupby('url').ngroup()
    else:
        df['perfume_id'] = np.arange(len(df))

    # 2. Inyección sintética condicional
    if APPLY_SYNTHETIC_INJECTION:
        print("⚠️ Aplicando Inyección Sintética de Datos (APPLY_SYNTHETIC_INJECTION = True)...")
        synth_data = pd.DataFrame([generate_synthetic_perfume_metrics() for _ in range(len(df))])
        for col in ["vibe_reactions_raw_dist", "seasons_raw_dist", "time_of_day_raw_dist", "perfumers_raw"]:
            df[col] = synth_data[col]
    else:
        print("ℹ️ Omitiendo Inyección Sintética. Procesando datos reales...")

    # 3. Construcción del Corpus Olfativo Ponderado (1x Salida, 2x Corazón, 3x Fondo)
    def build_weighted_corpus(row):
        val_top = row.get("top_notes_raw")
        val_mid = row.get("heart_notes_raw")
        val_base = row.get("base_notes_raw")

        if isinstance(val_top, (list, tuple)):
            val_top = ", ".join([str(x) for x in val_top])

        if isinstance(val_mid, (list, tuple)):
            val_mid = ", ".join([str(x) for x in val_mid])

        if isinstance(val_base, (list, tuple)):
            val_base = ", ".join([str(x) for x in val_base])
    
        # Ahora 'val' es un string/escalar y limpieza.py no romperá
        top = parse_notes_list_clean(val_top)
        #top = parse_notes_list_clean(row.get('top_notes_raw'))
        mid = parse_notes_list_clean(val_mid)
        base = parse_notes_list_clean(val_base)
        
        corpus = (top * 1) + (mid * 2) + (base * 3)
        return " ".join(corpus) if corpus else "unknown_note"

    df['notes_corpus_weighted'] = df.apply(build_weighted_corpus, axis=1)

    # Mapeos Arquetípicos Binarios en Español
    archetypes = {
        'is_elegant': ['iris', 'cuero', 'sandalo', 'ambar', 'rosa', 'vetiver'],
        'is_clean': ['almizcle', 'almizcle_blanco', 'lavanda', 'aldehido', 'neroli', 'bergamota'],
        'is_leadership_boss': ['tabaco', 'oud', 'cedro', 'cuero', 'incienso'],
        'is_seductive': ['vainilla', 'habatonka', 'haba_tonka', 'ambar', 'canela', 'praline'],
        'is_fresh_casual': ['limon', 'citricos', 'menta', 'notas_acuaticas', 'manzana']
    }
    for arch, kws in archetypes.items():
        df[arch] = df['notes_corpus_weighted'].apply(lambda c: int(any(k in c for k in kws)))

    # 5. Extracción de Métricas de Engagement
    def parse_count(val) -> float:
        if isinstance(val, (int, float)): return float(val)
        if isinstance(val, str):
            val = val.lower().replace('"', '').strip()
            if 'k' in val: return float(val.replace('k', '')) * 1000
            try: return float(val)
            except ValueError: return 0.0
        return 0.0

    def extract_metrics(row):
        vibes = parse_dict(row.get('vibe_reactions_raw_dist'))
        seasons = parse_dict(row.get('seasons_raw_dist'))
        tod = parse_dict(row.get('time_of_day_raw_dist'))

        # 1. Sentimientos en español (pueden venir con o sin mayúsculas/acentos)
        # Buscamos de forma flexible mapeando las claves comunes en español
        love = parse_count(vibes.get('me encanta', vibes.get('love', 0)))
        like = parse_count(vibes.get('me gusta', vibes.get('like', 0)))
        ok = parse_count(vibes.get('me es indiferente', vibes.get('indiferente', vibes.get('ok', 0))))
        dislike = parse_count(vibes.get('no me gusta', vibes.get('dislike', 0)))
        hate = parse_count(vibes.get('la odio', vibes.get('odio', vibes.get('hate', 0))))
        
        tot = love + like + ok + dislike + hate
        pos, neg = love + like, dislike + hate

        # 2. Estaciones en español
        # Si seasons es un dict de español, p. ej. {"invierno": "1.2k", "primavera": "500", ...}
        parsed_seasons = {k.lower(): parse_count(v) for k, v in seasons.items()}
        best_s = max(parsed_seasons, key=parsed_seasons.get) if parsed_seasons else 'versatile'

        # 3. Momento del día en español (día / noche)
        day = parse_count(tod.get('día', tod.get('dia', tod.get('day', 0))))
        night = parse_count(tod.get('noche', tod.get('night', 0)))

        return pd.Series({
            'total_votes': tot,
            'satisfaction_rate': (pos / tot) if tot > 0 else 0.5,
            'controversy_index': (neg / tot) if tot > 0 else 0.0,
            'best_season': best_s,
            'day_ratio': (day / (day + night)) if (day + night) > 0 else 0.5
        })

    metrics_df = df.apply(extract_metrics, axis=1)
    df = pd.concat([df, metrics_df], axis=1)

    # Defaults para normalización si no existen aún
    for col in ['longevity_norm', 'sillage_norm', 'compliments_norm']:
        if col not in df.columns:
            df[col] = 0.5

    # 6. TF-IDF, StandardScaler y Reducción SVD
    num_cols = [
        'longevity_norm', 'sillage_norm', 'compliments_norm',
        'day_ratio', 'satisfaction_rate', 'controversy_index',
        'is_elegant', 'is_clean', 'is_leadership_boss', 'is_seductive', 'is_fresh_casual'
    ]
    df[num_cols] = df[num_cols].fillna(0)

    tfidf = TfidfVectorizer(min_df=1, token_pattern=r'(?u)\b\w+\b')
    tfidf_mat = tfidf.fit_transform(df['notes_corpus_weighted'])

    scaler = StandardScaler()
    num_scaled = scaler.fit_transform(df[num_cols])

    X_comb = hstack([tfidf_mat, num_scaled]).tocsr()
    
    n_comp = min(15, max(1, X_comb.shape[0] - 1))
    svd = TruncatedSVD(n_components=n_comp, random_state=42)
    X_embed = svd.fit_transform(X_comb)

    # 7. Clustering KMeans
    n_clusters = min(9, len(df))
    kmeans = KMeans(n_clusters=6, random_state=42, n_init=10)
    df['olfactory_cluster'] = kmeans.fit_predict(X_embed)

    profile_map = {
        0: "Bruma Casual & Sombra Íntima",
        1: "Nocturno Urbano & Aceptación Versátil",
        2: "Nicho Polarizante & Amaderado Audaz",
        3: "Mass-Pleaser & Apuesta Segura",
        4: "Fresco Diurno & Estilo Oficina",
        5: "Seductor & Imán de Cumplidos",
        6: "Gourmand Cálido & Calidez Personal",
        7: "Estela Potente & Presencia Impuesta",
        8: "Larga Duración & Alta Fijación"
    }
    df['olfactory_profile_label'] = df['olfactory_cluster'].map(profile_map)

    artifacts = {
        'tfidf_vectorizer': tfidf,
        'scaler': scaler,
        'svd': svd,
        'kmeans_model': kmeans,
        'profile_map': profile_map,
        'num_cols': num_cols
    }

    return df, X_embed, artifacts

# ==============================================================================
# EJECUCIÓN PRINCIPAL
# ==============================================================================
if __name__ == "__main__":
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../modelos'))
    
    # 1. Cargar desde la base de datos PostgreSQL
    df_db = load_fragrances_from_db()

    # 2. Guardar Snapshot en CSV
    save_data_snapshot(df_db, data_dir)

    # 3. Ejecutar Pipeline
    print("⚙️ Ejecutando Pipeline de Ingeniería de Variables y Clustering...")
    df_master, X_embedding, artifacts = run_feature_engineering_pipeline(df_db)

    # 4. Guardar artefactos entrenados (.pkl / .parquet)
    models_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../modelos'))
    os.makedirs(models_dir, exist_ok=True)

    artifacts_path = os.path.join(models_dir, "profiling_artifacts.pkl")
    embedding_path = os.path.join(models_dir, "X_embedding.npy")
    master_parquet_path = os.path.join(data_dir, "df_master.parquet")

    with open(artifacts_path, "wb") as f:
        pickle.dump(artifacts, f)

    np.save(embedding_path, X_embedding)
    
    # Convertir columnas complejas a JSON string para guardar en Parquet limpiamente
    df_to_save = df_master.copy()
    for col in df_to_save.columns:
        if df_to_save[col].apply(lambda x: isinstance(x, (dict, list))).any():
            df_to_save[col] = df_to_save[col].apply(lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, (dict, list)) else x)

    df_to_save.to_parquet(master_parquet_path, index=False)

    print("\n🎉 Entrenamiento finalizado con éxito:")
    print(f"  - Dataset featurizado: {master_parquet_path}")
    print(f"  - Artefactos ML (.pkl): {artifacts_path}")
    print(f"  - Matriz Embeddings (.npy): {embedding_path}")