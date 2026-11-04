"""Chargement, maquette, validation et exports music21."""
from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from music21 import chord, converter, dynamics, instrument, key, meter, note, stream, tempo
from music21.harmony import ChordSymbol

from .instruments import INSTRUMENTS, InstrumentSpec, configured_instruments
from .strings import STRING_NAMES, generate_strings


def load_config(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    required = ("melody", "chords", "tempo", "meter", "key", "structure")
    missing = [name for name in required if name not in data]
    if missing:
        raise ValueError("Informations manquantes dans la configuration: " + ", ".join(missing))
    if not data["chords"]:
        raise ValueError("Fournissez les accords: aucune harmonie ne sera inventée.")
    if not isinstance(data["tempo"], (int, float)) or data["tempo"] <= 0:
        raise ValueError("'tempo' doit être un nombre positif.")
    if not isinstance(data["chords"], list) or not all(isinstance(c, str) for c in data["chords"]):
        raise ValueError("'chords' doit être une liste de symboles, un par mesure.")
    configured_instruments(data)  # valide les effectifs et les noms de pupitres
    return data


def _read_melody(source: str | Path) -> stream.Part:
    score = converter.parse(str(source))
    parts = list(score.parts)
    if not parts:
        raise ValueError("Le fichier ne contient pas de partie mélodique lisible.")
    part = parts[0]
    if not any(isinstance(el, (note.Note, chord.Chord)) for el in part.recurse().notes):
        raise ValueError("Aucune note trouvée dans la première partie du fichier.")
    return part


def _chord_pitches(symbol: str) -> list[int]:
    try:
        cs = ChordSymbol(symbol)
        return sorted({p.midi for p in cs.pitches})
    except Exception as exc:
        raise ValueError(f"Accord non reconnu par music21: {symbol!r}") from exc


def _nearest_in_range(pitches: list[int], target: int, low: int, high: int) -> int:
    choices = [p + 12 * octave for p in pitches for octave in range(-6, 7) if low <= p + 12 * octave <= high]
    return min(choices, key=lambda p: (abs(p - target), p)) if choices else target


ROLE_BY_NAME = {
    "Violon I": "lead", "Violon II": "pad", "Alto": "pad", "Violoncelle": "bass",
    "Contrebasse": "bass", "Flûte 1": "answer", "Flûte 2": "answer",
    "Hautbois": "answer", "Clarinette en Sib": "pad", "Trompette en Sib": "accent",
    "Batterie": "rest", "Basse électrique": "bass", "Derbouka": "rest",
    "Soprano": "voice", "Alto choral": "voice", "Ténor": "voice", "Basse chorale": "voice",
}
VOICE_TARGET = {"Soprano": 76, "Alto choral": 69, "Ténor": 64, "Basse chorale": 55}


def _instrument_object(spec: InstrumentSpec):
    source_name = spec.source_name or spec.name
    cls = {
        "Violon I": instrument.Violin, "Violon II": instrument.Violin,
        "Alto": instrument.Viola, "Violoncelle": instrument.Violoncello,
        "Contrebasse": instrument.Contrabass, "Flûte 1": instrument.Flute,
        "Flûte 2": instrument.Flute, "Hautbois": instrument.Oboe,
        "Clarinette en Sib": instrument.Clarinet, "Trompette en Sib": instrument.Trumpet,
        "Basse électrique": instrument.ElectricBass,
    }.get(source_name, instrument.Instrument)
    obj = cls()
    obj.instrumentName = spec.name
    obj.partName = spec.name
    # MIDI possède 16 canaux; on réutilise un canal pour les pupitres de
    # même famille/programme et réserve le canal 10 aux percussions.
    obj.midiChannel = {
        "Violon I": 1, "Violon II": 2, "Alto": 3, "Violoncelle": 4,
        "Contrebasse": 5, "Flûte 1": 6, "Flûte 2": 7, "Hautbois": 8,
        "Clarinette en Sib": 9, "Batterie": 10, "Derbouka": 10,
        "Basse électrique": 11, "Soprano": 12, "Alto choral": 12,
        "Ténor": 12, "Basse chorale": 12, "Trompette en Sib": 13,
    }.get(source_name, 14)
    return obj


def arrange(config: dict[str, Any]) -> tuple[stream.Score, dict[str, Any]]:
    melody = _read_melody(config["melody"])
    ts = meter.TimeSignature(config["meter"])
    beats_per_bar = ts.barDuration.quarterLength
    measures = list(melody.getElementsByClass(stream.Measure))
    if not measures:
        melody = deepcopy(melody).flatten()
        melody.insert(0, deepcopy(ts))
        melody = melody.makeMeasures(inPlace=False)
        measures = list(melody.getElementsByClass(stream.Measure))
    chords = config["chords"]
    if len(chords) < len(measures):
        raise ValueError(f"Il faut un accord pour chaque mesure: {len(measures)} mesures, {len(chords)} accords reçus.")
    chord_sets = [_chord_pitches(c) for c in chords[:len(measures)]]

    score = stream.Score(id="Orchestration")
    score.insert(0, tempo.MetronomeMark(number=int(config["tempo"])))
    score.insert(0, ts)
    score.insert(0, key.Key(config["key"]))
    lead = stream.Part(id="Melodie")
    lead.partName = "Mélodie principale"
    lead_instrument = instrument.Violin()
    lead_instrument.midiChannel = 1
    lead.insert(0, lead_instrument)
    lead.insert(0, deepcopy(ts))
    for element in melody.flatten().notesAndRests:
        lead.insert(element.offset, element)
    lead.makeMeasures(inPlace=True)
    score.insert(0, lead)

    part_summaries = [{"nom": "Mélodie principale", "effectif": 1, "role": "mélodie importée"}]
    specs = configured_instruments(config)
    string_parts, string_summaries, string_issues = generate_strings(
        melody, measures, chords[:len(measures)], chord_sets, specs, config.get("structure", []), beats_per_bar, config
    )
    part_summaries.extend(string_summaries)
    for spec in specs:
        if (spec.source_name or spec.name) in STRING_NAMES:
            score.insert(0, string_parts[spec.name])
            continue
        part = stream.Part(id=re.sub(r"\W+", "_", spec.name).strip("_") or "partie")
        part.partName = spec.name
        part.insert(0, _instrument_object(spec))
        role = ROLE_BY_NAME.get(spec.source_name or spec.name, "pad")
        intentional_silences: list[int] = []
        for i, tones in enumerate(chord_sets):
            m = stream.Measure(number=i + 1)
            silent = role == "rest" or (role == "answer" and i % 2 == 0) or (role == "accent" and i % 4 != 3)
            if silent:
                intentional_silences.append(i)
                m.append(note.Rest(quarterLength=beats_per_bar))
            elif role == "bass":
                # Les accords music21 gardent leur fondamentale comme note initiale.
                root = tones[0]
                m.append(note.Note(_nearest_in_range([root], 43, spec.extreme_low, spec.extreme_high), quarterLength=beats_per_bar))
            else:
                target = VOICE_TARGET.get(spec.name, 76 if role == "lead" else 64)
                m.append(note.Note(_nearest_in_range(tones, target, spec.extreme_low, spec.extreme_high), quarterLength=beats_per_bar))
            if i == 0:
                m.insert(0, dynamics.Dynamic("mp"))
            if i == len(chord_sets) - 1:
                m.insert(0, dynamics.Dynamic("f"))
            part.append(m)
        part.editorial.intentional_silent_measures = intentional_silences
        score.insert(0, part)
        part_summaries.append({"nom": spec.name, "effectif": spec.count, "role": role,
                               "partie_musicale": spec.name})

    report = validate_score(score, specs, chord_sets)
    report["issues"].extend(string_issues)
    report["warning_count"] = sum(i["severity"] == "warning" for i in report["issues"])
    report["critical_count"] = sum(i["severity"] == "critical" for i in report["issues"])
    report["status"] = "issues" if report["issues"] else "ok"
    overview = {"mesures": len(measures), "tempo": int(config["tempo"]), "mesure": config["meter"],
                "tonalite": config["key"], "structure": config["structure"],
                "accords": chords[:len(measures)], "parties": part_summaries,
                "validation": report}
    return score, overview


def validate_score(score: stream.Score, specs: tuple[InstrumentSpec, ...], chord_sets: list[list[int]]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    by_name = {spec.name: spec for spec in specs}
    expected = {"Mélodie principale", *(s.name for s in specs)}
    actual = {p.partName for p in score.parts}
    for missing in sorted(expected - actual):
        issues.append({"severity": "critical", "code": "missing_part", "message": f"Partie absente: {missing}"})
    for part in score.parts:
        spec = by_name.get(part.partName)
        notes = list(part.recurse().notes)
        if not notes and len(getattr(part.editorial, "intentional_silent_measures", [])) < len(part.getElementsByClass(stream.Measure)):
            issues.append({"severity": "warning", "code": "empty_part", "message": f"Aucune note dans {part.partName}"})
        if spec:
            for n in notes:
                for p in (n.pitches if isinstance(n, chord.Chord) else [n.pitch]):
                    if not spec.extreme_low <= p.midi <= spec.extreme_high:
                        issues.append({"severity": "warning", "code": "out_of_range", "message": f"{p.nameWithOctave} hors tessiture extrême de {spec.name}"})
                    elif not spec.comfortable_low <= p.midi <= spec.comfortable_high:
                        issues.append({"severity": "warning", "code": "outside_comfortable_range", "message": f"{p.nameWithOctave} hors tessiture confortable de {spec.name}"})
        for measure_index, measure in enumerate(part.getElementsByClass(stream.Measure)):
            string_roles = getattr(part.editorial, "string_roles_by_measure", [])
            intentional = getattr(part.editorial, "intentional_silence", False) or (
                measure_index < len(string_roles) and string_roles[measure_index] == "silence"
            ) or measure_index in getattr(part.editorial, "intentional_silent_measures", [])
            if not measure.notes and not intentional:
                issues.append({"severity": "warning", "code": "empty_measure", "message": f"Mesure {measure.number} sans contenu dans {part.partName}"})
            elif spec and spec.name != "Violon I" and measure.number and measure.number <= len(chord_sets):
                allowed = {p % 12 for p in chord_sets[measure.number - 1]}
                for n in measure.notes:
                    for p in (n.pitches if isinstance(n, chord.Chord) else [n.pitch]):
                        if p.pitchClass not in allowed:
                            issues.append({"severity": "warning", "code": "non_chord_tone", "message": f"{p.nameWithOctave} n'appartient pas à l'accord de la mesure {measure.number} ({part.partName})"})
    transposing = [s.name for s in specs if s.transposition_semitones]
    if transposing:
        issues.append({"severity": "warning", "code": "concert_pitch_parts", "message": "Les exports restent en sons réels; la notation transposée n'est pas encore produite pour: " + ", ".join(transposing)})
    if len(score.parts) > 16:
        issues.append({"severity": "warning", "code": "midi_channel_capacity", "message": f"La partition contient {len(score.parts)} parties; le format MIDI standard limite les canaux à 16. Les fichiers MIDI individuels restent séparés."})
    if not chord_sets:
        issues.append({"severity": "critical", "code": "no_harmony", "message": "Aucune donnée harmonique fournie."})
    return {"status": "issues" if issues else "ok", "critical_count": sum(i["severity"] == "critical" for i in issues),
            "warning_count": sum(i["severity"] == "warning" for i in issues), "issues": issues,
            "checks": ["parties attendues", "tessitures confortables et extrêmes", "mesures vides", "notes étrangères aux accords", "transposition concert pitch explicitée"]}


def _slug(value: str) -> str:
    aliases = {
        "Mélodie principale": "melodie_principale", "Violon I": "violons_1", "Violon II": "violons_2",
        "Alto": "altos", "Violoncelle": "violoncelles", "Contrebasse": "contrebasse",
        "Flûte 1": "flute_1", "Flûte 2": "flute_2", "Hautbois": "hautbois",
        "Clarinette en Sib": "clarinette", "Trompette en Sib": "trompette",
        "Batterie": "batterie", "Basse électrique": "basse_electrique", "Derbouka": "derbouka",
        "Soprano": "soprano", "Alto choral": "alto_vocal", "Ténor": "tenor", "Basse chorale": "basse_vocale",
    }
    if value in aliases:
        return aliases[value]
    value = value.lower().replace("×", " ")
    value = value.replace("é", "e").replace("è", "e").replace("ê", "e").replace("î", "i").replace("û", "u").replace("à", "a").replace("ï", "i")
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_")


def export(score: stream.Score, overview: dict[str, Any], outdir: str | Path) -> None:
    out = Path(outdir)
    parts_dir = out / "parties"
    parts_dir.mkdir(parents=True, exist_ok=True)
    score.write("musicxml", fp=str(out / "partition_generale.musicxml"))
    score.write("midi", fp=str(out / "arrangement.mid"))
    for part in score.parts:
        solo = stream.Score(id=f"Score_{part.id}")
        for context in score.getElementsByClass((tempo.MetronomeMark, meter.TimeSignature, key.Key)):
            solo.insert(0, deepcopy(context))
        copied_part = deepcopy(part)
        solo.insert(0, copied_part)
        base = _slug(part.partName or part.id)
        solo.write("musicxml", fp=str(parts_dir / f"{base}.musicxml"))
        try:
            solo.write("midi", fp=str(parts_dir / f"{base}.mid"))
        except Exception as exc:
            # Certaines percussions n'ont pas encore de convention MIDI dédiée.
            overview.setdefault("validation", {}).setdefault("issues", []).append(
                {"severity": "warning", "code": "individual_midi_export", "message": f"MIDI individuel {base}: {exc}"})
    report = overview.get("validation", {})
    issues = report.setdefault("issues", [])
    report["critical_count"] = sum(i.get("severity") == "critical" for i in issues)
    report["warning_count"] = sum(i.get("severity") == "warning" for i in issues)
    report["status"] = "issues" if issues else "ok"
    (out / "rapport_validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {k: v for k, v in overview.items() if k != "validation"}
    (out / "resume_arrangement.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    # Nom historique conservé pour les consommateurs du prototype précédent.
    (out / "structure.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
