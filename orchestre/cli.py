import argparse

from .core import arrange, export, load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Génère une maquette d'orchestration depuis une mélodie et des accords fournis.")
    parser.add_argument("config", help="Fichier de configuration JSON")
    parser.add_argument("--out", default="sortie", help="Dossier de sortie")
    args = parser.parse_args()
    score, overview = arrange(load_config(args.config))
    export(score, overview, args.out)
    print(f"Partitions exportées dans {args.out}")


if __name__ == "__main__":
    main()
