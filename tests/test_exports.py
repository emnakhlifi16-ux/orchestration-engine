import json
from pathlib import Path

import pytest
from music21 import converter, instrument, meter, note, stream

from orchestre.core import arrange, export, load_config


@pytest.fixture
def melody_files(tmp_path):
    score = stream.Score()
    part = stream.Part(id="source_melody")
    part.partName = "Mélodie test"
    part.insert(0, instrument.Violin())
    part.insert(0, meter.TimeSignature("4/4"))
    for number, pitch in enumerate(("C5", "D5", "E5", "G5"), start=1):
        measure = stream.Measure(number=number)
        measure.append(note.Note(pitch, quarterLength=4))
        part.append(measure)
    score.insert(0, part)
    musicxml_path = tmp_path / "source.musicxml"
    midi_path = tmp_path / "source.mid"
    score.write("musicxml", fp=str(musicxml_path))
    score.write("midi", fp=str(midi_path))
    return musicxml_path, midi_path


@pytest.mark.parametrize("input_index", (0, 1), ids=("musicxml-input", "midi-input"))
def test_read_input_and_generate_all_exports(tmp_path, melody_files, input_index):
    melody_path = melody_files[input_index]
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({
        "melody": str(melody_path),
        "chords": ["C", "Am", "F", "G7"],
        "tempo": 96,
        "meter": "4/4",
        "key": "C",
        "structure": [{"section": "test", "measures": [1, 2, 3, 4]}],
        "instruments": {"Violon I": {"count": 4, "parts": ["Violon I"]}, "Violoncelle": {"count": 2}},
    }, ensure_ascii=False), encoding="utf-8")

    score, summary = arrange(load_config(config_path))
    output = tmp_path / "output"
    export(score, summary, output)

    expected = [output / "partition_generale.musicxml", output / "arrangement.mid",
                output / "rapport_validation.json", output / "resume_arrangement.json"]
    assert all(path.is_file() and path.stat().st_size > 0 for path in expected)
    general = converter.parse(str(output / "partition_generale.musicxml"))
    midi = converter.parse(str(output / "arrangement.mid"))
    assert len(general.parts) == len(score.parts)
    nonempty_score_parts = [part for part in score.parts if list(part.recurse().notes)]
    assert len(midi.parts) == len(nonempty_score_parts)
    assert len(list(general.recurse().notes)) > 0
    assert len(list(midi.recurse().notes)) == sum(len(list(part.recurse().notes)) for part in nonempty_score_parts)

    part_xml = sorted((output / "parties").glob("*.musicxml"))
    part_mid = sorted((output / "parties").glob("*.mid"))
    assert len(part_xml) == len(score.parts)
    assert len(part_mid) == len(score.parts)
    assert (output / "parties" / "violons_1.musicxml").is_file()
    assert (output / "parties" / "flute_1.musicxml").is_file()
    assert (output / "parties" / "alto_vocal.musicxml").is_file()
    assert (output / "parties" / "basse_vocale.mid").is_file()
    for path in part_xml:
        decoded = converter.parse(str(path))
        assert len(decoded.parts) == 1, path.name
        assert len(list(decoded.recurse().notes)) > 0 or "batterie" in path.stem or "derbouka" in path.stem
    for path in part_mid:
        decoded = converter.parse(str(path))
        assert len(list(decoded.recurse().notes)) > 0 or "batterie" in path.stem or "derbouka" in path.stem

    report = json.loads((output / "rapport_validation.json").read_text(encoding="utf-8"))
    assert report["status"] in {"ok", "issues"}
    assert "issues" in report
    assert summary["mesures"] == 4


def test_effectif_is_configurable():
    from orchestre.instruments import configured_instruments
    specs = configured_instruments({"instruments": {"Violon I": 6, "Flûte 1": {"count": 0}}})
    assert next(s for s in specs if s.name == "Violon I").count == 6
    assert next(s for s in specs if s.name == "Flûte 1").count == 0


def test_unknown_instrument_is_rejected():
    from orchestre.instruments import configured_instruments
    with pytest.raises(ValueError, match="Instruments inconnus"):
        configured_instruments({"instruments": {"Saxophone": 1}})
