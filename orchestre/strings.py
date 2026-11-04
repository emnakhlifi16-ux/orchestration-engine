"""Première écriture déterministe des cordes à partir de mélodie et d'accords.

Ce module n'invente pas de hauteurs : les mélodies reprennent la source,
et l'accompagnement pioche dans les notes de l'accord fourni pour la mesure.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Iterable

from music21 import articulations, dynamics, instrument, note, stream
from music21.harmony import ChordSymbol

from .instruments import InstrumentSpec


STRING_NAMES = {"Violon I", "Violon II", "Alto", "Violoncelle", "Contrebasse"}
ROLE_NAMES = {
    "main melody", "main_melody", "melodie principale", "mélodie principale", "melodie",
    "countermelody", "contrechant", "harmony", "harmonie", "arpeggio", "arpège",
    "rhythmic accompaniment", "accompagnement rythmique", "repeated notes", "notes répétées",
    "bass foundation", "fondamentale", "basse", "sustained", "notes tenues", "solo", "silence", "rest",
}

SECTION_ALIASES = {
    "couplet": "verse", "refrain": "chorus", "pré-refrain": "prechorus", "pre-refrain": "prechorus",
    "interlude": "interlude", "interlude instrumental": "interlude", "pont": "bridge",
    "final": "final", "finale": "final", "introduction": "intro", "intro": "intro",
    "verse": "verse", "chorus": "chorus", "prechorus": "prechorus", "bridge": "bridge", "solo": "solo",
}

DEFAULT_ROLES = {
    "intro": {"Violoncelle": "solo", "Contrebasse": "silence", "Violon I": "silence", "Violon II": "silence", "Alto": "silence"},
    "verse": {"Violon I": "main melody", "Violon II": "rhythmic accompaniment", "Alto": "sustained", "Violoncelle": "bass foundation", "Contrebasse": "bass foundation"},
    "prechorus": {"Violon I": "main melody", "Violon II": "arpeggio", "Alto": "rhythmic accompaniment", "Violoncelle": "arpeggio", "Contrebasse": "bass foundation"},
    "chorus": {"Violon I": "main melody", "Violon II": "harmony", "Alto": "harmony", "Violoncelle": "arpeggio", "Contrebasse": "bass foundation"},
    "interlude": {"Violon I": "solo", "Violon II": "harmony", "Alto": "sustained", "Violoncelle": "countermelody", "Contrebasse": "bass foundation"},
    "bridge": {"Violon I": "countermelody", "Violon II": "sustained", "Alto": "harmony", "Violoncelle": "solo", "Contrebasse": "silence"},
    "solo": {"Violon I": "silence", "Violon II": "silence", "Alto": "silence", "Violoncelle": "solo", "Contrebasse": "bass foundation"},
    "final": {"Violon I": "main melody", "Violon II": "harmony", "Alto": "harmony", "Violoncelle": "arpeggio", "Contrebasse": "bass foundation"},
}

SECTION_DYNAMICS = {"intro": "p", "verse": "mp", "prechorus": "mf", "chorus": "f", "interlude": "mp", "bridge": "mf", "solo": "mf", "final": "ff"}
STYLE_ALIASES = {"classique": "classical", "cinématographique": "cinematic", "chanson française": "chanson_francaise",
                 "chanson tunisienne": "chanson_tunisienne", "oriental": "oriental", "pop orchestral": "pop_orchestral"}
SUPPORTED_STYLES = {"classical", "cinematic", "chanson_francaise", "pop_orchestral"}


def canonical_section(name: str) -> str:
    lowered = name.strip().lower()
    return SECTION_ALIASES.get(lowered, lowered)


def _section_map(structure: list[dict], measure_count: int) -> tuple[list[str], dict[str, dict], list[dict]]:
    names = ["verse"] * measure_count
    options: dict[str, dict] = {}
    by_measure = [{} for _ in range(measure_count)]
    for section in structure or []:
        if not isinstance(section, dict):
            continue
        section_name = canonical_section(str(section.get("section", "verse")))
        options[section_name] = section
        for number in section.get("measures", []):
            if isinstance(number, int) and 1 <= number <= measure_count:
                names[number - 1] = section_name
                by_measure[number - 1] = section
    return names, options, by_measure


def _normalize_role(role: str) -> str:
    value = role.strip().lower()
    aliases = {"main melody": "main melody", "main_melody": "main melody", "mélodie principale": "main melody",
               "melodie principale": "main melody", "melodie": "main melody", "countermelody": "countermelody",
               "contrechant": "countermelody", "harmony": "harmony", "harmonie": "harmony", "arpeggio": "arpeggio",
               "arpège": "arpeggio", "rhythmic accompaniment": "rhythmic accompaniment", "accompagnement rythmique": "rhythmic accompaniment",
               "repeated notes": "repeated notes", "notes répétées": "repeated notes", "bass foundation": "bass foundation",
               "fondamentale": "bass foundation", "basse": "bass foundation", "sustained": "sustained", "notes tenues": "sustained",
               "solo": "solo", "silence": "silence", "rest": "silence"}
    return aliases.get(value, "")


def _note_elements(measure: stream.Measure) -> list:
    return [deepcopy(el) for el in measure.flatten().notesAndRests]


def _source_for_measure(measures: list[stream.Measure], number: int) -> list:
    if not measures:
        return []
    source = measures[min(max(number, 0), len(measures) - 1)]
    return _note_elements(source)


def _pitch_values(element) -> list[int]:
    if isinstance(element, note.Note):
        return [element.pitch.midi]
    if isinstance(element, note.Rest):
        return []
    if hasattr(element, "pitches"):
        return [p.midi for p in element.pitches]
    return []


def _octave_fit(elements: list, low: int, high: int, target: int) -> list:
    pitches = [p for element in elements for p in _pitch_values(element)]
    if not pitches:
        return elements
    shifts = range(-48, 49, 12)
    valid = [shift for shift in shifts if all(low <= p + shift <= high for p in pitches)]
    if valid:
        shift = min(valid, key=lambda x: abs(sum(pitches) / len(pitches) + x - target))
    else:
        shift = 0
    result = []
    for element in elements:
        if not _pitch_values(element):
            result.append(element)
            continue
        if shift:
            element = element.transpose(shift, inPlace=False)
        if isinstance(element, note.Note) and not low <= element.pitch.midi <= high:
            choices = [element.pitch.midi + s for s in shifts if low <= element.pitch.midi + s <= high]
            if choices:
                element.pitch.midi = min(choices, key=lambda p: abs(p - target))
        result.append(element)
    return result


def _available(tones: list[int], low: int, high: int) -> list[int]:
    return sorted({p + 12 * octave for p in tones for octave in range(-6, 7) if low <= p + 12 * octave <= high})


def _choose(tones: list[int], low: int, high: int, target: int, previous: int | None = None,
            below: int | None = None, above: int | None = None, exclude_pc: set[int] | None = None) -> int:
    candidates = _available(tones, low, high)
    if below is not None:
        candidates = [p for p in candidates if p < below]
    if above is not None:
        candidates = [p for p in candidates if p > above]
    if exclude_pc and len({p % 12 for p in candidates if p % 12 not in exclude_pc}) >= 1:
        candidates = [p for p in candidates if p % 12 not in exclude_pc]
    if not candidates:
        candidates = _available(tones, low, high)
    if not candidates:
        return max(low, min(target, high))
    return min(candidates, key=lambda p: (abs(p - target) + (1.5 * abs(p - previous) if previous is not None else 0), p))


def _chord_root_and_fifth(symbol: str, tones: list[int]) -> tuple[int, int]:
    cs = ChordSymbol(symbol)
    root = cs.root().midi
    fifth_pc = (cs.root().pitchClass + 7) % 12
    fifth = next((p for p in tones if p % 12 == fifth_pc), root + 7)
    return root, fifth


def _section_role(section_name: str, instrument_name: str, part_name: str, section_config: dict,
                  override: dict, measure_number: int) -> str:
    roles = dict(DEFAULT_ROLES.get(section_name, DEFAULT_ROLES["verse"]))
    roles.update(section_config.get("roles", {}) if isinstance(section_config.get("roles", {}), dict) else {})
    roles.update(override.get("roles", {}) if isinstance(override.get("roles", {}), dict) else {})
    for source in (section_config, override):
        by_measure = source.get("roles_by_measure", {}) if isinstance(source, dict) else {}
        measure_roles = by_measure.get(str(measure_number), by_measure.get(measure_number, {})) if isinstance(by_measure, dict) else {}
        if isinstance(measure_roles, dict) and instrument_name in measure_roles:
            roles[instrument_name] = measure_roles[instrument_name]
    chosen = roles.get(part_name, roles.get(instrument_name, "silence"))
    normalized = _normalize_role(str(chosen))
    return normalized or "silence"


def _previous_pupitre_pitch(parts: dict[str, stream.Part], source_name: str, measure_index: int) -> int | None:
    for part in parts.values():
        inst = part.getInstrument(returnDefault=False)
        if inst is not None and inst.instrumentName == source_name:
            measures = list(part.getElementsByClass(stream.Measure))
            if measure_index < len(measures):
                for element in measures[measure_index].notes:
                    values = _pitch_values(element)
                    if values:
                        return values[-1]
    return None


def _style_pattern(style: str, role: str, measure_index: int, beats: float) -> list[tuple[float, int | None, str]]:
    """Retourne une cellule rythmique en durées de noire, avec None pour un silence."""
    if role == "arpeggio":
        count = max(1, int(beats))
        return [(beats / count, i, "") for i in range(count)]
    if role == "repeated notes":
        count = max(2, int(beats * 2 if style == "pop_orchestral" else beats))
        return [(beats / count, i % 2, "") for i in range(count)]
    if role == "countermelody":
        count = max(2, int(beats))
        return [(beats / count, (i * 2 + measure_index) % 4, "") for i in range(count)]
    if role == "rhythmic accompaniment":
        # Deux cellules complémentaires évitent le même motif mécanique à chaque mesure.
        if style == "cinematic":
            unit = 1.0
            count = max(1, int(beats / unit))
            return [(unit, i % 3, "staccato") for i in range(count)] + ([(beats - count * unit, None, "")] if beats > count * unit else [])
        cell_a = [(1.0, 0, "staccato"), (0.5, None, ""), (0.5, 1, "staccato"), (1.0, 2, "staccato"), (1.0, None, "")]
        cell_b = [(0.5, 0, "staccato"), (0.5, 1, "staccato"), (1.0, None, ""), (1.0, 2, "staccato"), (1.0, None, "")]
        raw = cell_a if measure_index % 2 == 0 else cell_b
        result = []
        elapsed = 0.0
        for dur, tone, art in raw:
            if elapsed >= beats:
                break
            dur = min(dur, beats - elapsed)
            result.append((dur, tone, art))
            elapsed += dur
        if elapsed < beats:
            result.append((beats - elapsed, None, ""))
        return result
    return [(beats, 0, "")]


def _make_line(role: str, spec: InstrumentSpec, elements: list, tones: list[int], root_fifth: tuple[int, int],
               beats: float, style: str, measure_index: int, previous: int | None,
               upper_pitch: int | None = None, lower_pitch: int | None = None) -> tuple[list, int | None]:
    if role in {"silence", ""}:
        return [note.Rest(quarterLength=beats)], previous
    if role in {"main melody", "solo"}:
        fitted = _octave_fit(elements, spec.comfortable_low, spec.comfortable_high, (spec.comfortable_low + spec.comfortable_high) // 2)
        return (fitted or [note.Rest(quarterLength=beats)]), next((p for e in reversed(fitted) for p in _pitch_values(e)), previous)
    if role == "bass foundation":
        root, fifth = root_fifth
        bass_alternating = spec.name == "Contrebasse" and style in {"pop_orchestral", "chanson_francaise"}
        values = [root, fifth] if bass_alternating else [root]
        count = len(values)
        dur = beats / count
        line = []
        for idx, value in enumerate(values):
            pitch = _choose([value], spec.extreme_low, spec.extreme_high, (spec.comfortable_low + spec.comfortable_high) // 2,
                            previous=previous, below=upper_pitch, above=lower_pitch)
            line.append(note.Note(pitch, quarterLength=dur))
            previous = pitch
        return line, previous
    if role in {"harmony", "sustained", "arpeggio", "rhythmic accompaniment", "repeated notes", "countermelody"}:
        target = (spec.comfortable_low + spec.comfortable_high) // 2
        root, fifth = root_fifth
        if role == "harmony" and spec.name in {"Violon II", "Alto", "Violoncelle"}:
            preferred = tones[1:]
            pitch_pool = preferred or tones
        elif role in {"rhythmic accompaniment", "repeated notes"}:
            pitch_pool = [tones[1] if len(tones) > 1 else tones[0], tones[-1]]
        elif role == "countermelody":
            pitch_pool = tones
        else:
            pitch_pool = tones
        pattern = _style_pattern(style, role, measure_index, beats)
        line = []
        elapsed = 0.0
        last = previous
        for duration, tone_index, articulation in pattern:
            if duration <= 0:
                continue
            if tone_index is None:
                line.append(note.Rest(quarterLength=duration))
            else:
                source_pitch = pitch_pool[tone_index % len(pitch_pool)]
                pitch = _choose([source_pitch], spec.extreme_low, spec.extreme_high, target,
                                previous=last, below=upper_pitch, above=lower_pitch)
                new_note = note.Note(pitch, quarterLength=duration)
                if articulation == "staccato":
                    new_note.articulations.append(articulations.Staccato())
                line.append(new_note)
                last = pitch
            elapsed += duration
        return line or [note.Rest(quarterLength=beats)], last
    return [note.Rest(quarterLength=beats)], previous


def generate_strings(melody: stream.Part, measures: list[stream.Measure], chord_symbols: list[str],
                     chord_sets: list[list[int]], specs: tuple[InstrumentSpec, ...], structure: list[dict],
                     beats_per_bar: float, config: dict) -> tuple[dict[str, stream.Part], list[dict], list[dict]]:
    string_specs = [s for s in specs if (s.source_name or s.name) in STRING_NAMES]
    measure_count = len(chord_sets)
    section_names, section_options, section_by_measure = _section_map(structure, measure_count)
    style_in = str(config.get("style", "classique"))
    style = STYLE_ALIASES.get(style_in.lower(), style_in.lower().replace(" ", "_"))
    issues: list[dict] = []
    if style not in SUPPORTED_STYLES:
        issues.append({"severity": "warning", "code": "style_profile_limited", "message": f"Le style {style_in!r} n'a pas encore de motif dédié; les cordes utilisent des motifs harmoniques génériques."})
        style = "classical"
    if style_in.lower() in {"oriental", "chanson tunisienne"}:
        issues.append({"severity": "warning", "code": "modal_material_required", "message": f"Le style {style_in!r} n'invente pas de maqam: fournissez des accords et des hauteurs mélodiques adaptés."})

    parts: dict[str, stream.Part] = {}
    summaries: list[dict] = []
    previous: dict[str, int | None] = {s.name: None for s in string_specs}
    for spec in string_specs:
        source_name = spec.source_name or spec.name
        part = stream.Part(id=spec.name.replace(" ", "_"))
        part.partName = spec.name
        instrument_cls = {"Violon I": instrument.Violin, "Violon II": instrument.Violin, "Alto": instrument.Viola,
                          "Violoncelle": instrument.Violoncello, "Contrebasse": instrument.Contrabass}[source_name]
        inst = instrument_cls()
        inst.instrumentName = source_name
        inst.partName = spec.name
        inst.midiChannel = {"Violon I": 1, "Violon II": 2, "Alto": 3, "Violoncelle": 4, "Contrebasse": 5}[source_name]
        part.insert(0, inst)
        role_log: dict[str, list[int]] = {}
        role_by_measure: list[str] = []
        for i, (section_name, tones, symbol) in enumerate(zip(section_names, chord_sets, chord_symbols)):
            section_cfg = section_by_measure[i] or section_options.get(section_name, {})
            role = _section_role(section_name, source_name, spec.name, section_cfg,
                                 config.get("orchestration", {}).get(section_name, {}), i + 1)
            if source_name not in STRING_NAMES:
                role = "silence"
            source_elements = _source_for_measure(measures, i)
            root_fifth = _chord_root_and_fifth(symbol, tones)
            upper = None
            lower = None
            # Conserve l'ordre vertical usuel entre pupitres quand tous jouent.
            if source_name == "Violon II":
                upper = next((p for e in source_elements for p in _pitch_values(e)), None) if section_name != "intro" else None
            elif source_name == "Alto":
                upper = _previous_pupitre_pitch(parts, "Violon II", i) if section_name != "intro" else None
            elif source_name == "Violoncelle":
                upper = _previous_pupitre_pitch(parts, "Alto", i) if section_name not in {"intro", "solo"} else None
            elif source_name == "Contrebasse":
                upper = _previous_pupitre_pitch(parts, "Violoncelle", i) if section_name not in {"intro", "solo"} else None
            line, last_pitch = _make_line(role, spec, source_elements, tones, root_fifth, beats_per_bar, style, i,
                                          previous.get(spec.name), upper_pitch=upper, lower_pitch=lower)
            previous[spec.name] = last_pitch
            m = stream.Measure(number=i + 1)
            for element in line:
                m.append(element)
            dynamics_name = section_cfg.get("dynamic") or SECTION_DYNAMICS.get(section_name, "mp")
            if i == 0 or section_names[i - 1] != section_name:
                m.insert(0, dynamics.Dynamic(dynamics_name))
            part.append(m)
            role_log.setdefault(role, []).append(i + 1)
            role_by_measure.append(role)
        part.editorial.string_roles_by_measure = role_by_measure
        parts[spec.name] = part
        summaries.append({"nom": spec.name, "effectif": spec.count, "role_par_section": role_log,
                          "famille": "cordes", "style": style_in})
    return parts, summaries, issues
