import pandas as pd
import os

def generate_template():
    columns = [
        "identificador", 
        "tipo_identificador", 
        "nombre_razon_social", 
        "nacionalidad", 
        "residencia_fiscal", 
        "domicilio", 
        "telefono", 
        "porcentaje_participacion", 
        "es_persona_fisica", 
        "entidad_madre_identificador", 
        "cargo", 
        "riesgo_pais"
    ]
    
    # Datos de ejemplo (Socio Senior Style)
    data = [
        {
            "identificador": "101-00000-1",
            "tipo_identificador": 1, # Cédula
            "nombre_razon_social": "JUAN PEREZ (SOCIO MAYORITARIO)",
            "nacionalidad": "Dominicana",
            "residencia_fiscal": "República Dominicana",
            "domicilio": "Av. Winston Churchill #100, Santo Domingo",
            "telefono": "809-555-1234",
            "porcentaje_participacion": 60.00,
            "es_persona_fisica": True,
            "entidad_madre_identificador": "",
            "cargo": "Presidente",
            "riesgo_pais": False
        },
        {
            "identificador": "1-30-12345-6",
            "tipo_identificador": 2, # RNC
            "nombre_razon_social": "INVERSIONES HOLDING RD, SRL",
            "nacionalidad": "Dominicana",
            "residencia_fiscal": "República Dominicana",
            "domicilio": "Calle Piantini #55, Santo Domingo",
            "telefono": "809-555-5678",
            "porcentaje_participacion": 40.00,
            "es_persona_fisica": False,
            "entidad_madre_identificador": "",
            "cargo": "Accionista",
            "riesgo_pais": False
        },
        {
            "identificador": "001-9999999-9",
            "tipo_identificador": 1, 
            "nombre_razon_social": "MARIA LOPEZ (DUEÑA DEL HOLDING)",
            "nacionalidad": "Dominicana",
            "residencia_fiscal": "República Dominicana",
            "domicilio": "Naco, Santo Domingo",
            "telefono": "829-000-0000",
            "porcentaje_participacion": 100.00, # Dueña del 100% del holding anterior
            "es_persona_fisica": True,
            "entidad_madre_identificador": "1-30-12345-6", # Pertecene al holding
            "cargo": "Beneficiaria Final",
            "riesgo_pais": False
        }
    ]
    
    df = pd.DataFrame(data, columns=columns)
    
    output_path = r"c:\GEMINI\AiContaFiscalRD\data\templates\template_beneficiarios.xlsx"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    df.to_excel(output_path, index=False)
    print(f"Plantilla generada en: {output_path}")

if __name__ == "__main__":
    generate_template()
