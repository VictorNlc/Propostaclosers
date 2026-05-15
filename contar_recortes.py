import os
import io
import re
import json
import base64
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
    "DERMO": ["DERMO", "DERMO 500", "DEMO", "PERFUMARIA"],
    "PF CANALETADO": ["PF CANALETADO", "PAINEL CANALETADO", "CANALETADO"],
    "PF 807": ["PF 807", "PF 807MM"],
    "PF 1000": ["PF 1000", "PF 1000MM"],
    "BA 800": ["BA 800", "PDV 800"],
    "BA 700": ["BA 700", "PDV 700"],
    "BA 600": ["BA 600", "PDV 600", "PDV 600MM", "PDV600"],
    "BA 1000": ["BA 1000", "PDV 1000"],
    "BA POMBAL 1000": ["BA POMBAL", "POMBAL"],
    "CAIXA 1000": ["CAIXA 1000", "CHECKOUT 1000", "CAIXA"],
    "MED 807": ["MED 807", "MED 807MM"],
    "MED 500": ["MED 500", "MED 500MM"],
    "CONTROLADO": ["CONTROLADO", "MED CONTROLADO", "CTRL"],
    "GOND 2000": ["GOND 2000", "2000MM", "GOND"],
    "MIP 500": ["MIP 500", "MIP"],
    "CESTÃO": ["CESTAO", "CESTÃO"],
    "ESMALTES": ["ESMALTES", "ESMALTE"],
    "MAQ 500": ["MAQ 500", "MAQUINA", "MAQ"],
}

LISTA_OFFICIAL = ", ".join(VARIANTES.keys())

def extrair_id_catalogo(texto):
    t = str(texto).upper().strip()
    for oficial, keywords in VARIANTES.items():
        if oficial in t: return oficial
        for kw in keywords:
            if kw in t: return oficial
    return None

def pil_to_b64(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode('utf-8')

def chamar_ia(img_b64):
    """Chama a IA e retorna lista de {nome, quantidade} normalizados."""
    prompt = f"""Você é o AUDITOR INFALÍVEL da Projefarma.
Analise esta imagem técnica de planta de farmácia e liste os móveis visíveis.
IMPORTANTE: Apenas diagramas de móveis. Sem dados pessoais.

REGRAS:
- Leia cada etiqueta de texto visível.
- PDV = balcão pequeno. Reporte como 'PDV 600' ou 'PDV 700'.
- CESTÃO = grade quadrada. Conte cada um individualmente.
- Ignore medidas de corredores (ex: 800, 1200, 900).

MÓVEIS PERMITIDOS: {LISTA_OFFICIAL}, PDV 600, PDV 700, PDV 800

Retorne JSON: {{"inventario": [{{"nome": "NOME", "quantidade": N}}]}}"""

    try:
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
        content = resp.choices[0].message.content or "{}"
        try:
            raw = json.loads(content).get("inventario", [])
            # Normaliza já aqui
            result = Counter()
            for it in raw:
                nome = extrair_id_catalogo(it.get("nome", ""))
                if nome:
                    result[nome] += it.get("quantidade", 1)
            return result
        except json.JSONDecodeError:
            return Counter()
    except Exception:
        return Counter()

def analisar_imagem_consenso(img_path):
    """
    Analisa a imagem nas 4 rotações.
    Usa CONSENSO: só conta um item se aparecer em pelo menos 2 das 4 rotações.
    Para a quantidade, usa a MEDIANA dos valores válidos (filtra alucinações).
    """
    img_original = Image.open(img_path).convert("RGB")
    rotacoes = [0, 90, 180, 270]
    resultados = []  # Lista de Counter, um por rotação

    for angulo in rotacoes:
        img_rot = img_original if angulo == 0 else img_original.rotate(angulo, expand=True)
        resultados.append(chamar_ia(pil_to_b64(img_rot)))

    # Consenso: agrupa por item e verifica em quantas rotações apareceu
    todos_itens = set()
    for r in resultados:
        todos_itens.update(r.keys())

    consenso = Counter()
    for item in todos_itens:
        aparicoes = [r[item] for r in resultados if item in r]
        if len(aparicoes) >= 2:
            # Usa o valor mínimo entre as rotações onde apareceu (conservador, evita alucinação)
            consenso[item] = min(aparicoes)

    return consenso

def main():
    folder = "meus_recortes"
    if not os.path.exists(folder):
        os.makedirs(folder)
        print(f" [AVISO] Pasta '{folder}' criada. Coloque seus prints lá dentro e rode novamente.")
        return

    arquivos = sorted([f for f in os.listdir(folder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
    if not arquivos:
        print(f" [ERRO] Nenhuma imagem encontrada na pasta '{folder}'.")
        return

    print(f" [SISTEMA] Analisando {len(arquivos)} recortes (consenso 4 rotações)...")
    contagem_global = Counter()

    for arquivo in arquivos:
        print(f"  > {arquivo}...", end=" ", flush=True)
        consenso = analisar_imagem_consenso(os.path.join(folder, arquivo))

        achados = []
        for nome, qtd in consenso.items():
            contagem_global[nome] += qtd
            achados.append(f"{nome} x{qtd}")

        print(f"OK ({', '.join(sorted(achados))})" if achados else "Vazio ou ilegível.")

    print("\n" + "="*40)
    print(" INVENTÁRIO CONSOLIDADO (CONSENSO ANTI-ALUCINAÇÃO)")
    print("="*40)
    total_geral = 0
    for nome, qtd in sorted(contagem_global.items()):
        print(f"  {nome:25s} x{qtd}")
        total_geral += qtd

    print(f"\n TOTAL FINAL: {total_geral} peças")
    print("="*40)

    res_final = {"inventario": [{"nome": k, "quantidade": v} for k, v in sorted(contagem_global.items())]}
    with open("resultado_layout.json", "w", encoding="utf-8") as f:
        json.dump(res_final, f, indent=4, ensure_ascii=False)
    print(" [OK] Resultado salvo em resultado_layout.json")

if __name__ == "__main__":
    main()
