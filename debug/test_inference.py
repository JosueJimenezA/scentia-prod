import sys
import os
import uuid
import numpy as np
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Asegurar que los módulos del backend estén en el PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../scentia-backend')))

from app.models import Fragrance
from app.services.inference_service import inference_engine

# =========================================================================
# CONFIGURACIÓN DE LA URL OBJETIVO PARA EL EXPERIMENTO B
# =========================================================================
TARGET_FRAGRANCE_URL = "https://www.fragrantica.es/perfume/Armaf/Club-de-Nuit-Sillage-64105.html"  # <--- Cambia esta URL por la que desees probar

def print_separator(title: str):
    print("\n" + "=" * 75)
    print(f" 🧪 {title}")
    print("=" * 75)

def display_recommendations(recs):
    if not recs:
        print("   ❌ No se generaron recomendaciones.")
        return
    for idx, r in enumerate(recs[:5], 1):
        print(f"   [{idx}] {r['name']} ({r.get('designer', 'N/A')}) | Match: {r['similarity_score']} | Perfil: {r.get('olfactory_profile_label')}")

def run_test():
    print_separator("INICIANDO PRUEBA DE INFERENCIA DINÁMICA CON BUSQUEDA POR URL")

    # -------------------------------------------------------------------------
    # CONFIGURACIÓN Y CONEXIÓN A POSTGRESQL (RENDER)
    # -------------------------------------------------------------------------
    RENDER_DATABASE_URL = "postgresql://scentia_admin:m6TZWG6R3AyxqKtJ6cU2sSJS5ogFXf91@dpg-d9iquh37uimc73c12plg-a.oregon-postgres.render.com/scentia_db?sslmode=require"
    
    engine = create_engine(RENDER_DATABASE_URL, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # =========================================================================
        # 1. LÍNEA BASE: Colección Inicial (Tomada desde el Parquet/BD)
        # =========================================================================
        print_separator("PASO 1: LÍNEA BASE (Colección Inicial)")

        sample_ids = list(inference_engine.id_to_index.keys())[:2]
        
        subsample_base = []
        for fid in sample_ids:
            idx = inference_engine.id_to_index[fid]
            row = inference_engine.df_master.iloc[idx]
            
            f = Fragrance(
                id=uuid.UUID(fid),
                name=row.get('name_raw', 'Fragancia Base'),
                designer=row.get('designer_raw', 'Casa Base'),
                top_notes=row.get('top_notes_raw'),
                heart_notes=row.get('heart_notes_raw'),
                base_notes=row.get('base_notes_raw')
            )
            subsample_base.append((f, 5.0))

        print(f"📌 [CONFIGURACIÓN] Colección Base con {len(subsample_base)} fragancias:")
        for f, r in subsample_base:
            print(f"   • {f.name} (ID: {f.id}) - Rating: {r}")

        # --- EVALUACIÓN LÍNEA BASE ---
        res_base = inference_engine.analyze_user_vector_and_cluster(subsample_base)
        centroid_base = res_base["user_centroid"]
        cluster_base = res_base["predicted_cluster"]
        label_base = res_base["predicted_label"]

        print(f"\n📊 [RESULTADO LÍNEA BASE]")
        print(f"   • Cluster Predicho: {cluster_base} ({label_base})")
        print(f"   • Norma del Centroide: {np.linalg.norm(centroid_base):.4f}")

        recs_base = inference_engine.generate_recommendations(
            user_centroid=centroid_base,
            collected_ids=res_base["collected_ids"],
            top_k=5
        )
        print("\n🎯 Top 5 Recomendaciones (Línea Base):")
        display_recommendations(recs_base)

        # =========================================================================
        # 2. EXPERIMENTO A: Agregar Fragancia Existente en Parquet (Estilo Diferente)
        # =========================================================================
        print_separator("PASO 2: EXPERIMENTO A (Fragancia Existente en Parquet - Estilo Diferente)")

        extra_id_a = list(inference_engine.id_to_index.keys())[50]
        extra_idx_a = inference_engine.id_to_index[extra_id_a]
        row_a = inference_engine.df_master.iloc[extra_idx_a]

        frag_a = Fragrance(
            id=uuid.UUID(extra_id_a),
            name=row_a.get('name_raw', 'Fragancia A'),
            designer=row_a.get('designer_raw', 'Diseñador A'),
            top_notes=row_a.get('top_notes_raw'),
            heart_notes=row_a.get('heart_notes_raw'),
            base_notes=row_a.get('base_notes_raw')
        )

        subsample_exp_a = subsample_base + [(frag_a, 5.0)]

        res_a = inference_engine.analyze_user_vector_and_cluster(subsample_exp_a)
        centroid_a = res_a["user_centroid"]
        
        cos_sim_a = np.dot(centroid_base, centroid_a.T) / (np.linalg.norm(centroid_base) * np.linalg.norm(centroid_a))
        
        print(f"➕ Fragancia añadida: {frag_a.name}")
        print(f"📊 [RESULTADO EXPERIMENTO A]")
        print(f"   • Nuevo Cluster: {res_a['predicted_cluster']} ({res_a['predicted_label']})")
        print(f"   • Similitud Coseno con Centroide Base: {cos_sim_a[0][0]:.4f}")

        recs_a = inference_engine.generate_recommendations(
            user_centroid=centroid_a,
            collected_ids=res_a["collected_ids"],
            top_k=5
        )
        print("\n🎯 Top 5 Recomendaciones (Tras añadir Fragancia A):")
        display_recommendations(recs_a)

        # =========================================================================
        # 3. EXPERIMENTO B: BÚSQUEDA POR URL EN LA BASE DE DATOS Y PESOS ON-THE-FLY
        # =========================================================================
        print_separator("PASO 3: EXPERIMENTO B (Búsqueda por URL en BD e Inferencia Dinámica)")

        clean_target_url = TARGET_FRAGRANCE_URL.strip()
        print(f"🔍 Consultando la base de datos por la URL:\n   '{clean_target_url}'")

        # Buscar el registro exacto por fragrantica_url
        target_fragrance = db.query(Fragrance).filter(Fragrance.fragrantica_url == clean_target_url).first()

        if not target_fragrance:
            print(f"\n❌ ERROR: No se encontró ninguna fragancia con la URL especificada en la BD.")
            print(f"   Asegúrate de que el scraper haya insertado la URL exacta.")
            return

        target_id_str = str(target_fragrance.id)
        is_in_parquet = target_id_str in inference_engine.id_to_index

        print(f"\n📌 [DATOS EXTRAÍDOS DE LA BD]:")
        print(f"   • ID:               {target_fragrance.id}")
        print(f"   • Nombre:           {target_fragrance.name}")
        print(f"   • Diseñador:        {target_fragrance.designer}")
        print(f"   • URL:              {target_fragrance.fragrantica_url}")
        print(f"   • Notas Salida:    {target_fragrance.top_notes}")
        print(f"   • Notas Corazón:   {target_fragrance.heart_notes}")
        print(f"   • Notas Fondo:     {target_fragrance.base_notes}")
        print(f"   • ¿Existe en Parquet precalculado?: {'SÍ' if is_in_parquet else 'NO (Se transformará ON-THE-FLY ⚡)'}")

        # Ejecutamos la transformación directa para extraer los pesos intermedios
        embedding_vec, weights = inference_engine._transform_fragrance_on_the_fly(target_fragrance)

        print("\n⚖️ [DESGLOSE DE PESOS CALCULADOS ON-THE-FLY PARA ESTA FRAGANCIA]")
        print(f"   1. Corpus Olfativo Ponderado:\n      '{weights['weighted_corpus']}'")
        
        print("\n   2. Pesos TF-IDF (Términos olfativos detectados):")
        if weights['top_tfidf_words']:
            for word, weight in weights['top_tfidf_words'].items():
                print(f"      • {word:<20} -> Peso TF-IDF: {weight}")
        else:
            print("      (Sin coincidencias en el vocabulario TF-IDF)")

        print("\n   3. Arquetipos Olfativos Activados (0.0 o 1.0):")
        for arch, val in weights['active_archetypes'].items():
            status = "✅ ACTIVADO" if val == 1.0 else "❌ Inactivo"
            print(f"      • {arch:<22} -> {status}")

        print("\n   4. Componentes Vectoriales reducidas por SVD (Dimensión 15):")
        print(f"      {weights['svd_embedding_components']}")

        # Agregamos esta fragancia encontrada por URL a la colección acumulada
        subsample_exp_b = subsample_exp_a + [(target_fragrance, 5.0)]

        res_b = inference_engine.analyze_user_vector_and_cluster(subsample_exp_b)
        centroid_b = res_b["user_centroid"]
        
        cos_sim_b = np.dot(centroid_a, centroid_b.T) / (np.linalg.norm(centroid_a) * np.linalg.norm(centroid_b))

        print(f"\n📊 [RESULTADO EXPERIMENTO B]")
        print(f"   • Cluster Predicho Final: {res_b['predicted_cluster']} ({res_b['predicted_label']})")
        print(f"   • Similitud Coseno con Centroide del Exp A: {cos_sim_b[0][0]:.4f}")

        recs_b = inference_engine.generate_recommendations(
            user_centroid=centroid_b,
            collected_ids=res_b["collected_ids"],
            top_k=5
        )
        print("\n🎯 Top 5 Recomendaciones Finales (Influenciadas por la fragancia buscada por URL):")
        display_recommendations(recs_b)

        print_separator("PRUEBAS DE INFERENCIA POR URL COMPLETADAS CON ÉXITO 🎉")

    except Exception as e:
        print(f"\n💥 Excepción durante la prueba: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    run_test()