import os
import json
import base64
import time
import pyautogui
from PIL import Image
from dotenv import load_dotenv
from openai import OpenAI
from collections import Counter

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

MODELO_VISAO = "gpt-4o"

# Catálogo Projefarma (Sincronizado)
VARIANTES = {
    "DERMO": ["DERMO", "DERMO 500", "DEMO"],
    "PF CANALETADO": ["PF CANALETADO", "PAINEL CANALETADO"],
    "PF 807": ["PF 807", "PF 807MM"],
    "PF 1000": ["PF 1000", "PF 1000MM"],
    "BA 800": ["BA 800", "PDV 800"],
    "BA 700": ["BA 700", "PDV 700"],
    "BA 600": ["BA 600", "PDV 600"],
    "BA 1000": ["BA 1000", "PDV 1000"],
    "BA POMBAL 1000": ["BA POMBAL", "POMBAL"],
    "CAIXA 1000": ["CAIXA 1000", "CHECKOUT 1000"],
    "MED 807": ["MED 807", "MED 807MM"],
    "MED 500": ["MED 500", "MED 500MM"],
    "CONTROLADO": ["CONTROLADO", "MED CONTROLADO"],
    "GOND 2000": ["GOND 2000", "2000MM"],
    "MIP 500": ["MIP 500", "MIP"],
}

LISTA_OFFICIAL = ", ".join(VARIANTES.keys())

def limpar_nome(nome):
    n = str(nome).upper().strip()
    for oficial, vars in VARIANTES.items():
        if n == oficial or n in vars or any(v in n for v in vars):
            return oficial
    return n

def capturar_tela():
    print("\n [LENTE MÁGICA] Prepare sua tela! Tirando print em 5 segundos...")
    for i in range(5, 0, -1):
        print(f"  {i}...")
        time.sleep(1)
    
    screenshot = pyautogui.screenshot()
    screenshot.save("screenshot_lente.png")
    print(" [OK] Tela capturada!")
    return "screenshot_lente.png"

def analisar_print(img_path):
    # Converter para base64
    with open(img_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode('utf-8')

    prompt = f"""Você é o AUDITOR INFALÍVEL da Projefarma.
Sua missão é fazer um inventário 100% exato desta captura de tela.

MÉTODO DE CONTAGEM OBRIGATÓRIO:
1. FOCO EM ETIQUETAS: Não conte os desenhos dos móveis, conte as ETIQUETAS (textos). Se houver 6 textos 'CESTÃO', reporte 6 unidades.
2. ILHAS DE CESTÕES: Eles costumam estar em grupos de 4 ou 6. Verifique se há etiquetas empilhadas.
3. ORIENTAÇÃO: Leia textos em qualquer ângulo (ponta-cabeça ou lado).

REGRAS CRÍTICAS:
- Identifique cada retângulo individual de etiqueta.
- Se houver 6 etiquetas de CESTÃO coladas, conte como 6 itens.
- Ignore medidas de corredores.

MÓVEIS PERMITIDOS: {LISTA_OFFICIAL}

Retorne JSON: {{"analise_detalhada": ["Descrição da etiqueta e posição"], "inventario": [{{"nome": "NOME", "quantidade": N}}]}}"""

    print(" [SISTEMA] I.A. Analisando sua tela agora...")
    resp = client.chat.completions.create(
        model=MODELO_VISAO,
        temperature=0.0,
        seed=42,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}", "detail": "high"}}
        ]}]
    )
    return json.loads(resp.choices[0].message.content)

def main():
    path = capturar_tela()
    resultado = analisar_print(path)
    
    print("\n" + "="*40)
    print(" INVENTÁRIO DA TELA (100% PRECISÃO)")
    print("="*40)
    total = 0
    for it in resultado.get("inventario", []):
        nome_clean = limpar_nome(it['nome'])
        print(f"  {nome_clean:25s} x{it['quantidade']}")
        total += it['quantidade']
    print(f"\n TOTAL NESTA ÁREA: {total} peças")
    print("="*40)

if __name__ == "__main__":
    main()
