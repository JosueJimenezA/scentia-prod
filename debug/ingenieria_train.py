"""
Pipeline de Consolidación y Profiling de Fragancias
=================================================
Este script realiza la extracción desde PostgreSQL, procesamiento de datos, 
ingeniería de características, análisis léxico-bayesiano de reseñas, 
vectorización TF-IDF, reducción de dimensionalidad (SVD) y clustering (K-Means).

Archivos de salida generados:
  - df_master.parquet
  - profiling_artifacts.pkl
  - X_embeddings.npy
"""

import os
import sys
import re
import json
import ast
import pickle
from datetime import datetime

import numpy as np
import pandas as pd
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from sklearn.decomposition import TruncatedSVD
from sklearn.cluster import KMeans


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../scentia-backend')))

from app.database import SessionLocal
from app.models import Fragrance
from app.limpieza import parse_notes_list_clean, parse_dict
# -----------------------------------------------------------------------------
# 1. CARGA DE DATOS Y SNAPSHOT
# -----------------------------------------------------------------------------
def load_fragrances_from_db() -> pd.DataFrame:
    """Consulta la tabla 'fragrances' en PostgreSQL y la convierte en DataFrame."""
    if SessionLocal is None:
        raise ImportError("No se pudo importar 'SessionLocal' ni 'Fragrance'. Ajusta la ruta de importación de tu ORM.")

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
                'perfume_id': str(f.id),
                'url': getattr(f, 'fragrantica_url', ''),
                'bottle_image_url': getattr(f, 'bottle_image_url', ''),
                'name_raw': getattr(f, 'name', ''),
                'designer_raw': getattr(f, 'designer', ''),
                'global_rating': float(f.global_rating) if getattr(f, 'global_rating', None) is not None else 0.0,
                'global_rating_count': getattr(f, 'global_rating_count', 0),
                'top_notes_raw': getattr(f, 'top_notes', ''),
                'heart_notes_raw': getattr(f, 'heart_notes', ''),
                'base_notes_raw': getattr(f, 'base_notes', ''),
                'perfumers_raw': getattr(f, 'perfumers', ''),
                'seasons_raw_dist': getattr(f, 'seasons_dist', ''),
                'time_of_day_raw_dist': getattr(f, 'time_of_day_dist', ''),
                'longevity_raw_dist': getattr(f, 'longevity_dist', ''),
                'sillage_raw_dist': getattr(f, 'sillage_dist', ''),
                'price_value_raw_dist': getattr(f, 'price_value_dist', ''),
                'gender_voted_raw_dist': getattr(f, 'gender_voted_dist', ''),
                'vibe_reactions_raw_dist': getattr(f, 'vibe_reactions_dist', ''),
                'reviews_text_corpus': getattr(f, 'reviews_corpus', '')
            })
            
        df = pd.DataFrame(data)
        print(f"✅ Se cargaron {len(df)} registros desde la base de datos.")
        return df
    finally:
        db.close()


def save_data_snapshot(df: pd.DataFrame, output_dir: str = "./snapshots"):
    """Guarda un CSV de snapshot para auditoría del dataset utilizado en el entrenamiento."""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_filename = f"training_snapshot_fragrances_{timestamp}.csv"
    snapshot_path = os.path.join(output_dir, snapshot_filename)
    latest_path = os.path.join(output_dir, "training_snapshot_fragrances_latest.csv")
    
    df.to_csv(snapshot_path, index=False, encoding='utf-8-sig')
    df.to_csv(latest_path, index=False, encoding='utf-8-sig')
    print(f"💾 Snapshot de entrenamiento guardado en:\n  - {snapshot_path}\n  - {latest_path}")


# -----------------------------------------------------------------------------
# 2. SEPARACIÓN Y LIMPIEZA DE DISTRIBUCIONES
# -----------------------------------------------------------------------------
SEASONS_KEYS = {"invierno", "primaverda", "verano", "otoño", "oto\u00f1o"}
TIME_OF_DAY_KEYS = {"noche", "dia", "d\u00eda"}
LONGEVITY_KEYS = {"escasa", "débil", "dÉbil", "d\u00e9bil", "duradera", "muy duradera"} 
SILLAGE_KEYS = {"suave", "pesada", "enorme"}
GENDER_KEYS = {"femenino", "unisex femenino", "unisex", "unisex masculino", "masculino"}
PRICE_KEYS = {
    "extremadamente costoso", 
    "ligeramente costoso", 
    "precio moderado", 
    "buen precio", 
    "excelente precio"
}


def parse_dict(val):
    """Convierte cadenas JSON o diccionarios string a dicts de Python de forma segura."""
    if pd.isna(val) or val is None:
        return {}
    if isinstance(val, dict):
        return val
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        try:
            return ast.literal_eval(val)
        except Exception:
            return {}


def separate_distributions(row):
    """Separa las distribuciones combinadas en sus campos correspondientes de forma independiente."""
    # Parsear cada diccionario individualmente para evitar que una columna tape a otra
    seasons_dict = parse_dict(row.get('seasons_raw_dist'))
    tod_dict = parse_dict(row.get('time_of_day_raw_dist'))
    long_dict = parse_dict(row.get('longevity_raw_dist'))
    sill_dict = parse_dict(row.get('sillage_raw_dist'))
    price_dict = parse_dict(row.get('price_value_raw_dist'))
    gender_dict = parse_dict(row.get('gender_voted_raw_dist'))

    # Si vienen combinados en una sola columna por discrepancia del scraper, combinamos los dicts:
    seasons_day_combined = {**seasons_dict, **tod_dict}
    long_sill_combined = {**long_dict, **sill_dict}
    gen_price_combined = {**gender_dict, **price_dict}

    # 1. Temporada vs Momento del Día
    seasons_clean, time_of_day_clean = {}, {}
    for k, v in seasons_day_combined.items():
        k_lower = k.lower().strip()
        if k_lower in SEASONS_KEYS:
            seasons_clean[k] = v
        elif k_lower in TIME_OF_DAY_KEYS:
            time_of_day_clean[k] = v

    # 2. Longevidad vs Estela
    longevity_clean, sillage_clean = {}, {}
    for k, v in long_sill_combined.items():
        k_lower = k.lower().strip()
        if k_lower in LONGEVITY_KEYS:
            longevity_clean[k] = v
        elif k_lower in SILLAGE_KEYS:
            sillage_clean[k] = v
        elif k_lower == "moderada":
            longevity_clean[k] = v
            sillage_clean[k] = v

    # 3. Género vs Precio
    gender_clean, price_clean = {}, {}
    for k, v in gen_price_combined.items():
        k_lower = k.lower().strip()
        if k_lower in GENDER_KEYS:
            gender_clean[k] = v
        elif k_lower in PRICE_KEYS:
            price_clean[k] = v

    return pd.Series({
        'seasons_fixed_dist': json.dumps(seasons_clean, ensure_ascii=False),
        'time_of_day_fixed_dist': json.dumps(time_of_day_clean, ensure_ascii=False),
        'longevity_fixed_dist': json.dumps(longevity_clean, ensure_ascii=False),
        'sillage_fixed_dist': json.dumps(sillage_clean, ensure_ascii=False),
        'gender_fixed_dist': json.dumps(gender_clean, ensure_ascii=False),
        'price_value_fixed_dist': json.dumps(price_clean, ensure_ascii=False)
    })


# -----------------------------------------------------------------------------
# 3. PROCESAMIENTO DE NOTAS Y CORPUS OLFATIVO
# -----------------------------------------------------------------------------
def parse_any_notes_to_list(val) -> list:
    """Convierte cadenas/listas de notas en una lista limpia de strings."""
    if isinstance(val, list):
        return [str(x).strip() for x in val if x]
    if pd.isna(val) or not val or val == 'nan':
        return []
    if isinstance(val, str):
        val_str = val.strip()
        if val_str.startswith('[') and val_str.endswith(']'):
            try:
                parsed = ast.literal_eval(val_str)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if x]
            except Exception:
                pass
        cleaned = re.sub(r"[\[\]'\"']", "", val_str)
        return [x.strip() for x in re.split(r'[,|/]', cleaned) if x.strip()]
    return []


def clean_note_text(note: str) -> str:
    """Limpia caracteres especiales y estandariza minúsculas."""
    note = str(note).lower().strip()
    note = re.sub(r'[^a-z0-9\s_]', '', note)
    return note.replace(' ', '_')


def create_weighted_corpus_from_raw(row):
    """Ponderación olfativa: 3x Fondo, 2x Corazón, 1x Salida sobre columnas _raw."""
    top = [clean_note_text(n) for n in parse_any_notes_to_list(row.get('top_notes_raw'))]
    mid = [clean_note_text(n) for n in parse_any_notes_to_list(row.get('heart_notes_raw'))]
    base = [clean_note_text(n) for n in parse_any_notes_to_list(row.get('base_notes_raw'))]
    
    corpus = (top * 1) + (mid * 2) + (base * 3)
    return " ".join(corpus) if corpus else "unknown_note"


# -----------------------------------------------------------------------------
# 4. ARQUETIPOS
# -----------------------------------------------------------------------------
ARCHETYPES = {
    'is_elegant': ['iris', 'cuero', 'sandalo', 'ambar', 'rosa', 'vetiver'],
    'is_clean': ['almizcle', 'almizcle_blanco', 'lavanda', 'aldehido', 'neroli', 'bergamota'],
    'is_leadership_boss': ['tabaco', 'oud', 'cedro', 'cuero', 'incienso'],
    'is_seductive': ['vainilla', 'habatonka', 'haba_tonka', 'ambar', 'canela', 'praline'],
    'is_fresh_casual': ['limon', 'citricos', 'menta', 'notas_acuaticas', 'manzana']
}


def parse_count(val) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        val = val.lower().replace('"', '').strip()
        if 'k' in val:
            return float(val.replace('k', '')) * 1000
        try:
            return float(val)
        except ValueError:
            return 0.0
    return 0.0


def process_synthetic_metrics(row):
    try:
        vibes = parse_dict(row.get('vibe_reactions_raw_dist'))
        seasons = parse_dict(row.get('seasons_fixed_dist'))
        tod = parse_dict(row.get('time_of_day_fixed_dist'))
    except Exception:
        vibes, seasons, tod = {}, {}, {}

    love = parse_count(vibes.get('me encanta', 0))
    like = parse_count(vibes.get('me gusta', 0))
    ok = parse_count(vibes.get('me es indiferente', 0))
    dislike = parse_count(vibes.get('no me gusta', 0))
    hate = parse_count(vibes.get('la odio', 0))
    
    total_votes = love + like + ok + dislike + hate
    positives = love + like
    negatives = dislike + hate
    
    satisfaction_rate = (positives / total_votes) if total_votes > 0 else 0.5
    controversy_index = (negatives / total_votes) if total_votes > 0 else 0.0
    
    parsed_seasons = {k: parse_count(v) for k, v in seasons.items()}
    best_season = max(parsed_seasons, key=parsed_seasons.get) if parsed_seasons else 'versatile'
    
    day = parse_count(tod.get('día', 0) or tod.get('dia', 0))
    night = parse_count(tod.get('noche', 0))
    day_ratio = day / (day + night) if (day + night) > 0 else 0.5

    return pd.Series({
        'total_votes': total_votes,
        'satisfaction_rate': satisfaction_rate,
        'controversy_index': controversy_index,
        'best_season': best_season,
        'day_ratio': day_ratio
    })


# -----------------------------------------------------------------------------
# 5. EXTRACCIÓN DE ASPECTOS Y PROMEDIO BAYESIANO POR RESEÑA
# -----------------------------------------------------------------------------
ASPECT_LEXICON_ES = {
    'longevity': {
        'keywords': [
            'duracion', 'durabilidad', 'dura', 'durar', 'fijacion', 'fija', 
            'longevidad', 'horas', 'longevo', 'desempeno', 'performance', 'pellejo'
        ],
        'positives': [
            'excelente', 'bestia', 'barbaridad', 'eterna', 'mucho', 'increible', 
            'buena', '10/10', 'mucha', 'eterno', 'duradero', 'todo el dia', 'sobrado'
        ],
        'negatives': [
            'nada', 'poco', 'debil', 'pobre', 'mala', 'desaparece', 'suspiro', 
            'escasa', 'cero', 'agua', 'mediocre', 'efimero', 'no se siente'
        ]
    },
    'sillage': {
        'keywords': [
            'estela', 'proyeccion', 'proyecta', 'alcance', 'proyectar', 'presencia',
            'se siente', 'distancia', 'estelar'
        ],
        'positives': [
            'enorme', 'pesada', 'potente', 'llena', 'habitacion', 'mucha', 'fuerte', 
            'monstruosa', 'bestial', 'marcada', 'pesado', 'notable'
        ],
        'negatives': [
            'pobre', 'intima', 'baja', 'cerca', 'piel', 'suave', 'nula', 'inexistente',
            'ras de piel', 'timida', 'debil'
        ]
    },
    'compliments': {
        'keywords': [
            'cumplido', 'cumplidos', 'halago', 'halagos', 'elogio', 'elogios', 
            'chulearon', 'preguntaron', 'preguntan', 'gusta a todos', 'encanta a', 
            'llamo la atencion', 'me dijeron', 'te dicen', 'atractivo', 'sexy', 'reacciones'
        ],
        'positives': [
            'muchos', 'siempre', 'reacciones', 'asegurados', 'chulean', 'voltear', 
            'cabezas', 'llueven', 'garantizados', 'increible', 'encanta', 'fascinados'
        ],
        'negatives': [
            'ninguno', 'nadie', 'cero', 'sin', 'ningun', 'feo', 'disgusto', 'desagrada'
        ]
    }
}

COMPILED_PATTERNS = {}
for aspect, lexicon in ASPECT_LEXICON_ES.items():
    COMPILED_PATTERNS[aspect] = {
        'kw': re.compile(r'\b(' + '|'.join(lexicon['keywords']) + r')\b', re.IGNORECASE),
        'pos': re.compile(r'\b(' + '|'.join(lexicon['positives']) + r')\b', re.IGNORECASE),
        'neg': re.compile(r'\b(' + '|'.join(lexicon['negatives']) + r')\b', re.IGNORECASE)
    }


def process_reviews_expanded(df: pd.DataFrame, text_column: str = 'reviews_text_corpus') -> pd.DataFrame:
    """Extrae scores por reseña usando asignación inteligente de NaNs."""
    cleaned_series = (
        df[text_column]
        .astype(str)
        .str.lower()
        .str.replace(r'[áàäâ]', 'a', regex=True)
        .str.replace(r'[éèëê]', 'e', regex=True)
        .str.replace(r'[íìïî]', 'i', regex=True)
        .str.replace(r'[óòöô]', 'o', regex=True)
        .str.replace(r'[úùüû]', 'u', regex=True)
    )

    results = pd.DataFrame(index=df.index)

    COMPILED_PATTERNS = {}
    for aspect, lexicon in ASPECT_LEXICON_ES.items():
        COMPILED_PATTERNS[aspect] = {
            # Se agrega '?:' dentro de los paréntesis para evitar que Pandas detecte grupos de captura
            'kw': re.compile(r'\b(?:' + '|'.join(lexicon['keywords']) + r')\b', re.IGNORECASE),
            'pos': re.compile(r'\b(?:' + '|'.join(lexicon['positives']) + r')\b', re.IGNORECASE),
            'neg': re.compile(r'\b(?:' + '|'.join(lexicon['negatives']) + r')\b', re.IGNORECASE)
        }

    # 2. Tu ciclo 'for' dentro de process_reviews_expanded
    for aspect, patterns in COMPILED_PATTERNS.items():
        # regex=True procesará las expresiones regulares de forma nativa sin warnings
        has_aspect = cleaned_series.str.contains(patterns['kw'], regex=True)

        pos_counts = cleaned_series.str.findall(patterns['pos']).str.len()
        neg_counts = cleaned_series.str.findall(patterns['neg']).str.len()
        total_modifiers = pos_counts + neg_counts

        score = np.where(
            ~has_aspect,
            np.nan,
            np.where(
                total_modifiers > 0,
                (pos_counts - neg_counts) / total_modifiers,
                0.1
            )
        )

        results[f'{aspect}_score'] = np.round(score, 2)

    return results


def calculate_bayesian_perfume_scores(reviews_df: pd.DataFrame, aspect_scores_df: pd.DataFrame, min_mencions_weight: int = 3) -> pd.DataFrame:
    """Agrupa por perfume y calcula un Promedio Bayesiano para suavizar la distribución."""
    df_combined = pd.concat([reviews_df[['perfume_id']], aspect_scores_df], axis=1)
    perfume_metrics = {}
    
    for aspect in ['longevity_score', 'sillage_score', 'compliments_score']:
        global_mean = df_combined[aspect].mean()
        if pd.isna(global_mean):
            global_mean = 0.0

        grouped = df_combined.groupby('perfume_id')[aspect].agg(['count', 'mean']).reset_index()

        n = grouped['count']
        mean = grouped['mean'].fillna(global_mean)
        m = min_mencions_weight

        bayesian_score = (n * mean + m * global_mean) / (n + m)
        grouped[f'{aspect}_bayesian'] = np.round(bayesian_score, 3)

        perfume_metrics[aspect] = grouped[['perfume_id', f'{aspect}_bayesian']]

    final_perfume_df = perfume_metrics['longevity_score']
    final_perfume_df = final_perfume_df.merge(perfume_metrics['sillage_score'], on='perfume_id')
    final_perfume_df = final_perfume_df.merge(perfume_metrics['compliments_score'], on='perfume_id')

    return final_perfume_df


# -----------------------------------------------------------------------------
# 6. PIPELINE PRINCIPAL DE EJECUCIÓN
# -----------------------------------------------------------------------------
def run_pipeline():
    print("🚀 Iniciando el Pipeline de Fragancias...")

    # 1. Cargar datos desde PostgreSQL
    df_raw = load_fragrances_from_db()
    save_data_snapshot(df_raw)

    # 2. Separar distribuciones
    dist_df = df_raw.apply(separate_distributions, axis=1)
    df_fixed = df_raw.copy()
    for col in dist_df.columns:
        df_fixed[col] = dist_df[col]

    df_fixed.drop(columns=['accords_query_string', 'perfumers_raw'], inplace=True, errors='ignore')

    # Tratar notas faltantes y nulos
    note_cols = ['top_notes_raw', 'heart_notes_raw', 'base_notes_raw']
    for col in note_cols:
        df_fixed[col] = df_fixed[col].fillna('Sin notas declaradas')

    df_fixed['global_rating'] = df_fixed['global_rating'].fillna(0.0)
    df_fixed['global_rating_count'] = df_fixed['global_rating_count'].fillna(0)

    # 3. Arquetipos
    df_fixed['notes_corpus_weighted'] = df_fixed.apply(create_weighted_corpus_from_raw, axis=1)
    for archetype, keywords in ARCHETYPES.items():
        df_fixed[archetype] = df_fixed['notes_corpus_weighted'].apply(
            lambda corpus: int(any(kw in corpus for kw in keywords))
        )

    # 4. Métricas sintéticas
    synthetic_feats = df_fixed.apply(process_synthetic_metrics, axis=1)
    df_fixed = pd.concat([df_fixed, synthetic_feats], axis=1)

    # 5. Análisis Bayesiano de Reseñas
    reviews_demo = df_fixed[['perfume_id', 'reviews_text_corpus']].copy()
    aspect_scores = process_reviews_expanded(reviews_demo, text_column='reviews_text_corpus')
    perfume_performance_df = calculate_bayesian_perfume_scores(reviews_demo, aspect_scores)

    scaler_minmax = MinMaxScaler()
    perfume_performance_df[['longevity_norm', 'sillage_norm', 'compliments_norm']] = scaler_minmax.fit_transform(
        perfume_performance_df[['longevity_score_bayesian', 'sillage_score_bayesian', 'compliments_score_bayesian']]
    )

    # Unir a DataFrame maestro
    df_master = df_fixed.merge(perfume_performance_df, on='perfume_id', how='left')
    df_master['notes_corpus_weighted'] = df_master.apply(create_weighted_corpus_from_raw, axis=1)

    # 6. Vectorización TF-IDF y SVD
    tfidf = TfidfVectorizer(min_df=1, token_pattern=r'(?u)\b\w+\b')
    tfidf_matrix = tfidf.fit_transform(df_master['notes_corpus_weighted'])

    num_cols = [
        'longevity_norm', 'sillage_norm', 'compliments_norm',
        'day_ratio', 'satisfaction_rate', 'controversy_index',
        'is_elegant', 'is_clean', 'is_leadership_boss', 'is_seductive', 'is_fresh_casual'
    ]

    df_master[num_cols] = df_master[num_cols].fillna(0)

    scaler_std = StandardScaler()
    X_numeric_scaled = scaler_std.fit_transform(df_master[num_cols])

    X_combined = hstack([tfidf_matrix, X_numeric_scaled]).tocsr()

    n_samples, n_features = X_combined.shape
    n_comp = min(15, min(n_samples, n_features) - 1) if min(n_samples, n_features) > 1 else 1

    svd = TruncatedSVD(n_components=n_comp, random_state=42)
    X_embedding = svd.fit_transform(X_combined)

    # 7. Clustering K-Means
    k_optimal = min(6, n_samples)
    kmeans_model = KMeans(n_clusters=k_optimal, random_state=42, n_init=10)
    df_master['olfactory_cluster'] = kmeans_model.fit_predict(X_embedding)
    df_master['distance_to_cluster_center'] = kmeans_model.transform(X_embedding).min(axis=1)

    olfactory_profile_map = {
        0: "Oriental / gourmand",
        1: "Amaderado fresco e Informal",
        2: "Limpio y atalcado",
        3: "Nicho / Retador",
        4: "Dulce Nocturno / Versátil Elegante",
        5: "Cuero Amaderado de Autoridad"
    }

    df_master['olfactory_profile_label'] = df_master['olfactory_cluster'].map(olfactory_profile_map)

    # 8. Guardar Artefactos Requeridos
    print("💾 Guardando artefactos...")

    # a) df_master en formato Parquet

    # ==============================================================================
    # LIMPIEZA DE COLUMNAS PREVIA A GUARDAR EN PARQUET
    # ==============================================================================

    # 1. Lista de columnas crudas/intermedias redundantes que no deben ir en df_master.parquet
    raw_cols_to_drop = [
        'id',  # Ya existe perfume_id
        'top_notes_raw', 'heart_notes_raw', 'base_notes_raw', 'perfumers_raw',
        'seasons_raw_dist', 'time_of_day_raw_dist', 'longevity_raw_dist', 
        'sillage_raw_dist', 'price_value_raw_dist', 'gender_voted_raw_dist', 
        'vibe_reactions_raw_dist'
    ]

    df_master.drop(columns=raw_cols_to_drop, inplace=True, errors='ignore')

    # 2. Asegurar que las columnas JSON limpias sean strings puros y no diccionarios
    json_cols = [
        'seasons_fixed_dist', 'time_of_day_fixed_dist', 'longevity_fixed_dist',
        'sillage_fixed_dist', 'gender_fixed_dist', 'price_value_fixed_dist'
    ]

    for col in json_cols:
        if col in df_master.columns:
            df_master[col] = df_master[col].apply(
                lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, dict) else str(x or "{}")
            )

    # 3. Guardar el archivo Parquet limpio
    parquet_path = "df_master.parquet"
    df_master.to_parquet(parquet_path, index=False)
    print(f"✅ 'df_master.parquet' guardado correctamente sin subcolumnas anidadas ({len(df_master.columns)} columnas totales).")


    # b) X_embeddings.npy
    embedding_path = "X_embeddings.npy"
    np.save(embedding_path, X_embedding)
    print(f"  - Matriz de Embeddings guardada en: {embedding_path}")

    # c) profiling_artifacts.pkl
    artifacts = {
        'tfidf_vectorizer': tfidf,
        'standard_scaler': scaler_std,
        'minmax_scaler': scaler_minmax,
        'svd_model': svd,
        'kmeans_model': kmeans_model,
        'olfactory_profile_map': olfactory_profile_map,
        'archetypes': ARCHETYPES,
        'num_cols': num_cols
    }
    artifacts_path = "profiling_artifacts.pkl"
    with open(artifacts_path, 'wb') as f:
        pickle.dump(artifacts, f)
    print(f"  - Artefactos del modelo guardados en: {artifacts_path}")

    print("🎉 Pipeline finalizado exitosamente.")


if __name__ == "__main__":
    run_pipeline()