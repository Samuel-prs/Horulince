"""
Horulince API - MVP (protótipo acadêmico, dados fictícios)

Escopo do MVP: veículos.
  - leitura/validação de placa (padrão antigo e Mercosul)
  - identificação do modelo do veículo e conferência com o cadastro
  - registros de trânsito (histórico de passagens)
  - alerta para veículos com restrição ou com divergência placa x modelo,
    com validação humana obrigatória e trilha de auditoria

A etapa de visão computacional (YOLO + OpenCV + Tesseract) roda fora da API e
envia o resultado (placa lida, modelo detectado e confianças) para POST /detections.

Documentação automática: /docs (Swagger), /redoc, /openapi.json
"""
from __future__ import annotations

import re
import threading
from datetime import datetime, timedelta, timezone
from enum import Enum
from itertools import count
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

PLACA_ANTIGA = re.compile(r"^[A-Z]{3}[0-9]{4}$")  # ABC1234
PLACA_MERCOSUL = re.compile(r"^[A-Z]{3}[0-9][A-Z][0-9]{2}$")  # ABC1D23
LIMIAR_PLACA = 0.60   # abaixo disso a leitura da placa é descartada
LIMIAR_MODELO = 0.50  # abaixo disso o modelo detectado é ignorado na conferência
RETENCAO_DIAS = 30    # prazo inicial (a definir juridicamente) para registros de trânsito

app = FastAPI(
    title="Horulince API (MVP)",
    version="0.2.0",
    description=(
        "MVP acadêmico para apoio à localização de **veículos roubados/furtados**.\n\n"
        "- Identifica **placa** e **modelo** do veículo e mantém **registros de trânsito**.\n"
        "- Todos os dados são **fictícios**; não há consulta a sistemas oficiais (DETRAN, polícia).\n"
        "- O sistema produz **indícios, não certezas**: nenhum alerta segue sem **validação humana**.\n"
        "- Registros de trânsito têm **prazo de retenção** e podem ser expurgados."
    ),
    openapi_tags=[
        {"name": "Sistema", "description": "Saúde e resumo operacional."},
        {"name": "Detecções", "description": "Entrada do resultado da visão computacional (placa + modelo)."},
        {"name": "Veículos", "description": "Cadastro fictício, catálogo de modelos e histórico por placa."},
        {"name": "Registros de trânsito", "description": "Histórico de passagens de veículos."},
        {"name": "Alertas", "description": "Central de alertas e validação humana obrigatória."},
        {"name": "Auditoria e avaliação", "description": "Trilha de auditoria e plano de métricas."},
    ],
)


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------
class FormatoPlaca(str, Enum):
    antigo = "antigo"
    mercosul = "mercosul"


class ResultadoDeteccao(str, Enum):
    formato_invalido = "formato_invalido"
    baixa_confianca = "baixa_confianca"
    sem_cadastro = "sem_cadastro"
    cadastro_ok = "cadastro_ok"
    divergencia_modelo = "divergencia_modelo"
    restricao = "restricao"
    restricao_com_divergencia = "restricao_com_divergencia"


class EstadoAlerta(str, Enum):
    pendente = "pendente"
    em_revisao = "em_revisao"
    confirmado_para_analise = "confirmado_para_analise"
    descartado = "descartado"


class AcaoRevisao(str, Enum):
    confirmar_para_analise = "confirmar_para_analise"
    descartar = "descartar"
    solicitar_revisao = "solicitar_revisao"


class Deteccao(BaseModel):
    placa_lida: str = Field(..., examples=["ABC1D23"], description="Texto lido pelo OCR.")
    confianca_placa: float = Field(..., ge=0, le=1, examples=[0.91])
    marca_detectada: Optional[str] = Field(None, examples=["Fiat"])
    modelo_detectado: Optional[str] = Field(None, examples=["Uno"])
    confianca_modelo: Optional[float] = Field(None, ge=0, le=1, examples=[0.82])
    cor_detectada: Optional[str] = Field(None, examples=["preto"])
    origem: str = Field(..., examples=["video_teste_01"], description="Câmera ou vídeo de teste.")
    local: Optional[str] = Field(None, examples=["Av. Teste, 100 (fictício)"])
    data_hora: Optional[datetime] = Field(None, description="Momento da captura; padrão: agora (UTC).")
    detalhes: Optional[str] = Field(None, examples=["adesivo no vidro traseiro"])


class Veiculo(BaseModel):
    placa: str
    marca: str
    modelo: str
    cor: str
    ano: int
    restricao: Optional[str] = Field(None, description="'roubo', 'furto' ou nulo.")


class RegistroTransito(BaseModel):
    id: int
    placa: str
    formato: FormatoPlaca
    confianca_placa: float
    marca_detectada: Optional[str] = None
    modelo_detectado: Optional[str] = None
    confianca_modelo: Optional[float] = None
    cor_detectada: Optional[str] = None
    origem: str
    local: Optional[str] = None
    data_hora: datetime
    cadastrado: bool
    divergencias: list[str] = Field(default_factory=list)
    alerta_id: Optional[int] = None


class RespostaDeteccao(BaseModel):
    resultado: ResultadoDeteccao
    placa_normalizada: str
    formato: Optional[FormatoPlaca] = None
    registro_id: Optional[int] = Field(None, description="Registro de trânsito criado.")
    alerta_id: Optional[int] = None
    divergencias: list[str] = Field(
        default_factory=list,
        description="Divergências de marca/modelo/cor: possível placa clonada ou adulterada.",
    )
    dados_descartados: bool
    mensagem: str


class Alerta(BaseModel):
    id: int
    origem: str
    data_hora: datetime
    evidencia: str
    confianca: float
    natureza_da_confianca: str
    estado: EstadoAlerta
    registro_id: int
    motivos: list[str]


class Revisao(BaseModel):
    operador: str = Field(..., min_length=2, examples=["operador_teste"])
    acao: AcaoRevisao
    justificativa: str = Field(..., min_length=5, examples=["Placa e modelo conferem com o cadastro fictício."])


class RegistroAuditoria(BaseModel):
    id: int
    data_hora: datetime
    usuario: str
    acao: str
    alerta_id: Optional[int] = None
    justificativa: str = ""


class HistoricoVeiculo(BaseModel):
    veiculo: Veiculo
    total_passagens: int
    passagens: list[RegistroTransito]


class ResultadoExpurgo(BaseModel):
    retencao_dias: int
    removidos: int
    restantes: int


class MetricaAvaliacao(BaseModel):
    nome: str
    valor: str = "a medir"
    descricao: str


# ---------------------------------------------------------------------------
# "Banco de dados" em memória (fictício)
# ---------------------------------------------------------------------------
_lock = threading.Lock()
_alert_ids = count(1)
_audit_ids = count(1)
_registro_ids = count(1)

CADASTRO: dict[str, Veiculo] = {
    v.placa: v
    for v in [
        Veiculo(placa="ABC1D23", marca="Fiat", modelo="Uno", cor="preto", ano=2014, restricao="furto"),
        Veiculo(placa="XYZ9876", marca="Volkswagen", modelo="Gol", cor="branco", ano=2012, restricao="roubo"),
        Veiculo(placa="QWE4R56", marca="Honda", modelo="Civic", cor="prata", ano=2019, restricao="roubo"),
        Veiculo(placa="BRA2E19", marca="Chevrolet", modelo="Onix", cor="vermelho", ano=2021),
        Veiculo(placa="DEF5678", marca="Toyota", modelo="Corolla", cor="cinza", ano=2017),
    ]
}

# Catálogo de modelos reconhecíveis pelo MVP (marca -> modelos)
CATALOGO_MODELOS: dict[str, list[str]] = {
    "Fiat": ["Uno", "Palio", "Argo", "Strada"],
    "Volkswagen": ["Gol", "Polo", "Voyage", "Saveiro"],
    "Chevrolet": ["Onix", "Prisma", "S10"],
    "Honda": ["Civic", "Fit", "HR-V"],
    "Toyota": ["Corolla", "Hilux", "Etios"],
}

REGISTROS: dict[int, RegistroTransito] = {}
ALERTAS: dict[int, Alerta] = {}
AUDITORIA: list[RegistroAuditoria] = []

NATUREZA_CONFIANCA = "Indício estatístico gerado por OCR/classificação; não constitui identificação definitiva."


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _auditar(usuario: str, acao: str, alerta_id: Optional[int] = None, justificativa: str = "") -> None:
    AUDITORIA.append(
        RegistroAuditoria(
            id=next(_audit_ids), data_hora=_agora(), usuario=usuario,
            acao=acao, alerta_id=alerta_id, justificativa=justificativa,
        )
    )


def _normalizar(placa: str) -> str:
    return re.sub(r"[\s\-]", "", placa).upper()


def _formato_placa(placa: str) -> Optional[FormatoPlaca]:
    if PLACA_ANTIGA.match(placa):
        return FormatoPlaca.antigo
    if PLACA_MERCOSUL.match(placa):
        return FormatoPlaca.mercosul
    return None


def _igual(a: Optional[str], b: str) -> bool:
    return a is not None and a.strip().lower() == b.lower()


def _divergencias(v: Veiculo, d: Deteccao) -> list[str]:
    """Compara o que a visão detectou com o cadastro (placa clonada/adulterada)."""
    out = []
    if d.marca_detectada and not _igual(d.marca_detectada, v.marca):
        out.append(f"marca: detectada '{d.marca_detectada}' x cadastro '{v.marca}'")
    modelo_confiavel = d.confianca_modelo is None or d.confianca_modelo >= LIMIAR_MODELO
    if d.modelo_detectado and modelo_confiavel and not _igual(d.modelo_detectado, v.modelo):
        out.append(f"modelo: detectado '{d.modelo_detectado}' x cadastro '{v.modelo}'")
    if d.cor_detectada and not _igual(d.cor_detectada, v.cor):
        out.append(f"cor: detectada '{d.cor_detectada}' x cadastro '{v.cor}'")
    return out


# ---------------------------------------------------------------------------
# Sistema
# ---------------------------------------------------------------------------
@app.get("/health", tags=["Sistema"], summary="Verifica se a API está no ar")
def health() -> dict:
    return {"status": "ok", "ambiente": "mvp_academico", "dados": "ficticios"}


@app.get("/dashboard", tags=["Sistema"], summary="Resumo operacional (dados fictícios)")
def dashboard() -> dict:
    por_estado = {e.value: 0 for e in EstadoAlerta}
    for a in ALERTAS.values():
        por_estado[a.estado.value] += 1
    return {
        "total_registros_transito": len(REGISTROS),
        "total_alertas": len(ALERTAS),
        "alertas_por_estado": por_estado,
        "registros_com_divergencia": sum(1 for r in REGISTROS.values() if r.divergencias),
        "aviso": "Indicadores fictícios; não são estatísticas de criminalidade do município.",
    }


# ---------------------------------------------------------------------------
# Detecções: entrada do pipeline de visão computacional
# ---------------------------------------------------------------------------
@app.post(
    "/detections",
    response_model=RespostaDeteccao,
    tags=["Detecções"],
    summary="Recebe placa + modelo detectados, registra a passagem e avalia alertas",
)
def registrar_deteccao(d: Deteccao) -> RespostaDeteccao:
    """
    Fluxo:

    1. Normaliza e valida a placa (antiga `ABC1234` ou Mercosul `ABC1D23`).
    2. Descarta leituras com confiança de placa abaixo do limiar.
    3. Cria o **registro de trânsito** da passagem.
    4. Se a placa está no cadastro, compara marca/modelo/cor detectados com os do cadastro.
    5. Emite **alerta pendente** se o veículo tem restrição **ou** se há divergência
       (possível placa clonada). Todo alerta exige validação humana.
    """
    placa = _normalizar(d.placa_lida)
    formato = _formato_placa(placa)
    if formato is None:
        return RespostaDeteccao(
            resultado=ResultadoDeteccao.formato_invalido, placa_normalizada=placa, dados_descartados=True,
            mensagem="Leitura não corresponde ao padrão antigo nem ao Mercosul; descartada.",
        )
    if d.confianca_placa < LIMIAR_PLACA:
        return RespostaDeteccao(
            resultado=ResultadoDeteccao.baixa_confianca, placa_normalizada=placa, formato=formato,
            dados_descartados=True, mensagem=f"Confiança da placa abaixo de {LIMIAR_PLACA}; descartada.",
        )

    veiculo = CADASTRO.get(placa)
    divergencias = _divergencias(veiculo, d) if veiculo else []
    restrito = bool(veiculo and veiculo.restricao)

    with _lock:
        registro = RegistroTransito(
            id=next(_registro_ids), placa=placa, formato=formato,
            confianca_placa=d.confianca_placa, marca_detectada=d.marca_detectada,
            modelo_detectado=d.modelo_detectado, confianca_modelo=d.confianca_modelo,
            cor_detectada=d.cor_detectada, origem=d.origem, local=d.local,
            data_hora=d.data_hora or _agora(), cadastrado=veiculo is not None,
            divergencias=divergencias,
        )
        REGISTROS[registro.id] = registro

        alerta_id = None
        if restrito or divergencias:
            motivos = []
            if restrito:
                motivos.append(f"veículo com restrição de {veiculo.restricao}")
            if divergencias:
                motivos.append("divergência entre placa e características do veículo")
            confianca = d.confianca_placa * (0.7 if divergencias else 1.0)
            alerta = Alerta(
                id=next(_alert_ids), origem=d.origem, data_hora=registro.data_hora,
                evidencia=f"Placa '{placa}' lida em '{d.origem}'. " + "; ".join(divergencias),
                confianca=round(confianca, 3), natureza_da_confianca=NATUREZA_CONFIANCA,
                estado=EstadoAlerta.pendente, registro_id=registro.id, motivos=motivos,
            )
            ALERTAS[alerta.id] = alerta
            registro.alerta_id = alerta.id
            alerta_id = alerta.id
            _auditar("sistema", "alerta_emitido", alerta.id, "; ".join(motivos))

    if veiculo is None:
        resultado, msg = ResultadoDeteccao.sem_cadastro, "Placa válida sem cadastro; passagem registrada, sem alerta."
    elif restrito and divergencias:
        resultado, msg = ResultadoDeteccao.restricao_com_divergencia, "Restrição e divergência de modelo/cor: alerta emitido."
    elif restrito:
        resultado, msg = ResultadoDeteccao.restricao, "Veículo com restrição: alerta emitido."
    elif divergencias:
        resultado, msg = ResultadoDeteccao.divergencia_modelo, "Possível placa clonada: alerta emitido."
    else:
        resultado, msg = ResultadoDeteccao.cadastro_ok, "Placa e características conferem; passagem registrada."
    if alerta_id:
        msg += " Aguarda validação humana antes de qualquer encaminhamento."

    return RespostaDeteccao(
        resultado=resultado, placa_normalizada=placa, formato=formato, registro_id=registro.id,
        alerta_id=alerta_id, divergencias=divergencias, dados_descartados=False, mensagem=msg,
    )


# ---------------------------------------------------------------------------
# Veículos
# ---------------------------------------------------------------------------
@app.get("/vehicles", response_model=list[Veiculo], tags=["Veículos"], summary="Cadastro fictício de veículos")
def listar_veiculos(
    com_restricao: Optional[bool] = Query(None, description="Filtra veículos com/sem restrição."),
    marca: Optional[str] = Query(None),
    modelo: Optional[str] = Query(None),
) -> list[Veiculo]:
    itens = list(CADASTRO.values())
    if com_restricao is not None:
        itens = [v for v in itens if bool(v.restricao) == com_restricao]
    if marca:
        itens = [v for v in itens if v.marca.lower() == marca.lower()]
    if modelo:
        itens = [v for v in itens if v.modelo.lower() == modelo.lower()]
    return itens


@app.get("/vehicles/models", tags=["Veículos"], summary="Catálogo de marcas/modelos reconhecíveis")
def catalogo_modelos() -> dict[str, list[str]]:
    return CATALOGO_MODELOS


@app.get(
    "/vehicles/{placa}",
    response_model=HistoricoVeiculo,
    tags=["Veículos"],
    summary="Cadastro e histórico de passagens de uma placa",
)
def historico_veiculo(placa: str) -> HistoricoVeiculo:
    p = _normalizar(placa)
    veiculo = CADASTRO.get(p)
    if not veiculo:
        raise HTTPException(404, "Placa não encontrada no cadastro fictício.")
    passagens = sorted((r for r in REGISTROS.values() if r.placa == p), key=lambda r: r.data_hora)
    return HistoricoVeiculo(veiculo=veiculo, total_passagens=len(passagens), passagens=passagens)


# ---------------------------------------------------------------------------
# Registros de trânsito
# ---------------------------------------------------------------------------
@app.get(
    "/traffic-records",
    response_model=list[RegistroTransito],
    tags=["Registros de trânsito"],
    summary="Lista registros de passagem (com filtros)",
)
def listar_registros(
    placa: Optional[str] = Query(None),
    origem: Optional[str] = Query(None),
    modelo: Optional[str] = Query(None, description="Modelo detectado."),
    com_divergencia: Optional[bool] = Query(None),
    desde: Optional[datetime] = Query(None),
    ate: Optional[datetime] = Query(None),
) -> list[RegistroTransito]:
    itens = list(REGISTROS.values())
    if placa:
        itens = [r for r in itens if r.placa == _normalizar(placa)]
    if origem:
        itens = [r for r in itens if r.origem == origem]
    if modelo:
        itens = [r for r in itens if r.modelo_detectado and r.modelo_detectado.lower() == modelo.lower()]
    if com_divergencia is not None:
        itens = [r for r in itens if bool(r.divergencias) == com_divergencia]
    if desde:
        itens = [r for r in itens if r.data_hora >= desde]
    if ate:
        itens = [r for r in itens if r.data_hora <= ate]
    return sorted(itens, key=lambda r: r.data_hora)


@app.get(
    "/traffic-records/{registro_id}",
    response_model=RegistroTransito,
    tags=["Registros de trânsito"],
    summary="Detalha um registro",
)
def obter_registro(registro_id: int) -> RegistroTransito:
    r = REGISTROS.get(registro_id)
    if not r:
        raise HTTPException(404, "Registro não encontrado.")
    return r


@app.post(
    "/traffic-records/purge",
    response_model=ResultadoExpurgo,
    tags=["Registros de trânsito"],
    summary="Expurga registros além do prazo de retenção",
)
def expurgar(
    retencao_dias: int = Query(RETENCAO_DIAS, ge=0, description="Prazo de retenção em dias (padrão a definir juridicamente)."),
    operador: str = Query("sistema", min_length=2),
) -> ResultadoExpurgo:
    """
    Remove registros mais antigos que o prazo. Registros ligados a alertas ainda não
    finalizados são preservados. A ação é registrada na auditoria.
    """
    limite = _agora() - timedelta(days=retencao_dias)
    with _lock:
        alvo = [
            r.id for r in REGISTROS.values()
            if r.data_hora < limite
            and not (r.alerta_id and ALERTAS[r.alerta_id].estado in (EstadoAlerta.pendente, EstadoAlerta.em_revisao))
        ]
        for rid in alvo:
            del REGISTROS[rid]
        _auditar(operador, "expurgo_registros", None, f"{len(alvo)} removidos (retenção {retencao_dias} dias)")
    return ResultadoExpurgo(retencao_dias=retencao_dias, removidos=len(alvo), restantes=len(REGISTROS))


# ---------------------------------------------------------------------------
# Alertas e validação humana
# ---------------------------------------------------------------------------
@app.get("/alerts", response_model=list[Alerta], tags=["Alertas"], summary="Lista alertas da central")
def listar_alertas(estado: Optional[EstadoAlerta] = Query(None, description="Filtra por estado.")) -> list[Alerta]:
    itens = list(ALERTAS.values())
    return [a for a in itens if a.estado == estado] if estado else itens


@app.get("/alerts/{alerta_id}", response_model=Alerta, tags=["Alertas"], summary="Detalha um alerta")
def obter_alerta(alerta_id: int) -> Alerta:
    alerta = ALERTAS.get(alerta_id)
    if not alerta:
        raise HTTPException(404, "Alerta não encontrado.")
    return alerta


@app.post(
    "/alerts/{alerta_id}/review",
    response_model=Alerta,
    tags=["Alertas"],
    summary="Validação humana do alerta (obrigatória)",
)
def revisar_alerta(alerta_id: int, revisao: Revisao) -> Alerta:
    """Toda decisão exige operador e justificativa e é registrada em auditoria."""
    with _lock:
        alerta = ALERTAS.get(alerta_id)
        if not alerta:
            raise HTTPException(404, "Alerta não encontrado.")
        if alerta.estado in (EstadoAlerta.confirmado_para_analise, EstadoAlerta.descartado):
            raise HTTPException(409, f"Alerta já finalizado ({alerta.estado.value}).")
        alerta.estado = {
            AcaoRevisao.confirmar_para_analise: EstadoAlerta.confirmado_para_analise,
            AcaoRevisao.descartar: EstadoAlerta.descartado,
            AcaoRevisao.solicitar_revisao: EstadoAlerta.em_revisao,
        }[revisao.acao]
        _auditar(revisao.operador, revisao.acao.value, alerta.id, revisao.justificativa)
        return alerta


# ---------------------------------------------------------------------------
# Auditoria e avaliação
# ---------------------------------------------------------------------------
@app.get("/audit", response_model=list[RegistroAuditoria], tags=["Auditoria e avaliação"], summary="Trilha de auditoria")
def auditoria(alerta_id: Optional[int] = Query(None, description="Filtra por alerta.")) -> list[RegistroAuditoria]:
    return AUDITORIA if alerta_id is None else [r for r in AUDITORIA if r.alerta_id == alerta_id]


@app.get(
    "/evaluation/metrics",
    response_model=list[MetricaAvaliacao],
    tags=["Auditoria e avaliação"],
    summary="Plano de métricas (valores 'a medir' até a execução dos testes)",
)
def metricas() -> list[MetricaAvaliacao]:
    return [
        MetricaAvaliacao(nome="precisao_alertas", descricao="Dos alertas emitidos, quantos eram corretos."),
        MetricaAvaliacao(nome="revocacao", descricao="Das ocorrências nos vídeos de teste, quantas foram detectadas."),
        MetricaAvaliacao(nome="falsos_positivos", descricao="Alertas emitidos indevidamente."),
        MetricaAvaliacao(nome="falsos_negativos", descricao="Ocorrências não detectadas."),
        MetricaAvaliacao(nome="acerto_leitura_placas", descricao="Por turno, clima e distância."),
        MetricaAvaliacao(nome="acerto_modelo_veiculo", descricao="Acerto de marca/modelo, por classe e condição de imagem."),
        MetricaAvaliacao(nome="latencia", descricao="Da captura do quadro à exibição do alerta."),
        MetricaAvaliacao(nome="tempo_medio_revisao", descricao="Tempo médio de revisão pelo operador."),
    ]
