from ultralytics import YOLO

# Carrega o modelo YOLO pequeno (baixa sozinho na primeira vez)
modelo = YOLO("yolov8n.pt")

# Imagem de exemplo da própria biblioteca (tem ônibus e pessoas)
resultados = modelo("https://ultralytics.com/images/bus.jpg")

# Mostra o que foi detectado
for r in resultados:
    for caixa in r.boxes:
        classe = modelo.names[int(caixa.cls)]
        confianca = float(caixa.conf)
        print(f"{classe}: {confianca:.2f}")

# Salva a imagem com as caixas desenhadas
resultados[0].save("saida.jpg")
print("Imagem salva em saida.jpg")
