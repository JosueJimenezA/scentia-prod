import pickle
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple, Optional
from sklearn.metrics.pairwise import cosine_similarity
from scipy.sparse import hstack
from sqlalchemy.orm import Session
from pathlib import Path

from app.models import Fragrance, UserCollection
from app.limpieza import parse_notes_list_clean, parse_dict

BASE_DIR = Path(__file__).resolve().parents[2] 
MODELOS_DIR = BASE_DIR / "modelos"

class InferenceEngine_v2:
    """
    Motor Singleton que mantiene en memoria los artefactos ML
    y realiza cálculos de vectores, clusters y recomendaciones.
    Soporta inferencia *on-the-fly* para fragancias fuera del dataset de entrenamiento.
    """

    def __init__(
        self,
        master_path: str = str(MODELOS_DIR / "df_master_prueba.parquet"),
        artifacts_path: str = str(MODELOS_DIR / "profiling_artifacts_prueba.pkl"),
        embeddings_path: str = str(MODELOS_DIR / "X_embeddings_prueba.npy")  # Actualizado nombre de archivo a X_embeddings.npy
    ):
        print("[InferenceEngine] Cargando artefactos de ML en memoria...")
        
        # 1. Dataset Master
        self.df_master = pd.read_parquet(master_path)
        
        # AJUSTE 1: Mapeo usando 'perfume_id' en lugar de 'id'
        if "perfume_id" in self.df_master.columns:
            self.df_master["id_str"] = self.df_master["perfume_id"].astype(str)
        elif "id" in self.df_master.columns:
            self.df_master["id_str"] = self.df_master["id"].astype(str)

        # 2. Matriz de Embeddings precalculada
        self.X_embedding = np.load(embeddings_path)

        # 3. Artefactos ML (vectorizadores, escaladores, SVD, etc.)
        with open(artifacts_path, "rb") as f:
            self.artifacts = pickle.load(f)

        # AJUSTE 2: Mapeo con los nombres exactos del nuevo profiling_artifacts.pkl
        self.tfidf = self.artifacts.get('tfidf_vectorizer')
        self.minmax_scaler = self.artifacts.get('minmax_scaler')
        self.standard_scaler = self.artifacts.get('standard_scaler')
        self.svd = self.artifacts.get('svd_model')
        self.kmeans = self.artifacts.get('kmeans_model')
        self.olfactory_profile_map = self.artifacts.get('olfactory_profile_map', {})
        self.archetypes = self.artifacts.get('archetypes', {})
        
        self.num_cols = self.artifacts.get('num_cols', [
            'longevity_norm', 'sillage_norm', 'compliments_norm',
            'day_ratio', 'satisfaction_rate', 'controversy_index',
            'is_elegant', 'is_clean', 'is_leadership_boss', 'is_seductive', 'is_fresh_casual'
        ])

        # Mapeo rápido UUID (str) -> Índice en matriz de embeddings
        df_master_ids = self.df_master["id_str"].tolist()
        self.id_to_index = {str(fid): idx for idx, fid in enumerate(df_master_ids)}

        print(f"[InferenceEngine] Listo. Total fragancias master: {len(self.df_master)}")

    def _transform_fragrance_on_the_fly(self, frag: Fragrance) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Transforma una fragancia desconocida (no presente en el Parquet)
        al espacio vectorial reducido (SVD) en tiempo real y retorna los pesos intermedios.
        """
        def clean_val(v):
            if isinstance(v, (list, tuple)):
                return ", ".join([str(x) for x in v])
            return str(v) if v else ""

        # 1. Construir Corpus Olfativo Ponderado
        top = parse_notes_list_clean(clean_val(frag.top_notes))
        mid = parse_notes_list_clean(clean_val(frag.heart_notes))
        base = parse_notes_list_clean(clean_val(frag.base_notes))
        
        corpus = (top * 1) + (mid * 2) + (base * 3)
        weighted_corpus = " ".join(corpus) if corpus else "unknown_note"

        # 2. Arquetipos Binarios
        archetypes = self.archetypes or {
            'is_elegant': ['iris', 'cuero', 'sandalo', 'ambar', 'rosa', 'vetiver'],
            'is_clean': ['almizcle', 'almizcle_blanco', 'lavanda', 'aldehido', 'neroli', 'bergamota'],
            'is_leadership_boss': ['tabaco', 'oud', 'cedro', 'cuero', 'incienso'],
            'is_seductive': ['vainilla', 'habatonka', 'haba_tonka', 'ambar', 'canela', 'praline'],
            'is_fresh_casual': ['limon', 'citricos', 'menta', 'notas_acuaticas', 'manzana']
        }
        
        # Métrica de performance base para normalizar
        perf_base = np.array([[0.0, 0.0, 0.0]]) # longevity, sillage, compliments iniciales
        if self.minmax_scaler:
            perf_norm = self.minmax_scaler.transform(perf_base)[0]
        else:
            perf_norm = [0.5, 0.5, 0.5]

        num_dict = {
            'longevity_norm': perf_norm[0],
            'sillage_norm': perf_norm[1],
            'compliments_norm': perf_norm[2],
            'day_ratio': 0.5,
            'satisfaction_rate': 0.5,
            'controversy_index': 0.0
        }

        active_archetypes = {}
        for arch, kws in archetypes.items():
            is_active = any(k in weighted_corpus for k in kws)
            num_dict[arch] = 1.0 if is_active else 0.0
            active_archetypes[arch] = 1.0 if is_active else 0.0

        # Crear array numérico respetando el orden exacto de `num_cols`
        num_vector = np.array([[num_dict.get(col, 0.0) for col in self.num_cols]])

        # 3. Transformación usando los Artefactos ML
        tfidf_vec = self.tfidf.transform([weighted_corpus])
        
        # AJUSTE 3: Escalado estandarizado correcto
        num_scaled = self.standard_scaler.transform(num_vector)

        # Extraer términos TF-IDF con mayor peso
        feature_names = np.array(self.tfidf.get_feature_names_out())
        nonzero_indices = tfidf_vec.nonzero()[1]
        tfidf_weights = {feature_names[i]: round(float(tfidf_vec[0, i]), 4) for i in nonzero_indices}

        # Combinar Sparse Matrix
        X_comb = hstack([tfidf_vec, num_scaled]).tocsr()

        # Proyectar en el espacio SVD
        embedding_vec = self.svd.transform(X_comb)[0]

        weights_info = {
            "weighted_corpus": weighted_corpus,
            "top_tfidf_words": tfidf_weights,
            "active_archetypes": active_archetypes,
            "numeric_scaled_vector": [round(float(v), 4) for v in num_scaled[0]],
            "svd_embedding_components": [round(float(v), 4) for v in embedding_vec]
        }

        return embedding_vec, weights_info

    def get_user_fragrances_subsample(self, user_id: str, db: Session) -> List[Tuple[Fragrance, float]]:
        """Obtiene las fragancias 'owned' del usuario y su calificación."""
        results = (
            db.query(Fragrance, UserCollection.user_rating)
            .join(UserCollection, Fragrance.id == UserCollection.fragrance_id)
            .filter(
                UserCollection.user_id == user_id,
                UserCollection.acquisition_status == "owned"
            )
            .all()
        )
        return results

    def analyze_user_vector_and_cluster(
        self, 
        subsample: List[Tuple[Fragrance, float]]
    ) -> Dict[str, Any]:
        """Calcula el vector ponderado del usuario y predice su cluster/perfil."""
        if not subsample:
            return None

        user_vectors = []
        user_weights = []
        collected_ids = []

        for frag, user_rating in subsample:
            frag_id_str = str(frag.id)
            collected_ids.append(frag_id_str)

            weight = float(user_rating) / 5.0 if user_rating else 1.0

            if frag_id_str in self.id_to_index:
                idx = self.id_to_index[frag_id_str]
                vector = self.X_embedding[idx]
            else:
                vector, weights_info = self._transform_fragrance_on_the_fly(frag)
                self.last_onthefly_weights = weights_info

            user_vectors.append(vector)
            user_weights.append(weight)

        if not user_vectors:
            return None

        # Vector promedio ponderado (Centroide)
        user_vectors = np.array(user_vectors)
        user_weights = np.array(user_weights).reshape(-1, 1)
        user_centroid = np.sum(user_vectors * user_weights, axis=0) / np.sum(user_weights)
        user_centroid = user_centroid.reshape(1, -1)

        # Predecir Cluster mediante KMeans
        predicted_cluster = int(self.kmeans.predict(user_centroid)[0])
        
        # AJUSTE 4: Uso del mapa de perfiles olfativos correcto
        predicted_label = self.olfactory_profile_map.get(predicted_cluster, "Firma Olfativa Versátil")

        subsample_df = self.df_master[self.df_master["id_str"].isin(collected_ids)]
        avg_longevity = float(subsample_df["longevity_norm"].mean()) if not subsample_df.empty and "longevity_norm" in subsample_df.columns else 0.80
        avg_sillage = float(subsample_df["sillage_norm"].mean()) if not subsample_df.empty and "sillage_norm" in subsample_df.columns else 0.75

        return {
            "user_centroid": user_centroid,
            "predicted_cluster": predicted_cluster,
            "predicted_label": predicted_label,
            "collected_ids": collected_ids,
            "metrics": {
                "total_owned": len(subsample),
                "avg_longevity_score": round(avg_longevity, 2),
                "avg_sillage_score": round(avg_sillage, 2)
            }
        }

    def generate_recommendations(
        self, 
        user_centroid: np.ndarray, 
        collected_ids: List[str], 
        top_k: int = 8
    ) -> List[Dict[str, Any]]:
        """Calcula la similitud coseno y sugiere fragancias fuera de su colección."""
        similarities = cosine_similarity(user_centroid, self.X_embedding)[0]

        df_scored = self.df_master.copy()
        df_scored["similarity_score"] = similarities

        # Excluir poseídas
        df_scored = df_scored[~df_scored["id_str"].isin(collected_ids)]

        top_df = df_scored.sort_values(by="similarity_score", ascending=False).head(top_k)

        recommendations = []
        for _, row in top_df.iterrows():
            recommendations.append({
                "id": str(row["perfume_id"]), # AJUSTE 5: Usa perfume_id
                "name": row.get("name_raw"),
                "designer": row.get("designer_raw"),
                "bottle_image_url": row.get("bottle_image_url"),
                "similarity_score": round(float(row["similarity_score"]), 4),
                "global_rating": float(row.get("global_rating")) if pd.notnull(row.get("global_rating")) else None,
                "olfactory_profile_label": row.get("olfactory_profile_label"),
                "best_season": row.get("best_season")
            })

        return recommendations

    def get_weather_based_recommendations(
        self,
        weather_forecast: dict,
        user_centroid: Optional[np.ndarray] = None,
        user_collection_ids: Optional[List[Any]] = None,
        top_k_collection: int = 3,
        top_k_discovery: int = 3
    ) -> Dict[str, Any]:
        """Calcula recomendaciones ajustando la afinidad climática."""
        temp_max = weather_forecast.get("temp_max", 20.0)
        precip = weather_forecast.get("precipitation_sum", 0.0)

        if temp_max >= 25.0:
            target_season = "verano"
        elif temp_max <= 13.0:
            target_season = "invierno"
        elif 14.0 <= temp_max < 20.0:
            target_season = "otoño"
        else:
            target_season = "primavera"

        df_scored = self.df_master.copy()

        if user_centroid is not None:
            user_centroid = np.asarray(user_centroid)
            if user_centroid.ndim == 1:
                user_centroid = user_centroid.reshape(1, -1)
            
            similarities = cosine_similarity(user_centroid, self.X_embedding)[0]
            df_scored["base_score"] = np.clip(similarities, 0, 1) * 0.70
        else:
            raw_rating = df_scored["global_rating"].fillna(0.0)
            df_scored["base_score"] = (raw_rating / 5.0) * 0.70

        df_scored["similarity_score"] = df_scored["base_score"]

        # Boosts climáticos
        if "best_season" in df_scored.columns:
            season_mask = df_scored["best_season"].str.lower() == target_season
            df_scored.loc[season_mask, "similarity_score"] *= 1.25

        # AJUSTE 6: Búsqueda sobre notes_corpus_weighted en lugar de accords_query_string
        if precip > 5.0 and "notes_corpus_weighted" in df_scored.columns:
            warm_mask = df_scored["notes_corpus_weighted"].str.contains(
                "ambar|canela|vainilla|cuero|tabaco|incienso|cedro|oud", case=False, na=False
            )
            df_scored.loc[warm_mask, "similarity_score"] *= 1.15

        max_possible_score = 0.70 * 1.25 * 1.15
        df_scored["final_affinity"] = np.clip(df_scored["similarity_score"] / max_possible_score, 0.0, 1.0)

        collection_set = set(str(cid) for cid in user_collection_ids) if user_collection_ids else set()
        
        df_collection = df_scored[df_scored["id_str"].isin(collection_set)]
        df_discovery = df_scored[~df_scored["id_str"].isin(collection_set)]

        def format_results(df_subset, top_k, source_label):
            top_df = df_subset.sort_values(by="final_affinity", ascending=False).head(top_k)
            items = []
            for _, row in top_df.iterrows():
                items.append({
                    "id": str(row["perfume_id"]), # AJUSTE 7: Usa perfume_id
                    "name": row.get("name_raw"),
                    "designer": row.get("designer_raw"),
                    "bottle_image_url": row.get("bottle_image_url"),
                    "family": row.get("olfactory_profile_label", target_season.capitalize()),
                    "recommended_season": target_season,
                    "similarity_score": round(float(row["final_affinity"]), 4),
                    "global_rating": float(row.get("global_rating")) if pd.notnull(row.get("global_rating")) else None,
                    "source": source_label
                })
            return items

        return {
            "collection_recommendations": format_results(df_collection, top_k_collection, "colección"),
            "discovery_recommendations": format_results(df_discovery, top_k_discovery, "descubrimiento")
        }

# Instancia Global Singleton
inference_engine_v2 = InferenceEngine_v2()