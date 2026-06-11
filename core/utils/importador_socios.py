import pandas as pd
from sqlalchemy.orm import Session
from database import Socio, Empresa
import os

def importar_socios_desde_excel(db: Session, empresa_id: int, excel_path: str):
    """
    Importa socios desde el template estandarizado de Excel.
    
    Proceso:
    1. Lee el Excel.
    2. Valida columnas.
    3. Mapea identificadores de entidad madre.
    4. Inserta/Actualiza en la DB.
    """
    if not os.path.exists(excel_path):
        return {"error": f"No se encontró el archivo en: {excel_path}"}
    
    try:
        df = pd.read_excel(excel_path)
        
        # Validar columnas requeridas
        required_cols = ["identificador", "tipo_identificador", "nombre_razon_social", "porcentaje_participacion"]
        for col in required_cols:
            if col not in df.columns:
                return {"error": f"Columna faltante en Excel: {col}"}
        
        # Primero, limpiar socios existentes de esta empresa para este proceso (o actualizar)
        # Por simplicidad en este MVP, borramos y re-importamos la estructura actual
        db.query(Socio).filter_by(empresa_id=empresa_id).delete()
        db.commit()
        
        # Diccionario para mapear identificadores a IDs de la DB (para entidad_madre_id)
        mapa_identificadores = {}
        
        # Primer pase: Insertar todos los socios
        for _, row in df.iterrows():
            nuevo_socio = Socio(
                empresa_id=empresa_id,
                identificador=str(row["identificador"]),
                tipo_identificador=int(row["tipo_identificador"]),
                nombre_razon_social=str(row["nombre_razon_social"]),
                nacionalidad=str(row.get("nacionalidad", "Dominicana")),
                residencia_fiscal=str(row.get("residencia_fiscal", "República Dominicana")),
                domicilio=str(row.get("domicilio", "")),
                telefono=str(row.get("telefono", "")),
                porcentaje_participacion=float(row["porcentaje_participacion"]),
                es_persona_fisica=bool(row.get("es_persona_fisica", True)),
                cargo=str(row.get("cargo", "")),
                riesgo_pais=bool(row.get("riesgo_pais", False))
            )
            db.add(nuevo_socio)
            db.flush() # Para obtener el ID generado
            mapa_identificadores[nuevo_socio.identificador] = nuevo_socio.id
        
        # Segundo pase: Resolver entidad_madre_id
        for _, row in df.iterrows():
            madre_ident = str(row.get("entidad_madre_identificador", ""))
            if madre_ident and madre_ident in mapa_identificadores:
                socio_id = mapa_identificadores[str(row["identificador"])]
                socio_db = db.query(Socio).get(socio_id)
                socio_db.entidad_madre_id = mapa_identificadores[madre_ident]
        
        db.commit()
        return {"status": "OK", "count": len(df)}
        
    except Exception as e:
        db.rollback()
        return {"error": f"Fallo al importar Excel: {str(e)}"}

if __name__ == "__main__":
    from core.database import SessionLocal
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db = SessionLocal()
    path = os.path.join(BASE_DIR, "data", "templates", "template_beneficiarios.xlsx")
    res = importar_socios_desde_excel(db, 1, path)
    print(res)
    db.close()
