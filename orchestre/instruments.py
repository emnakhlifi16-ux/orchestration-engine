"""Référentiel d'instruments, tessitures et conventions de transposition.

Les bornes sont en numéros MIDI de sons réels. Les tessitures restent des
repères de validation, pas une garantie de facilité pour chaque instrumentiste.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class InstrumentSpec:
    name: str
    count: int
    comfortable_low: int
    comfortable_high: int
    extreme_low: int
    extreme_high: int
    family: str
    reference_pitch: str = "C"
    transposition_semitones: int = 0  # écrit -> son réel
    technical_notes: tuple[str, ...] = ()
    source_name: str | None = None
    part_index: int = 0

    # Compatibilité avec le prototype précédent.
    @property
    def low(self) -> int:
        return self.extreme_low

    @property
    def high(self) -> int:
        return self.extreme_high

    @property
    def transposition(self) -> int:
        return self.transposition_semitones


INSTRUMENTS = (
    InstrumentSpec("Violon I", 4, 60, 96, 55, 103, "cordes", technical_notes=("arco/pizzicato", "doubles cordes selon faisabilité")),
    InstrumentSpec("Violon II", 4, 55, 91, 55, 100, "cordes", technical_notes=("arco/pizzicato",)),
    InstrumentSpec("Alto", 2, 53, 81, 48, 91, "cordes", technical_notes=("clé d'ut troisième ligne",)),
    InstrumentSpec("Violoncelle", 2, 43, 76, 36, 84, "cordes", technical_notes=("clé de fa, clé de ténor dans l'aigu",)),
    InstrumentSpec("Contrebasse", 1, 36, 60, 28, 67, "cordes", transposition_semitones=-12, technical_notes=("sonne une octave sous l'écrit",)),
    InstrumentSpec("Flûte 1", 1, 67, 88, 60, 96, "bois", technical_notes=("respirations à prévoir",)),
    InstrumentSpec("Flûte 2", 1, 60, 84, 60, 96, "bois", technical_notes=("respirations à prévoir",)),
    InstrumentSpec("Hautbois", 1, 58, 84, 58, 88, "bois", technical_notes=("respirations à prévoir",)),
    InstrumentSpec("Clarinette en Sib", 1, 55, 84, 50, 88, "bois", reference_pitch="Bb", transposition_semitones=-2, technical_notes=("transposition écrite vers son réel: -2 demi-tons",)),
    InstrumentSpec("Trompette en Sib", 1, 60, 77, 55, 82, "cuivres", reference_pitch="Bb", transposition_semitones=-2, technical_notes=("transposition à confirmer selon le modèle", "endurance et respiration")),
    InstrumentSpec("Batterie", 1, 35, 81, 35, 81, "percussions", technical_notes=("notation non transposée recommandée",)),
    InstrumentSpec("Basse électrique", 1, 36, 60, 28, 67, "rythmique", transposition_semitones=-12, technical_notes=("sonne généralement une octave sous l'écrit",)),
    InstrumentSpec("Derbouka", 1, 35, 81, 35, 81, "percussions", technical_notes=("hauteurs MIDI symboliques; notation rythmique à préciser",)),
    InstrumentSpec("Soprano", 1, 64, 77, 60, 81, "voix"),
    InstrumentSpec("Alto choral", 1, 57, 69, 53, 74, "voix"),
    InstrumentSpec("Ténor", 1, 50, 64, 48, 69, "voix"),
    InstrumentSpec("Basse chorale", 1, 43, 57, 40, 62, "voix"),
)


def configured_instruments(config: dict) -> tuple[InstrumentSpec, ...]:
    """Applique les effectifs optionnels sans confondre musiciens et parties.

    `parts` est une liste de noms de parties musicales. Chaque nom reçoit une
    copie de la partie de pupitre dans cette maquette initiale; la future
    écriture pourra donner à ces parties du matériau indépendant.
    """
    from dataclasses import replace
    overrides = config.get("instruments", {})
    result = []
    for spec in INSTRUMENTS:
        entry = overrides.get(spec.name, {})
        if isinstance(entry, int):
            entry = {"count": entry}
        count = entry.get("count", spec.count)
        if not isinstance(count, int) or count < 0:
            raise ValueError(f"Effectif invalide pour {spec.name}: {count!r}")
        part_names = entry.get("parts", [spec.name])
        if not isinstance(part_names, list) or not all(isinstance(n, str) and n.strip() for n in part_names):
            raise ValueError(f"'parts' doit être une liste de noms non vides pour {spec.name}.")
        for part_index, part_name in enumerate(part_names):
            result.append(replace(spec, name=part_name, count=count, source_name=spec.name, part_index=part_index))
    unknown = set(overrides) - {s.name for s in INSTRUMENTS}
    if unknown:
        raise ValueError("Instruments inconnus: " + ", ".join(sorted(unknown)))
    names = [spec.name for spec in result]
    if len(names) != len(set(names)):
        raise ValueError("Chaque partie musicale doit avoir un nom unique pour les exports.")
    return tuple(result)
