"""Entrada compatível. Prefira python -m horulince processar."""
import sys
from horulince.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main(["processar", "--fonte", "0", "--mostrar", *sys.argv[1:]]))
