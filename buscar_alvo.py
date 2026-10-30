"""Busca em vídeo usando as regras e persistência compartilhadas."""
import sys
from horulince.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main(["processar", *sys.argv[1:]]))
