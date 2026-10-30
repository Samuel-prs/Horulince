"""Avaliação de eventos com pareamento um-a-um, sem inventar negativos."""
import math

from .core import normalize_plate, valid_plate


def evaluate(alerts, reference):
    if not isinstance(reference, list):
        raise ValueError("Referência deve ser uma lista de ocorrências")
    identifiers = set()
    for event in reference:
        if not isinstance(event, dict) or not all(k in event for k in ("id", "alvo_id", "origem", "inicio", "fim")):
            raise ValueError("Cada referência exige id, alvo_id, origem, inicio e fim")
        if not isinstance(event["id"], str) or not event["id"].strip() or event["id"] in identifiers:
            raise ValueError("IDs de referência devem ser textos únicos")
        identifiers.add(event["id"])
        if not all(isinstance(event[k], str) and event[k].strip() for k in ("alvo_id", "origem")):
            raise ValueError("alvo_id e origem devem ser textos não vazios")
        if not all(isinstance(event[k], (int, float)) and math.isfinite(event[k]) for k in ("inicio", "fim")) or not 0 <= event["inicio"] <= event["fim"]:
            raise ValueError("Intervalo inválido na referência")
        if event.get("placa") and (not isinstance(event["placa"], str) or not valid_plate(normalize_plate(event["placa"]))):
            raise ValueError("Placa inválida na referência")
    choices = {}
    for i, alert in enumerate(alerts):
        choices[i] = [j for j, event in enumerate(reference) if alert["source"] == event["origem"] and alert["target"] == event["alvo_id"] and event["inicio"] <= alert["video_seconds"] <= event["fim"]]
    # Caminhos aumentantes evitam que a ordem dos alertas reduza os acertos.
    matched = {}

    def assign(i, visited):
        for j in choices[i]:
            if j in visited:
                continue
            visited.add(j)
            if j not in matched or assign(matched[j], visited):
                matched[j] = i
                return True
        return False

    for i in choices:
        assign(i, set())
    tp = len(matched)
    plate_pairs = [(alerts[i]["payload"].get("placa"), reference[j]["placa"]) for j, i in matched.items() if reference[j].get("placa")]
    plate_correct = sum(bool(a) and normalize_plate(a) == normalize_plate(b) for a, b in plate_pairs)
    return {"ocorrencias_referencia": len(reference), "alertas": len(alerts), "verdadeiros_positivos": tp, "falsos_positivos": len(alerts) - tp, "falsos_negativos": len(reference) - tp, "precisao_eventos": tp / len(alerts) if alerts else None, "revocacao_eventos": tp / len(reference) if reference else None, "placas_avaliadas_em_eventos_pareados": len(plate_pairs), "acerto_placa_completa_em_eventos_pareados": plate_correct / len(plate_pairs) if plate_pairs else None, "pareamentos": [{"referencia": reference[j]["id"], "alerta": alerts[i]["id"]} for j, i in matched.items()], "nota": "Evento correto = mesmo alvo/origem no intervalo anotado. Alertas duplicados contam como FP. Acerto de placa é calculado separadamente; não há taxa de falsos positivos sem negativos anotados."}
