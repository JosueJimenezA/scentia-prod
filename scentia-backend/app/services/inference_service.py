import pickle
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session
from pathlib import Path
from typing import Optional

from app.models import Fragrance, UserCollection

BASE_DIR = Path(__file__).resolve().parents[3] 
MODELOS_DIR = BASE_DIR / "modelos"

class InferenceEngine:
    """
    Motor Singleton que mantiene en memoria los artefactos ML
    y realiza cálculos de vectores, clusters y recomendaciones.

    Tambien procesa las recomendaciones basados en geolocalizaciòn, clima y fecha
    """

    def __init__(
        self,
        master_path: str = str(MODELOS_DIR / "df_master.parquet"),
        artifacts_path: str = str(MODELOS_DIR / "profiling_artifacts.pkl"),
        embeddings_path: str = str(MODELOS_DIR / "X_embedding.npy")
    ):
        print("[InferenceEngine] Cargando artefactos de ML en memoria...")
        
        # 1. Dataset Master
        self.df_master = pd.read_parquet(master_path)
        if "id" in self.df_master.columns:
            self.df_master["id_str"] = self.df_master["id"].astype(str)

        # 2. Matriz de Embeddings
        self.X_embedding = np.load(embeddings_path)

        # 3. Artefactos ML
        with open(artifacts_path, "rb") as f:
            self.artifacts = pickle.load(f)

        # Mapeo rápido UUID (str) -> Índice en matriz de embeddings
        df_master_ids = self.df_master["id"].astype(str).tolist()
        self.id_to_index = {str(fid): idx for idx, fid in enumerate(df_master_ids)}

        print(f"[InferenceEngine] Listo. Total fragancias master: {len(self.df_master)}")

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

            # Ponderación basada en calificación (default 1.0)
            weight = float(user_rating) / 5.0 if user_rating else 1.0

            if frag_id_str in self.id_to_index:
                idx = self.id_to_index[frag_id_str]
                user_vectors.append(self.X_embedding[idx])
                user_weights.append(weight)

        if not user_vectors:
            return None

        # Vector promedio ponderado (Centroide del gusto del usuario)
        user_vectors = np.array(user_vectors)
        user_weights = np.array(user_weights).reshape(-1, 1)
        user_centroid = np.sum(user_vectors * user_weights, axis=0) / np.sum(user_weights)
        user_centroid = user_centroid.reshape(1, -1)

        # Obtener Cluster o Etiqueta Predicha
        subsample_df = self.df_master[self.df_master["id_str"].isin(collected_ids)]
        
        predicted_cluster = None
        predicted_label = "Firma Olfativa Versátil"

        if "olfactory_cluster" in subsample_df.columns and not subsample_df["olfactory_cluster"].dropna().empty:
            predicted_cluster = int(subsample_df["olfactory_cluster"].mode()[0])

        if "olfactory_profile_label" in subsample_df.columns and not subsample_df["olfactory_profile_label"].dropna().empty:
            predicted_label = str(subsample_df["olfactory_profile_label"].mode()[0])

        # Métricas agregadas (Longevidad y Proyección promedio de su colección)
        avg_longevity = float(subsample_df["longevity_norm"].mean()) if "longevity_norm" in subsample_df.columns else 0.80
        avg_sillage = float(subsample_df["sillage_norm"].mean()) if "sillage_norm" in subsample_df.columns else 0.75

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

        # Excluir las que el usuario ya posee
        df_scored = df_scored[~df_scored["id_str"].isin(collected_ids)]

        # Top K
        top_df = df_scored.sort_values(by="similarity_score", ascending=False).head(top_k)

        recommendations = []
        for _, row in top_df.iterrows():
            recommendations.append({
                "id": str(row["id"]),
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
        collected_ids: Optional[List[Any]] = None,
        top_k: int = 6
    ) -> List[Dict[str, Any]]:
        """
        Filtra y recomienda fragancias de acuerdo a las variables meteorológicas de Open-Meteo
        (temperatura máxima, precipitación, etc.) y opcionalmente el centroide del usuario.
        """
        temp_max = weather_forecast.get("temp_max", 20.0)
        precip = weather_forecast.get("precipitation_sum", 0.0)

        # 1. Determinar estación / clima objetivo según temperatura
        if temp_max >= 25.0:
            target_season = "verano"
        elif temp_max <= 13.0:
            target_season = "invierno"
        elif 14.0 <= temp_max < 20.0:
            target_season = "otoño"
        else:
            target_season = "primavera"

        df_scored = self.df_master.copy()

        # 2. Excluir la colección del usuario si se proporciona
        if collected_ids:
            collected_ids_str = set(str(cid) for cid in collected_ids)
            df_scored = df_scored[~df_scored["id_str"].isin(collected_ids_str)]

        # 3. Ponderación por similitud de perfil o rating
        if user_centroid is not None:
            user_centroid = np.asarray(user_centroid)
            if user_centroid.ndim == 1:
                user_centroid = user_centroid.reshape(1, -1)
            
            similarities = cosine_similarity(user_centroid, self.X_embedding)[0]
            df_scored["similarity_score"] = similarities
        else:
            # Si el usuario no tiene perfil, usamos el rating global como base
            df_scored["similarity_score"] = df_scored["global_rating"].fillna(0)

        # 4. Bonificación / Filtrado por estación ideal
        if "best_season" in df_scored.columns:
            # Multiplicador para dar preferencia a fragancias de la estación objetivo
            season_mask = df_scored["best_season"].str.lower() == target_season
            df_scored.loc[season_mask, "similarity_score"] *= 1.25

        # 5. Si hay lluvia intensa, bonificar notas más pesadas/cálidas si existen
        if precip > 5.0 and "accords_query_string" in df_scored.columns:
            warm_mask = df_scored["accords_query_string"].str.contains("especiado|amaderado|cálido", case=False, na=False)
            df_scored.loc[warm_mask, "similarity_score"] *= 1.15

        # 6. Seleccionar Top K
        top_df = df_scored.sort_values(by="similarity_score", ascending=False).head(top_k)

        # 7. Dar formato de salida compatible con el Router
        results = []
        for _, row in top_df.iterrows():
            results.append({
                "id": str(row["id"]),
                "name": row.get("name_raw"),
                "designer": row.get("designer_raw"),
                "bottle_image_url": row.get("bottle_image_url"),
                "family": row.get("olfactory_profile_label", target_season.capitalize()),
                "recommended_season": target_season,
                "similarity_score": round(float(row["similarity_score"]), 4),
                "global_rating": float(row.get("global_rating")) if pd.notnull(row.get("global_rating")) else None
            })

        return results


# Instancia Global Singleton
inference_engine = InferenceEngine()