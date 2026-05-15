import easyocr
import fitz
import io
import os

def main():
    reader = easyocr.Reader(['pt', 'en'], gpu=False)
    pdfs = [f for f in os.listdir() if f.endswith('.pdf')]
    pdf_path = pdfs[0]
    
    doc = fitz.open(pdf_path)
    page = doc[19] # pagina 20
    mat = fitz.Matrix(8.0, 8.0) # Zoom gigante
    
    # Vamos pegar apenas um crop (quadrante superior esquerdo) onde sabemos que tem coisas
    w = page.rect.width
    h = page.rect.height
    rect = fitz.Rect(0, 0, w/2, h/2)
    
    pix = page.get_pixmap(matrix=mat, clip=rect)
    img_bytes = pix.tobytes("png")
    
    print("Processando OCR na resolucao alta...")
    results = reader.readtext(img_bytes)
    
    chaves = ["ESM", "MED", "PF", "807", "500", "CEST", "CHECKOUT", "DERMO", "BA", "GOND"]
    
    print("\nTextos encontrados no quadrante 1 (filtrados):")
    for bbox, text, prob in results:
        text_up = text.upper()
        if any(c in text_up for c in chaves):
            print(f"  [{prob:.2f}] {text}")

if __name__ == "__main__":
    main()
