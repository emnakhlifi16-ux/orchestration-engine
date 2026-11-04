import json
from pathlib import Path

from music21 import converter, instrument, meter, note, stream

from orchestre.core import arrange, export


def make_test_melody(path: Path, pitches=None):
    pitches = pitches or [
        ["C5", "D5", "E5"], ["G5", "E5", "D5"], ["R", "C5", "D5"], ["E5", "G5", "C6"],
        ["F5", "G5", "A5"], ["C6", "A5", "G5"], ["E5", "D5", "C5"], ["G5", "E5", "C5"],
    ]
    score = stream.Score()
    part = stream.Part(id="melody")
    part.partName = "Mélodie source"
    part.insert(0, instrument.Flute())
    part.insert(0, meter.TimeSignature("4/4"))
    for number, bar_pitches in enumerate(pitches, 1):
        measure = stream.Measure(number=number)
        for pitch in bar_pitches:
            if pitch == "R":
                measure.append(note.Rest(quarterLength=1))
            else:
                measure.append(note.Note(pitch, quarterLength=1))
        if measure.duration.quarterLength < 4:
            measure.append(note.Rest(quarterLength=4 - measure.duration.quarterLength))
        part.append(measure)
    score.insert(0, part)
    score.write("musicxml", fp=str(path))
    return path


def make_config(tmp_path, *, style="classique", structure=None, pitches=None, chords=None, extra=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    melody_path = make_test_melody(tmp_path / "melodie.musicxml", pitches)
    config = {
        "melody": str(melody_path),
        "chords": chords or ["C", "Am", "F", "G7", "Dm", "G", "C", "C"],
        "tempo": 72,
        "meter": "4/4",
        "key": "C",
        "style": style,
        "structure": structure or [{"section": "verse", "measures": list(range(1, 9))}],
    }
    if extra:
        config.update(extra)
    return config


def get_part(score, name):
    return next(part for part in score.parts if part.partName == name)


def pitches_in_measure(part, number):
    measure = list(part.getElementsByClass(stream.Measure))[number - 1]
    return [n.pitch.midi for n in measure.notes if isinstance(n, note.Note)]


def test_slow_intro_opens_with_cello_and_violin_one_takes_melody(tmp_path):
    config = make_config(tmp_path, structure=[
        {"section": "intro", "measures": [1, 2]},
        {"section": "couplet", "measures": [3, 4, 5, 6, 7, 8]},
    ])
    score, summary = arrange(config)
    cello = get_part(score, "Violoncelle")
    violin_one = get_part(score, "Violon I")
    violin_measures = list(violin_one.getElementsByClass(stream.Measure))
    cello_first = pitches_in_measure(cello, 1)
    assert cello_first
    assert all(36 <= pitch <= 84 for pitch in cello_first)
    assert not violin_measures[0].notes
    assert violin_measures[2].notes
    source_measure_3 = list(get_part(score, "Mélodie principale").getElementsByClass(stream.Measure))[2]
    assert [n.pitch.pitchClass for n in violin_measures[2].notes if isinstance(n, note.Note)] == [
        n.pitch.pitchClass for n in source_measure_3.notes if isinstance(n, note.Note)
    ]
    assert [e.duration.quarterLength for e in violin_measures[2].notesAndRests] == [
        e.duration.quarterLength for e in source_measure_3.notesAndRests
    ]
    source_first = list(get_part(score, "Mélodie principale").getElementsByClass(stream.Measure))[0]
    assert [p % 12 for p in cello_first] == [n.pitch.pitchClass for n in source_first.notes if isinstance(n, note.Note)]
    cello_roles = next(p for p in summary["parties"] if p["nom"] == "Violoncelle")["role_par_section"]
    assert cello_roles["solo"] == [1, 2]


def test_melody_rests_are_preserved_and_supporting_lines_are_distinct(tmp_path):
    score, _ = arrange(make_config(tmp_path))
    melody = get_part(score, "Mélodie principale")
    violin_one = get_part(score, "Violon I")
    violin_two = get_part(score, "Violon II")
    assert len(list(melody.getElementsByClass(stream.Measure))[2].getElementsByClass(note.Rest)) > 0
    assert len(list(violin_one.getElementsByClass(stream.Measure))[2].getElementsByClass(note.Rest)) > 0
    assert pitches_in_measure(violin_two, 1) != pitches_in_measure(violin_one, 1)
    assert len(list(violin_two.recurse().notes)) > 0


def test_chord_tones_voice_leading_and_ranges(tmp_path):
    score, _ = arrange(make_config(tmp_path))
    ranges = {"Violon II": (55, 100), "Alto": (48, 91), "Violoncelle": (36, 84), "Contrebasse": (28, 67)}
    for name, (low, high) in ranges.items():
        part = get_part(score, name)
        for measure in part.getElementsByClass(stream.Measure):
            assert all(low <= n.pitch.midi <= high for n in measure.notes if isinstance(n, note.Note))
    # Les notes d'accompagnement restent dans la grille fournie.
    from music21.harmony import ChordSymbol
    chords = ["C", "Am", "F", "G7", "Dm", "G", "C", "C"]
    for name in ranges:
        part = get_part(score, name)
        for index, measure in enumerate(part.getElementsByClass(stream.Measure)):
            allowed = {p.pitchClass for p in ChordSymbol(chords[index]).pitches}
            assert all(n.pitch.pitchClass in allowed for n in measure.notes if isinstance(n, note.Note))
    # Les voix intérieures ne se croisent pas à l'attaque des mesures du couplet.
    for index in range(2, 8):
        v2 = pitches_in_measure(get_part(score, "Violon II"), index)[0]
        viola = pitches_in_measure(get_part(score, "Alto"), index)[0]
        cello = pitches_in_measure(get_part(score, "Violoncelle"), index)[0]
        bass = pitches_in_measure(get_part(score, "Contrebasse"), index)[0]
        assert v2 > viola > cello > bass
    for name in ranges:
        first_notes = [pitches_in_measure(get_part(score, name), i)[0] for i in range(1, 9)]
        assert all(abs(right - left) <= 12 for left, right in zip(first_notes, first_notes[1:]))


def test_section_roles_and_dynamics_are_configurable(tmp_path):
    structure = [
        {"section": "intro", "measures": [1, 2, 3], "roles_by_measure": {"2": {"Alto": "sustained"}}},
        {"section": "refrain", "measures": [4, 5, 6, 7, 8], "roles": {"Violon II": "repeated notes"}, "dynamic": "ff"},
    ]
    score, summary = arrange(make_config(tmp_path, structure=structure))
    viola = get_part(score, "Alto")
    assert not list(viola.getElementsByClass(stream.Measure))[0].notes
    assert list(viola.getElementsByClass(stream.Measure))[1].notes
    violin_two = get_part(score, "Violon II")
    assert len(list(violin_two.getElementsByClass(stream.Measure))[3].notes) >= 3
    assert list(violin_two.getElementsByClass(stream.Measure))[3].getElementsByClass("Dynamic")[0].value == "ff"
    roles = next(p for p in summary["parties"] if p["nom"] == "Violon II")["role_par_section"]
    assert roles["repeated notes"] == [4, 5, 6, 7, 8]


def test_string_section_can_be_divided_into_independent_parts(tmp_path):
    config = make_config(tmp_path, structure=[{"section": "verse", "measures": list(range(1, 9))}], extra={
        "instruments": {"Violon I": {"count": 4, "parts": ["Violons I A", "Violons I B"]}},
        "orchestration": {"verse": {"roles": {"Violons I A": "main melody", "Violons I B": "harmony"}}},
    })
    score, summary = arrange(config)
    group_a, group_b = get_part(score, "Violons I A"), get_part(score, "Violons I B")
    assert pitches_in_measure(group_a, 1) != pitches_in_measure(group_b, 1)
    assert next(p for p in summary["parties"] if p["nom"] == "Violons I B")["role_par_section"]["harmony"] == list(range(1, 9))


def test_style_cells_and_musicxml_midi_exports(tmp_path):
    classical, _ = arrange(make_config(tmp_path / "classical", style="classique"))
    cinematic, _ = arrange(make_config(tmp_path / "cinematic", style="cinématographique"))
    classical_v2 = list(get_part(classical, "Violon II").getElementsByClass(stream.Measure))[0]
    cinematic_v2 = list(get_part(cinematic, "Violon II").getElementsByClass(stream.Measure))[0]
    assert [(e.duration.quarterLength, isinstance(e, note.Rest)) for e in classical_v2.notesAndRests] != [
        (e.duration.quarterLength, isinstance(e, note.Rest)) for e in cinematic_v2.notesAndRests
    ]
    output = tmp_path / "exports"
    export(cinematic, {"validation": {"issues": []}, "parties": []}, output)
    parsed_score = converter.parse(str(output / "partition_generale.musicxml"))
    parsed_midi = converter.parse(str(output / "arrangement.mid"))
    assert len(parsed_score.parts) == len(cinematic.parts)
    assert len(list(parsed_midi.recurse().notes)) > 0
    for filename in ("violons_1.musicxml", "violons_2.musicxml", "altos.musicxml", "violoncelles.musicxml", "contrebasse.musicxml"):
        assert len(list(converter.parse(str(output / "parties" / filename)).recurse().notes)) > 0


def test_generated_demo_musicxml_midi_and_role_report_are_readable():
    root = Path(__file__).resolve().parents[1] / "examples" / "sortie_demo"
    score = converter.parse(str(root / "partition_generale.musicxml"))
    midi = converter.parse(str(root / "arrangement.mid"))
    assert len(score.parts) >= 16
    assert len(list(score.recurse().notes)) > 0
    assert len(list(midi.recurse().notes)) > 0
    for filename in ("violons_1.musicxml", "violons_2.musicxml", "altos.musicxml", "violoncelles.musicxml", "contrebasse.musicxml"):
        individual = converter.parse(str(root / "parties" / filename))
        assert len(individual.parts) == 1
        assert len(list(individual.recurse().notes)) > 0
    report = json.loads((root / "rapport_validation.json").read_text(encoding="utf-8"))
    summary = json.loads((root / "resume_arrangement.json").read_text(encoding="utf-8"))
    assert report["critical_count"] == 0
    assert next(p for p in summary["parties"] if p["nom"] == "Violoncelle")["role_par_section"]["solo"] == [1, 2]
