from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from mainAPI import app

client = TestClient(app)


def det(placa, conf=0.9, **extra):
    return client.post(
        "/detections",
        json={"placa_lida": placa, "confianca_placa": conf, "origem": "video_teste_01", **extra},
    )


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_formato_invalido_descarta():
    r = det("12345").json()
    assert r["resultado"] == "formato_invalido" and r["dados_descartados"] and r["registro_id"] is None


def test_baixa_confianca_descarta():
    r = det("ABC1D23", conf=0.3).json()
    assert r["resultado"] == "baixa_confianca" and r["registro_id"] is None


def test_placa_sem_cadastro_registra_passagem_sem_alerta():
    r = det("JJJ0J00", modelo_detectado="Gol").json()
    assert r["resultado"] == "sem_cadastro" and r["registro_id"] and r["alerta_id"] is None
    assert client.get(f"/traffic-records/{r['registro_id']}").json()["cadastrado"] is False


def test_cadastro_ok_sem_alerta():
    r = det("BRA2E19", marca_detectada="Chevrolet", modelo_detectado="Onix",
            confianca_modelo=0.9, cor_detectada="vermelho").json()
    assert r["resultado"] == "cadastro_ok" and r["alerta_id"] is None and r["divergencias"] == []


def test_restricao_gera_alerta_e_exige_revisao():
    r = det("abc-1d23", modelo_detectado="Uno", cor_detectada="preto").json()
    assert r["resultado"] == "restricao" and r["alerta_id"]
    aid = r["alerta_id"]
    assert client.get(f"/alerts/{aid}").json()["estado"] == "pendente"

    ok = client.post(
        f"/alerts/{aid}/review",
        json={"operador": "op_teste", "acao": "confirmar_para_analise", "justificativa": "Conferido."},
    )
    assert ok.status_code == 200 and ok.json()["estado"] == "confirmado_para_analise"
    again = client.post(
        f"/alerts/{aid}/review",
        json={"operador": "op_teste", "acao": "descartar", "justificativa": "Tentativa."},
    )
    assert again.status_code == 409
    acoes = [x["acao"] for x in client.get("/audit", params={"alerta_id": aid}).json()]
    assert acoes == ["alerta_emitido", "confirmar_para_analise"]


def test_divergencia_de_modelo_sinaliza_clonagem():
    # DEF5678 é um Corolla sem restrição; a visão detectou um Gol
    r = det("DEF5678", modelo_detectado="Gol", confianca_modelo=0.85).json()
    assert r["resultado"] == "divergencia_modelo" and r["alerta_id"]
    assert any("modelo" in d for d in r["divergencias"])


def test_modelo_de_baixa_confianca_nao_gera_divergencia():
    r = det("DEF5678", modelo_detectado="Gol", confianca_modelo=0.2).json()
    assert r["resultado"] == "cadastro_ok" and r["alerta_id"] is None


def test_restricao_com_divergencia():
    r = det("XYZ9876", modelo_detectado="Onix", confianca_modelo=0.9).json()
    assert r["resultado"] == "restricao_com_divergencia"


def test_revisao_exige_justificativa():
    r = det("QWE4R56").json()
    bad = client.post(
        f"/alerts/{r['alerta_id']}/review",
        json={"operador": "op_teste", "acao": "descartar", "justificativa": ""},
    )
    assert bad.status_code == 422


def test_historico_e_filtros_de_registros():
    det("DEF5678", modelo_detectado="Corolla", confianca_modelo=0.9, origem="cam_filtro")
    h = client.get("/vehicles/def-5678").json()
    assert h["veiculo"]["modelo"] == "Corolla" and h["total_passagens"] >= 1
    assert client.get("/vehicles/ZZZ0000").status_code == 404
    regs = client.get("/traffic-records", params={"placa": "DEF5678", "origem": "cam_filtro"}).json()
    assert len(regs) == 1


def test_catalogo_e_cadastro():
    assert "Uno" in client.get("/vehicles/models").json()["Fiat"]
    restritos = client.get("/vehicles", params={"com_restricao": True}).json()
    assert restritos and all(v["restricao"] for v in restritos)


def test_expurgo_remove_antigos_e_preserva_alerta_pendente():
    antigo = datetime.now(timezone.utc) - timedelta(days=90)
    a = det("BRA2E19", data_hora=antigo.isoformat(), origem="cam_antiga").json()
    b = det("QWE4R56", data_hora=antigo.isoformat(), origem="cam_antiga").json()  # alerta pendente
    res = client.post("/traffic-records/purge", params={"retencao_dias": 30, "operador": "op_teste"}).json()
    assert res["removidos"] >= 1
    assert client.get(f"/traffic-records/{a['registro_id']}").status_code == 404
    assert client.get(f"/traffic-records/{b['registro_id']}").status_code == 200


def test_metricas_a_medir_e_docs():
    assert all(m["valor"] == "a medir" for m in client.get("/evaluation/metrics").json())
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200
