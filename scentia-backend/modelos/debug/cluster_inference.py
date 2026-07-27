import pickle
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session
from sqlalchemy import select
import sys
import os


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../scentia-backend')))

from app.models import Fragrance, UserCollection 



class InferenceEngine:
    """
    Clase que gestiona la inferencia del perfil olfativo/cluster de un usuario
    a partir de la submuestra de sus fragancias en 'user_collections', y calcula
    recomendaciones afines.
    """

    def __init__(
        self,
        master_path: str,
        artifacts_path: str,
        embeddings_path: str
    ):
        print("[InferenceEngine] Cargando artefactos en memoria...")
        # 1. Dataset Featurizado Master
        self.df_master = pd.read_parquet(master_path)
        
        # Indexar por id para búsquedas rápidas (UUID a str)
        if "id" in self.df_master.columns:
            self.df_master["id_str"] = self.df_master["id"].astype(str)
            self.df_master.set_index("id_str", inplace=False)

        # 2. Matriz de Embeddings (Shape: [num_fragancias, dimension_embedding])
        self.X_embedding = np.load(embeddings_path)

        # 3. Artefactos ML (Clustering / Profiling models, escaladores, vectorizadores, etc.)
        with open(artifacts_path, "rb") as f:
            self.artifacts = pickle.load(f)
            
        print("[InferenceEngine] Carga completada exitosamente.")

    def get_user_fragrances_subsample(
        self, 
        user_id: str, 
        db: Session, 
        status: str = "owned"
    ) -> List[Tuple[Fragrance, float]]:
        """
        1. Consulta la BD para obtener la submuestra de fragancias 
        pertenecientes a la colección del usuario con su respectiva calificación/ponderación.
        """
        results = (
            db.query(Fragrance, UserCollection.user_rating)
            .join(UserCollection, Fragrance.id == UserCollection.fragrance_id)
            .filter(
                UserCollection.user_id == user_id,
                UserCollection.acquisition_status == status
            )
            .all()
        )
        return results

    def predict_user_profile_and_cluster(
        self, 
        user_fragrance_subsample: List[Tuple[Fragrance, float]]
    ) -> Dict[str, Any]:
        """
        2. Procesa la submuestra de fragancias de la colección del usuario 
        para predecir su vector promedio, cluster olfativo y perfil.
        """
        if not user_fragrance_subsample:
            return None

        user_vectors = []
        user_weights = []
        collected_ids = []

        # Mapeo rápido de UUIDs a índice en df_master / X_embedding
        df_master_ids = self.df_master["id"].astype(str).tolist()
        id_to_index = {str(fid): idx for idx, fid in enumerate(df_master_ids)}

        for frag, user_rating in user_fragrance_subsample:
            frag_id_str = str(frag.id)
            collected_ids.append(frag_id_str)

            # Ponderación del usuario (1.0 por defecto si no ha calificado)
            weight = float(user_rating) / 5.0 if user_rating else 1.0

            # Intentar obtener el embedding prediseñado desde X_embedding
            if frag_id_str in id_to_index:
                idx = id_to_index[frag_id_str]
                embedding = self.X_embedding[idx]
                user_vectors.append(embedding)
                user_weights.append(weight)

        if not user_vectors:
            return None

        # Matriz ponderada de la submuestra del usuario
        user_vectors = np.array(user_vectors)
        user_weights = np.array(user_weights).reshape(-1, 1)

        # Vector Centroide / Representativo del Usuario (Ponderado)
        user_centroid_vector = np.sum(user_vectors * user_weights, axis=0) / np.sum(user_weights)
        user_centroid_vector = user_centroid_vector.reshape(1, -1)

        # Predicción de Cluster u Olfactory Profile Label
        predicted_cluster = None
        predicted_label = None

        # Si cuentas con un modelo de clustering guardado (ej. K-Means / GMM en artefactos)
        if "kmeans" in self.artifacts or "cluster_model" in self.artifacts:
            cluster_model = self.artifacts.get("kmeans") or self.artifacts.get("cluster_model")
            predicted_cluster = int(cluster_model.predict(user_centroid_vector)[0])
        else:
            # Si no hay modelo de clustering explicito, determinamos el cluster más común
            # en las fragancias de su submuestra
            subsample_df = self.df_master[self.df_master["id"].astype(str).isin(collected_ids)]
            if "olfactory_cluster" in subsample_df.columns:
                predicted_cluster = int(subsample_df["olfactory_cluster"].mode()[0])
            if "olfactory_profile_label" in subsample_df.columns:
                predicted_label = str(subsample_df["olfactory_profile_label"].mode()[0])

        return {
            "user_vector": user_centroid_vector,
            "predicted_cluster": predicted_cluster,
            "predicted_label": predicted_label,
            "collected_ids": collected_ids
        }

    def generate_recommendations(
        self, 
        user_vector: np.ndarray, 
        collected_ids: List[str], 
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        3. Genera las recomendaciones calculando la similitud entre el vector 
        del usuario y la matriz global de fragancias X_embedding.
        """
        # Calcular similitud coseno del vector del usuario contra todo el dataset
        similarities = cosine_similarity(user_vector, self.X_embedding)[0]

        df_scored = self.df_master.copy()
        df_scored["similarity_score"] = similarities

        # Excluir las fragancias que la submuestra del usuario ya incluye
        df_scored = df_scored[~df_scored["id"].astype(str).isin(collected_ids)]

        # Ordenar por similitud y extraer las Top-K
        top_recommendations = df_scored.sort_values(by="similarity_score", ascending=False).head(top_k)

        # Formatear la respuesta
        recommendations = []
        for _, row in top_recommendations.iterrows():
            recommendations.append({
                "id": str(row["id"]),
                "name": row.get("name_raw"),
                "designer": row.get("designer_raw"),
                "bottle_image_url": row.get("bottle_image_url"),
                "similarity_score": round(float(row["similarity_score"]), 4),
                "global_rating": row.get("global_rating"),
                "olfactory_cluster": row.get("olfactory_cluster"),
                "olfactory_profile_label": row.get("olfactory_profile_label")
            })

        return recommendations


# =====================================================================
# Orquestador del Servicio / Endpoint
# =====================================================================

# Inicializar motor globalmente (Singleton)
inference_engine = InferenceEngine(
    master_path="modelos/df_master.parquet",
    artifacts_path="modelos/profiling_artifacts.pkl",
    embeddings_path="modelos/X_embedding.npy"
)


def get_recommendations_and_user_profile(user_id: str, db: Session, top_k: int = 10):
    # 1. Obtener la submuestra de la tabla 'fragrances' asociada a 'user_collections'
    subsample = inference_engine.get_user_fragrances_subsample(user_id=user_id, db=db)

    if not subsample:
        return {
            "status": "empty",
            "message": "El usuario no cuenta con fragancias en su colección para generar el perfil."
        }

    # 2. Pasar la submuestra al módulo de inferencia para determinar el vector/cluster/perfil
    profile_data = inference_engine.predict_user_profile_and_cluster(subsample)

    if not profile_data:
        return {
            "status": "error",
            "message": "No se encontraron concordancias de vectores para la colección del usuario."
        }

    # 3. Obtener recomendaciones basadas en la colección del usuario
    recommendations = inference_engine.generate_recommendations(
        user_vector=profile_data["user_vector"],
        collected_ids=profile_data["collected_ids"],
        top_k=top_k
    )

    return {
        "status": "success",
        "user_id": user_id,
        "collection_count": len(subsample),
        "predicted_cluster": profile_data["predicted_cluster"],
        "predicted_label": profile_data["predicted_label"],
        "recommendations": recommendations
    }