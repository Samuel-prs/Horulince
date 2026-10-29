"""Compatibilidade de funções; não abre câmeras nem carrega modelos ao importar."""
from horulince.core import VEHICLES as VEICULOS, attribute_score as pontuar, color_name as nome_cor, plate_relation


def cores_do_veiculo(recorte):
    from horulince.vision import vehicle_colors
    return vehicle_colors(recorte)


def ler_placa(recorte):
    from horulince.vision import configure_tesseract, read_plate
    configure_tesseract()
    return read_plate(recorte)[0]


def placas_parecidas(a, b):
    """Compatibilidade legada; nunca implica certeza ou nota máxima."""
    return plate_relation(a, b) in {"exata", "aproximada"}
