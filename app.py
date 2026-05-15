import os
import io
import re
import time
import json
import base64
import math
import statistics
from PIL import Image
from flask import Flask, request, jsonify, render_template, send_file
from dotenv import load_dotenv
from openai import OpenAI
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import sqlite3
import fitz
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
app = Flask(__name__)
MODELO = "gpt-4o"           # Melhor para leitura visual de layouts
# MODELO = "gpt-4.1"        # Alternativa nova da OpenAI

def init_db():
    conn = sqlite3.connect('cache.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS analises
                 (hash TEXT PRIMARY KEY, resultado TEXT)''')
    conn.commit()
    conn.close()

init_db()

VARIANTES = {
    "DERMO": ["DERMO", "DEMO", "PERFUMARIA"],
    "ESMALTES": ["ESMALTES", "ESMALTE", "ESM"],
    "PF CANALETADO": ["PF CANALETADO", "CANALETADO", "PAINEL CANALETADO", "PF CANAL 807", "PF CANALETADO 807"],
    "PF 807": ["PF 807", "PF 807MM"],
    "PF 807 FUNDO": ["PF 807 FUNDO", "PF 807MM FUNDO"],
    "PF 550": ["PF 550", "PF 550MM"],
    "PF 1000": ["PF 1000", "PF 1000MM"],
    "GOND 3000": ["GOND 3000", "GOND 3000MM", "GONDOLA 3000"],
    "GOND 2200": ["GOND 2200", "GOND 2200MM", "GONDOLA 2200"],
    "GOND 2000": ["GOND 2000", "GOND 2000MM", "GONDOLA 2000"],
    "GOND 1700": ["GOND 1700", "GOND 1700MM", "GONDOLA 1700"],
    "GOND 1400": ["GOND 1400", "GOND 1400MM", "GONDOLA 1400"],
    "GOND": ["GOND", "GONDOLA"],
    "MIP 500": ["MIP 500", "MIP 500MM"],
    "LAT CX 400": ["LAT CX 400", "LAT. CAIXA 400"],
    "LAT CX 550": ["LAT CX 550", "LAT. CAIXA 550", "LAT CAIXA 550", "LAT CAIXA", "LATERAL CAIXA", "CAIXA 550"],
    "MAQ 500": ["MAQ 500", "MAQ 500MM"],
    "BA 800": ["BA 800", "BA 800MM", "PDV 800", "PDV 800MM", "BALCAO 800", "BALCÃO 800"],
    "BA 700": ["BA 700", "BA 700MM", "PDV 700", "PDV 700MM", "BALCAO 700", "BALCÃO 700"],
    "BA 600": ["BA 600", "BA 600MM", "PDV 600", "PDV 600MM", "BALCAO 600", "BALCÃO 600"],
    "BA 1000": ["BA 1000", "BA 1000MM", "PDV 1000", "PDV 1000MM", "BALCAO 1000", "BALCÃO 1000", "BALCAO", "BALCÃO"],
    "BA VIDRO 1000": ["BA VIDRO 1000", "BA VIDRO 1000MM"],
    "BA VIDRO 800": ["BA VIDRO 800", "BA VIDRO 800MM"],
    "BA VIDRO 700": ["BA VIDRO 700", "BA VIDRO 700MM"],
    "BA VIDRO 600": ["BA VIDRO 600", "BA VIDRO 600MM"],
    "BA PIA 900": ["BA PIA 900", "BA PIA 900MM"],
    "BA POMBAL 1000": ["BA POMBAL 1000", "BA POMBAL", "POMBAL 1000", "POMBAL"],
    "CESTAO": ["CESTAO", "CESTÃO", "CESTÃO 400", "CESTAO 400", "CESTO", "CEST 400", "CESTO 400"],
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
    "ESPACO KIDS": ["ESPACO KIDS", "ESPAÇO KIDS", "KIDS"],
    "BOMB": ["BOMB", "BOMBA"],
    "MACA": ["MACA", "MACA/ESCADA"],
}
LISTA_OFFICIAL = ", ".join(VARIANTES.keys())

# Ordem de prioridade: mais específico primeiro
ORDEM_EXTRACAO = [
    "BA POMBAL 1000", "BA VIDRO 1000", "BA VIDRO 800", "BA VIDRO 700", "BA VIDRO 600",
    "BA PIA 900", "BA 1000", "BA 800", "BA 700", "BA 600",
    "LAT CX 550", "LAT CX 400",
    "GOND 3000", "GOND 2200", "GOND 2000", "GOND 1700", "GOND 1400",
    "CHECKOUT 1000", "CAIXA 1000", "CAIXA 600", "CHECKOUT L",
    "PF CANALETADO", "PF 807 FUNDO", "PF 807", "PF 550", "PF 1000",
    "MED 807", "MED 500", "CONTROLADO",
    "MIP 500", "MAQ 500", "VITRINE", "CESTAO", "ESMALTES", "DERMO",
    "CANTONEIRA 400", "PORTA CORRER", "PORTA VAI VEM",
    "FECHAMENTO", "BASE 1200", "MESA EM L", "ESPACO KIDS", "BOMB", "MACA",
    "GOND",
]

def extrair_id(texto):
    if not texto: return None
    t = str(texto).upper().strip()
    for oficial, kws in VARIANTES.items():
        for kw in kws:
            if kw in t: return oficial
    return None

def pil_to_b64(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

def analisar_recorte_ia(b64, prompt_idx, custom_prompt=None):
    """Analisa um recorte e retorna caixas delimitadoras (x, y, w, h)."""
    base_prompt = """VOCE EH UM AUDITOR INFALIVEL.
Conte os moveis desta LISTA: {lista}.

REGRA CRITICA: Apenas conte a QUANTIDADE de cada item que voce consegue ler claramente.
Ignore medidas de paredes.

Retorne APENAS JSON:
{{"inventario": [{{"nome": "NOME DO MOVEL", "quantidade": 2}}]}}"""
    img_hash = hashlib.md5(b64.encode('utf-8')).hexdigest()
    
    # Verifica cache
    conn = sqlite3.connect('cache.db')
    c = conn.cursor()
    c.execute("SELECT resultado FROM analises WHERE hash=?", (img_hash,))
    row = c.fetchone()
    conn.close()
    
    if row:
        print(f" [CACHE HIT] Usando resultado cacheado para hash {img_hash}")
        cached_data = json.loads(row[0])
        return cached_data["validos"], cached_data["content"]
        
    prompt = base_prompt.replace("{lista}", str(LISTA_OFFICIAL))
        
    try:
        print(f" [IA] Consultando modelo de visão para novo recorte...")
        resp = client.chat.completions.create(
            model=MODELO,
            temperature=0.0,
            seed=42,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"}}
            ]}]
        )
        content = resp.choices[0].message.content or "{}"
        try:
            data = json.loads(content)
            raw_itens = data.get("inventario", [])
            contagem = Counter()
            for it in raw_itens:
                nome = extrair_id(it.get("nome", ""))
                if nome:
                    contagem[nome] += it.get("quantidade", 1)
            
            # Salva no cache
            conn = sqlite3.connect('cache.db')
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO analises VALUES (?, ?)", 
                      (img_hash, json.dumps({"validos": dict(contagem), "content": content})))
            conn.commit()
            conn.close()
            
            return dict(contagem), content
        except json.JSONDecodeError:
            return {}, content
    except Exception as e:
        return {}, str(e)

def analisar_recorte(img, rotacoes, crop_x, crop_y):
    """Processa recorte. Agora roda para TODAS as rotacoes selecionadas e pega o valor maximo (evita contar o mesmo item 2x)."""
    if not rotacoes: rotacoes = [0]
    
    max_counts = Counter()
    textos = []
    
    os.makedirs("debug", exist_ok=True)
    img_path = f"debug/crop_{int(time.time()*1000)}.png"
    img.save(img_path)

    for ang in rotacoes:
        rot = img if ang == 0 else img.rotate(ang, expand=True)
        b64 = pil_to_b64(rot)
        
        contagem, txt = analisar_recorte_ia(b64, 0)
        textos.append(f"[{ang} graus]: " + txt)
        
        for k, v in contagem.items():
            if v > max_counts[k]:
                max_counts[k] = v

    return max_counts, "\n".join(textos), img_path

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/renderizar-pdf", methods=["POST"])
def renderizar_pdf():
    """Renderiza uma pagina do PDF em baixa resolucao para exibir no canvas."""
    pdf_file = request.files.get("pdf")
    pagina = int(request.form.get("pagina", 1))
    if not pdf_file:
        return jsonify({"erro": "Nenhum PDF enviado"}), 400
    pdf_bytes = pdf_file.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    if pagina < 1 or pagina > len(doc):
        return jsonify({"erro": f"Pagina {pagina} invalida. PDF tem {len(doc)} paginas."}), 400
    page = doc[pagina - 1]
    # Baixa resolucao para o canvas (rapido)
    pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    b64 = pil_to_b64(img)
    return jsonify({"imagem": b64, "largura": pix.width, "altura": pix.height, "paginas": len(doc)})

@app.route("/debug_img/<filename>")
def debug_img(filename):
    return send_file(os.path.join("debug", filename))

def calcular_iou(boxA, boxB):
    # Determina as coordenadas da interseção
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    
    interWidth = max(0, xB - xA)
    interHeight = max(0, yB - yA)
    interArea = interWidth * interHeight
    
    # Calcula a área de ambos os boxes
    boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
    
    if boxAArea + boxBArea - interArea == 0: return 0
    return interArea / float(boxAArea + boxBArea - interArea)

@app.route("/analisar/canvas", methods=["POST"])
def analisar_canvas():
    try:
        pdf_file = request.files.get("pdf")
        pagina = int(request.form.get("pagina", 1))
        recortes_json = request.form.get("recortes", "[]")
        if not pdf_file:
            return jsonify({"erro": "Nenhum PDF enviado"}), 400

        recortes = json.loads(recortes_json)
        pdf_bytes = pdf_file.read()
        ZOOM_IA = 18.0
        scale_x = scale_y = 2.0

        itens_finais = Counter()
        logs = []
        
        for i, r in enumerate(recortes):
            doc_local = fitz.open(stream=pdf_bytes, filetype="pdf")
            page_local = doc_local[pagina - 1]
            x1, y1, w, h = r["x"], r["y"], r["width"], r["height"]
            x1_pdf, y1_pdf = x1 / scale_x, y1 / scale_y
            x2_pdf, y2_pdf = (x1 + w) / scale_x, (y1 + h) / scale_y
            rect = fitz.Rect(x1_pdf, y1_pdf, x2_pdf, y2_pdf)

            pix = page_local.get_pixmap(matrix=fitz.Matrix(ZOOM_IA, ZOOM_IA), clip=rect)
            crop_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            doc_local.close()
            
            resultado_contagem, texto_ia, path_img = analisar_recorte(crop_img, r.get("rotacoes", [0]), x1_pdf, y1_pdf)
            for k, v in resultado_contagem.items():
                itens_finais[k] += v
                
            logs.append({"recorte": i+1, "texto": texto_ia, "imagem": path_img})

        inventario = [{"nome": k, "quantidade": v} for k, v in sorted(itens_finais.items())]
        return jsonify({"inventario": inventario, "total": sum(itens_finais.values()), "logs": logs})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"erro": str(e)}), 500

@app.route("/exportar/excel", methods=["POST"])
def exportar_excel():
    """Gera um arquivo Excel formatado com o inventario."""
    data = request.get_json()
    inventario = data.get("inventario", [])
    nome_cliente = data.get("cliente", "Proposta")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Inventário"

    # Estilo do cabeçalho
    header_fill = PatternFill(start_color="1a1f3a", end_color="1a1f3a", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=12)
    header_align = Alignment(horizontal="center", vertical="center")

    ws.column_dimensions["A"].width = 35
    ws.column_dimensions["B"].width = 15
    ws.row_dimensions[1].height = 30

    ws["A1"] = "PRODUTO"
    ws["B1"] = "QUANTIDADE"
    for cell in [ws["A1"], ws["B1"]]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align

    # Linhas de dados
    alt_fill = PatternFill(start_color="f0f4ff", end_color="f0f4ff", fill_type="solid")
    for i, item in enumerate(inventario, start=2):
        ws[f"A{i}"] = item["nome"]
        ws[f"B{i}"] = item["quantidade"]
        ws[f"B{i}"].alignment = Alignment(horizontal="center")
        if i % 2 == 0:
            ws[f"A{i}"].fill = alt_fill
            ws[f"B{i}"].fill = alt_fill

    # Total
    total_row = len(inventario) + 3
    ws[f"A{total_row}"] = "TOTAL"
    ws[f"B{total_row}"] = sum(item["quantidade"] for item in inventario)
    for cell in [ws[f"A{total_row}"], ws[f"B{total_row}"]]:
        cell.font = Font(bold=True, size=12)
        cell.fill = PatternFill(start_color="00d4ff", end_color="00d4ff", fill_type="solid")
        cell.alignment = Alignment(horizontal="center")

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"inventario_{nome_cliente.replace(' ', '_')}.xlsx"
    return send_file(buf, as_attachment=True, download_name=filename,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")



if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
