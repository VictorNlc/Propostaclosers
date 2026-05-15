import os
import json
import base64
import argparse
import io
import math
from PIL import Image
import fitz  # PyMuPDF
from dotenv import load_dotenv
from openai import OpenAI
from collections import Counter

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

MODELO_VISAO = "gpt-4o"
ZOOM_FATOR = 10.0

VARIANTES = {
    "DERMO": ["DERMO", "DEMO", "PERFUMARIA"],
    "ESMALTES": ["ESMALTES", "ESMALTE", "ESM"],
    "PF CANALETADO": ["PF CANALETADO", "CANALETADO", "PAINEL CANALETADO", "PF CANAL 807", "PF CANALETADO 807"],
    "PF 807": ["PF 807", "PF 807MM"],
    "PF 807 FUNDO": ["PF 807 FUNDO", "PF 807MM FUNDO"],
    "PF 550": ["PF 550", "PF 550MM"],
    "PF 1000": ["PF 1000", "PF 1000MM"],
    "GOND 3000": ["GOND 3000", "GOND 3000MM"],
    "GOND 2200": ["GOND 2200", "GOND 2200MM"],
    "GOND 2000": ["GOND 2000", "GOND 2000MM"],
    "GOND 1700": ["GOND 1700", "GOND 1700MM"],
    "GOND 1400": ["GOND 1400", "GOND 1400MM"],
    "GOND": ["GOND"],
    "MIP 500": ["MIP 500", "MIP 500MM"],
    "LAT CX 400": ["LAT CX 400", "LAT. CAIXA 400", "LAT CX 400"],
    "LAT CX 550": ["LAT CX 550", "LAT. CAIXA 550", "LAT CAIXA 550", "LAT CAIXA", "LATERAL CAIXA", "CAIXA 550"],
    "MAQ 500": ["MAQ 500", "MAQ 500MM"],
    "BA 800": ["BA 800", "BA 800MM", "PDV 800", "PDV 800MM"],
    "BA 700": ["BA 700", "BA 700MM", "PDV 700", "PDV 700MM"],
    "BA 600": ["BA 600", "BA 600MM", "PDV 600", "PDV 600MM"],
    "BA 1000": ["BA 1000", "BA 1000MM", "PDV 1000", "PDV 1000MM"],
    "BA VIDRO 1000": ["BA VIDRO 1000", "BA VIDRO 1000MM"],
    "BA VIDRO 800": ["BA VIDRO 800", "BA VIDRO 800MM"],
    "BA VIDRO 700": ["BA VIDRO 700", "BA VIDRO 700MM"],
    "BA VIDRO 600": ["BA VIDRO 600", "BA VIDRO 600MM"],
    "BA PIA 900": ["BA PIA 900", "BA PIA 900MM"],
    "BA POMBAL 1000": ["BA POMBAL 1000", "BA POMBAL", "POMBAL 1000", "POMBAL"],
    "CESTÃO": ["CESTÃO", "CESTAO", "CESTÃO 400"],
    "CHECKOUT 1000": ["CHECKOUT 1000", "CHECK OUT 1000"],
    "CAIXA 1000": ["CAIXA 1000", "CAIXA 1000MM"],
    "CAIXA 600": ["CAIXA 600", "CHECKOUT 600", "CHECK OUT 600"],
    "CHECKOUT L": ["CHECKOUT L"],
    "VITRINE": ["VITRINE", "VITRINE 807", "VITRINE 807MM"],
    "MED 807": ["MED 807", "MED 807MM"],
    "MED 500": ["MED 500", "MED 500MM"],
    "CONTROLADO": ["CONTROLADO", "MED CONTROLADO", "CTRL 500"],
    "CANTONEIRA 400": ["CANTONEIRA 400", "CANTONEIRA 400MM"],
    "PORTA CORRER": ["PORTA CORRER"],
    "PORTA VAI VEM": ["PORTA VAI VEM"],
    "FECHAMENTO": ["FECHAMENTO"],
    "BASE 1200": ["BASE 1200"],
    "MESA EM L": ["MESA EM L", "MESA L", "MESA EM L AMADEIRADO"],
    "ESPAÇO KIDS": ["ESPAÇO KIDS", "ESPACO KIDS", "KIDS"],
    "BOMB": ["BOMB", "BOMBA"],
    "MACA": ["MACA", "MACA/ESCADA"],
}

LISTA_OFFICIAL = list(VARIANTES.keys())

def extrair_id_catalogo(texto):
    t = str(texto).upper()
    for oficial, keywords in VARIANTES.items():
        if oficial in t: return oficial
        for kw in keywords:
            if kw in t: return oficial
    return None

def pdf_page_to_pil(file_path, page_num):
    doc = fitz.open(file_path)
    page = doc[page_num - 1]
    pix = page.get_pixmap(matrix=fitz.Matrix(ZOOM_FATOR, ZOOM_FATOR))
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    w, h = img.size
    return img.crop((int(w*0.18), int(h*0.10), int(w*0.98), int(h*0.85)))

def pil_to_b64(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode('utf-8')

def analisar_setor(b64):
    prompt = f"""Extraia cada etiqueta de móvel.
MÓVEIS: {", ".join(LISTA_OFFICIAL)}

REGRAS:
1. LEITURA COMPLETA: Você deve ler o nome E a medida (ex: MED 807).
2. COORDENADAS: X e Y (0 a 1000).
3. IGNORE LINHAS DE MEDIDA DE PAREDE.

Retorne JSON: {{"deteccoes": [{{"texto": "TEXTO", "x": X, "y": Y}}]}}"""
    
    try:
        resp = client.chat.completions.create(
            model=MODELO_VISAO,
            temperature=0.0,
            seed=42,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"}}
            ]}]
        )
        return json.loads(resp.choices[0].message.content).get("deteccoes", [])
    except: return []

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("arquivo")
    parser.add_argument("--pagina", type=int, default=19)
    args = parser.parse_args()

    img = pdf_page_to_pil(args.arquivo, args.pagina)
    W, H = img.size
    
    # 4 Quadrantes com sobreposição para garantir que nada escape na borda
    setores = [
        (img.crop((0, 0, W*0.55, H*0.55)), 0, 0, W*0.55, H*0.55, 0, 500, 0, 500), # NW
        (img.crop((W*0.45, 0, W, H*0.55)), W*0.45, 0, W*0.55, H*0.55, 500, 1000, 0, 500), # NE
        (img.crop((0, H*0.45, W*0.55, H)), 0, H*0.45, W*0.55, H*0.55, 0, 500, 500, 1000), # SW
        (img.crop((W*0.45, H*0.45, W, H)), W*0.45, H*0.45, W*0.55, H*0.55, 500, 1000, 500, 1000) # Sax in setores:
        print(f" Analisando território {x_min}-{x_max}...")
        itens = analisar_setor(pil_to_b64(s_img))
        for it in itens:
            # Converter para global
            gx = ((off_x + (it['x']/1000.0) * s_w) / W) * 1000.0
            gy = ((off_y + (it['y']/1000.0) * s_h) / H) * 1000.0
            
            # FILTRO DE TERRITÓRIO: Só aceita se o móvel estiver no seu "pedaço" oficial
            if x_min <= gx < x_max and y_min <= gy < y_max:
                nome_oficial = extrair_id_catalogo(it['texto'])
                if nome_oficial:
                    inventario_validado.append(nome_oficial)

    counts = Counter(inventario_validado)
    resultado = {"inventario": [{"nome": k, "quantidade": v} for k, v in sorted(counts.items())]}

    with open("resultado_layout.json", "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=4, ensure_ascii=False)
    
    print("\n" + "="*40)
    print(" INVENTÁRIO FINAL 100% (TERRITORIAL)")
    print("="*40)
    total = 0
    for it in resultado["inventario"]:
        print(f"  {it['nome']:25s} x{it['quantidade']}")
        total += it['quantidade']
    print(f"\n TOTAL: {total} peças")

if __name__ == "__main__":
    main()