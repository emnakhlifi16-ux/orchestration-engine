# Assistant d'orchestration musicale

## État du projet

**Ce projet est en cours de développement.** Il s'agit d'un prototype Python construit avec `music21`. L'écriture des cordes est une première maquette musicale ; les bois, cuivres, percussions et voix utilisent encore la génération simplifiée des premières étapes. Le projet évoluera par familles instrumentales.

## Fonctionnalités actuellement disponibles

- Lecture d'une mélodie en MusicXML ou MIDI, à partir de sa première partie.
- Grille d'accords fournie explicitement, avec un symbole par mesure. Le programme ne complète pas une harmonie absente.
- Configuration du tempo, de la mesure, de la tonalité et de la structure.
- Écriture déterministe des cordes à partir de la mélodie et des accords : reprise de la mélodie aux violons 1, motifs de soutien distincts, rôles et silences par section ou par mesure, et première conduite des voix dans les tessitures indiquées.
- Configuration des effectifs et possibilité de nommer plusieurs parties au sein d'un pupitre, avec rôles distincts.
- Exports d'une partition générale MusicXML, d'un MIDI général, d'un MusicXML et d'un MIDI individuels par partie, d'un rapport de validation et d'un résumé des rôles.
- Exemple musical autonome dans `examples/`, avec les fichiers générés dans `examples/sortie_demo/`.

Les rôles orchestraux reconnus comprennent `main melody`, `countermelody`, `harmony`, `arpeggio`, `rhythmic accompaniment`, `repeated notes`, `bass foundation`, `sustained`, `solo` et `silence`. Les styles classique, cinématographique, chanson française et pop orchestrale disposent de quelques cellules rythmiques déterministes. Les styles oriental et tunisien n'ont pas encore de motifs modaux dédiés ; le moteur s'en tient aux notes fournies.

## Installation

Depuis la racine du dépôt, avec Python 3.10 ou plus récent :

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Utilisation

La configuration de démonstration référence une mélodie incluse dans le dépôt. Depuis la racine :

```powershell
orchestre examples/arrangement_demo.json --out output
```

Pour recréer à la fois la mélodie de démonstration et ses exports versionnés :

```powershell
py examples/generate_demo.py
```

Une configuration doit fournir les chemins de mélodie, les accords (un par mesure), le tempo, la mesure, la tonalité et la structure. Exemple de configuration d'effectifs et de parties divisées :

```json
{
  "instruments": {
    "Violon I": {"count": 4, "parts": ["Violons I A", "Violons I B"]},
    "Violoncelle": {"count": 2, "parts": ["Violoncelle 1", "Violoncelle 2"]}
  },
  "orchestration": {
    "couplet": {
      "roles": {
        "Violons I A": "main melody",
        "Violons I B": "harmony"
      }
    }
  }
}
```

Les effectifs (`count`) désignent le nombre de musiciens ; les noms dans `parts` désignent les parties musicales. Les rôles peuvent être adaptés dans `structure` avec `roles`, `roles_by_measure` et `dynamic`. Les chemins relatifs des fichiers MusicXML/MIDI sont résolus depuis le répertoire courant.

Les exports comprennent `partition_generale.musicxml`, `arrangement.mid`, `rapport_validation.json`, `resume_arrangement.json`, `structure.json` (nom historique) et le dossier `parties/`. Le rapport distingue les erreurs critiques des avertissements et ne bloque pas la génération pour chaque avertissement.

## Tests

Installez les dépendances de développement avec `python -m pip install -e ".[dev]"`, puis exécutez :

```powershell
python -m pytest
```

Les tests créent des mélodies locales et vérifient les entrées MusicXML/MIDI, les exports, le contenu des parties, les silences, les tessitures, les rôles par section, les pupitres divisés, les motifs rythmiques et la lisibilité de l'exemple généré.

## Fonctionnalités prévues et limites

Les éléments suivants ne sont **pas encore implémentés** ou ne sont que partiellement couverts :

- Une orchestration avancée des bois, cuivres, percussions et de la chorale SATB.
- Des contrechants plus développés, des notes de passage, appoggiatures, ornements, doubles cordes, pizzicatos et trémolos.
- Des crescendos et diminuendos progressifs, au-delà des changements de dynamique aux frontières de sections.
- La notation écrite transposée pour clarinette, trompette, contrebasse et basse électrique. Les tessitures du référentiel sont des repères approximatifs en sons réels.
- Une validation musicale plus poussée : les croisements de voix, la surcharge et les difficultés techniques ne sont pas encore contrôlés de façon complète.
- Des motifs orientaux ou tunisiens fondés sur un maqam. Les hauteurs et accords doivent être fournis par l'utilisateur.
- Une vérification directe des partitions dans MuseScore. Les fichiers MusicXML de l'exemple ont été relus avec `music21`, mais MuseScore n'est pas disponible dans l'environnement de développement actuel.

Les notes et motifs générés par la maquette des cordes sont déterministes et s'appuient sur la mélodie ou les accords donnés ; ils ne sont pas tirés au hasard.
