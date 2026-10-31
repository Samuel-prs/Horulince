import argparse
import json
from pathlib import Path
import sys
import sqlite3

from .core import COLORS, VEHICLES
from .pipeline import ROOT
from .storage import AlertStore, STATES


def parser():
    cli = argparse.ArgumentParser(description="Horulince - candidatos de veículos com revisão humana")
    commands = cli.add_subparsers(dest="command", required=True)
    process = commands.add_parser("processar", aliases=["iphone"], help="Processar vídeo ou câmera; iphone abre assistente de conexão")
    process.add_argument("--fonte", help="Arquivo, webcam ou URL RTSP/HTTP da câmera")
    process.add_argument("--origem", help="Identificador da fonte, sem URL/senha")
    process.add_argument("--modelo", default=str(ROOT / "models/yolov8n.pt"))
    process.add_argument("--modelo-placa", help="Modelo YOLO local treinado para placas; opcional")
    process.add_argument("--tesseract")
    process.add_argument("--tipo", choices=sorted(VEHICLES.values()), default="carro")
    process.add_argument("--cor", choices=sorted(COLORS), default="branco")
    process.add_argument("--placa", default="")
    process.add_argument("--lista", help="JSON de alvos fictícios; substitui tipo/cor/placa")
    process.add_argument("--limiar", type=float, default=.7, help="Compatibilidade de características; não é probabilidade")
    process.add_argument("--a-cada", type=int)
    process.add_argument("--ocr-a-cada", type=int, default=2)
    process.add_argument("--imgsz", type=int, default=480)
    process.add_argument("--max-quadros", type=int, default=0, help="0 = até terminar ou Q")
    process.add_argument("--mostrar", action="store_true")
    process.add_argument("--sem-ocr", action="store_true", help="Somente características; não aceita alvo com placa")
    process.add_argument("--registrar-placas", action="store_true", help="Salvar leituras consolidadas e recortes mesmo sem correspondência com alvos")
    process.add_argument("--relatorio", default=str(ROOT / "dados/ultima_execucao.json"))
    listing = commands.add_parser("alertas", help="Listar evidências e candidatos")
    listing.add_argument("--estado", choices=sorted(STATES | {"pendente"}))
    listing.add_argument("--execucao")
    review = commands.add_parser("revisar", help="Registrar decisão humana e justificativa")
    review.add_argument("id")
    review.add_argument("--estado", choices=sorted(STATES), required=True)
    review.add_argument("--operador", required=True)
    review.add_argument("--justificativa", required=True)
    audit = commands.add_parser("auditoria")
    audit.add_argument("--alerta")
    evaluation = commands.add_parser("avaliar", help="Comparar uma execução com ocorrências anotadas")
    evaluation.add_argument("--referencia", required=True)
    evaluation.add_argument("--execucao", required=True)
    evaluation.add_argument("--saida", default=str(ROOT / "dados/avaliacao.json"))
    camera = commands.add_parser("testar-camera", help="Testar transmissão do iPhone sem carregar IA")
    camera.add_argument("--fonte", help="URL RTSP/HTTP; se omitida, pede a URL")
    camera.add_argument("--segundos", type=int, default=10)
    camera.add_argument("--mostrar", action="store_true")
    panel = commands.add_parser("painel", help="Abrir a central de testes no navegador deste computador")
    panel.add_argument("--porta", type=int, default=8765)
    panel.add_argument("--abrir", action="store_true", help="Abrir automaticamente no navegador padrão")
    panel.add_argument("--banco", default=str(ROOT / "dados/horulince.sqlite3"))
    for command in (process, listing, review, audit, evaluation):
        command.add_argument("--banco", default=str(ROOT / "dados/horulince.sqlite3"))
    return cli


def main(argv=None):
    cli = parser()
    args = cli.parse_args(argv)
    try:
        if args.command == "painel":
            from .dashboard import serve
            serve(port=args.porta, database=args.banco, open_browser=args.abrir)
            return 0
        if args.command == "testar-camera":
            from .phone import camera_test, phone_source
            print(json.dumps(camera_test(phone_source(args.fonte), args.segundos, args.mostrar), ensure_ascii=False, indent=2))
            return 0
        if args.command in {"processar", "iphone"}:
            if args.command == "iphone":
                from .phone import phone_source
                args.fonte = phone_source(args.fonte)
                args.origem = args.origem or "iphone13"
                args.mostrar = True
            else:
                args.fonte = args.fonte or str(ROOT / "videos/transito1.mp4")
            args.a_cada = args.a_cada if args.a_cada is not None else (1 if args.command == "iphone" else 3)
            from .pipeline import run
            run(args)
            return 0
        store = AlertStore(args.banco)
        if args.command == "alertas":
            result = [a for a in store.list(args.estado) if not args.execucao or a["run"] == args.execucao]
        elif args.command == "revisar":
            store.review(args.id, args.estado, args.operador, args.justificativa)
            result = {"alerta": args.id, "estado": args.estado, "encaminhamento": "Nenhum envio externo foi executado"}
        elif args.command == "auditoria":
            result = store.audit(args.alerta)
        else:
            from .evaluation import evaluate
            execution = store.get_run(args.execucao)
            if execution is None:
                raise ValueError("Execução concluída não encontrada neste banco")
            if execution["summary"].get("estado_execucao") == "erro":
                raise ValueError("Não é possível avaliar uma execução que terminou com erro")
            reference = json.loads(Path(args.referencia).read_text(encoding="utf-8"))
            alerts = [a for a in store.list() if a["run"] == args.execucao]
            result = evaluate(alerts, reference) | {"execucao": args.execucao}
            if any(event["origem"] != execution["summary"]["origem"] for event in reference):
                raise ValueError("Referência contém origem diferente da execução")
            destination = Path(args.saida)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, RuntimeError, ImportError, sqlite3.Error) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrompido pelo operador.", file=sys.stderr)
        return 130
    except EOFError:
        print("Não foi informado o endereço da câmera. Use --fonte URL_DO_APP.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
