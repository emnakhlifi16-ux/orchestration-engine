"""Crée et exporte un court exemple sans fichier musical externe."""
from __future__ import annotations

import json
from pathlib import Path

from music21 import instrument, meter, note, stream

from orchestre.core import arrange, export


ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent


def main() -> None:
    melody = stream.Score()
    part = stream.Part(id="demo_melody")
    part.partName = "Mélodie de démonstration"
    part.insert(0, instrument.Violin())
    part.insert(0, meter.TimeSignature("4/4"))
    bars = [
        ("C5", "E5", "A5", "G5"), ("A4", "C5", "E5", "C5"),
        ("G5", "E5", "D5", "C5"), ("D5", "E5", "G5", "A5"),
        ("B5", "A5", "G5", "F5"), ("E5", "G5", "C6", "B5"),
        ("A5", "G5", "E5", "D5"), ("C6", "G5", "E5", "C5"),
    ]
    for measure_number, pitches in enumerate(bars, start=1):
        measure = stream.Measure(number=measure_number)
        for pitch_name in pitches:
            measure.append(note.Note(pitch_name, quarterLength=1))
        part.append(measure)
    melody.insert(0, part)
    source_path = HERE / "melodie_demo.musicxml"
    melody.write("musicxml", fp=str(source_path))

    config = json.loads((HERE / "arrangement_demo.json").read_text(encoding="utf-8"))
    config["melody"] = str(source_path)
    score, overview = arrange(config)
    export(score, overview, HERE / "sortie_demo")
    print(f"Exemple exporté dans {HERE / 'sortie_demo'}")


if __name__ == "__main__":
    main()
