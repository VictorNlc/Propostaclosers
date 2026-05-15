import easyocr
import fitz
from PIL import Image
import io
import os
import time

def main():
    print("Iniciando EasyOCR...")
    reader = easyocr.Reader(['pt', 'en'], gpu=False)
    
    pdfs = [f for f in os.listdir() if f.endswith('.pdf')]
    pdf_path = pdfs[0]
    print(f"Extraindo pagina 20 de {pdf_path}")
    
    doc = fitz.open(pdf_path)
    page = doc[19] # pagina 20
    zoom = 4.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    
    img_bytes = pix.tobytes("png")
    
    print("Processando OCR...")
    t0 = time.time()
    # Para EasyOCR, podemos passar os bytes da imagem
    results = reader.readtext(img_bytes)
    t1 = time.time()
    print(f"OCR finalizado em {t1-t0:.2f}s")
    
    # Vamos focar em achar as palavras chaves
    chaves = ["ESM", "MED", "PF", "807", "500", "CEST", "CHECKOUT", "DERMO", "BA", "GOND"]
    
    encontrados = []
    for bbox, text, prob in results:
        text_up = text.upper()
        if any(c in text_up for c in chaves):
            encontrados.append((text, prob))
            
    print("\nTextos encontrados (filtrados):")
    for t, p in encontrados:
        print(f"  [{p:.2f}] {t}")

if __name__ == "__main__":
    main()
