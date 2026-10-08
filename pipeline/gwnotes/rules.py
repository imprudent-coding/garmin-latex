"""Regole configurabili della conversione (pipeline/rules.yaml)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .paths import PIPELINE_ROOT

DEFAULT_RULES = PIPELINE_ROOT / "rules.yaml"


@dataclass
class Rules:
    # ridefinizioni di macro valide solo per la versione orologio: nome -> {args, body}
    macros: dict = field(default_factory=dict)
    # macro di sezionamento dichiarate a mano: nome -> {level, args, title, label, labeltext}
    structure: dict = field(default_factory=dict)
    # macro da NON considerare di sezionamento anche se contengono \addcontentsline
    ignore_structure: list = field(default_factory=list)
    # ambienti / macro da compilare con LaTeX e mostrare come immagine
    image_envs: list = field(default_factory=list)
    image_macros: dict = field(default_factory=dict)
    # ambienti \newenvironment da espandere invece di trattarli come riquadri
    expand_envs: list = field(default_factory=list)
    # simboli matematici extra: nome comando (senza \) -> testo Unicode
    math_symbols: dict = field(default_factory=dict)
    # titolo dei riquadri (sovrascrive quello letto da \newtcolorbox)
    box_titles: dict = field(default_factory=dict)
    # titolo del capitolo per il contenuto prima del primo capitolo
    front_title: str = "Introduzione"
    # parametri del bundle
    chunk_bytes: int = 1800
    # risoluzione di rendering: pixel per em del testo LaTeX (≈ dimensione del font body)
    math_px_per_em: float = 25.0
    figure_zoom_dpi: int = 130

    @classmethod
    def load(cls, path: Path | None = None) -> "Rules":
        path = path or DEFAULT_RULES
        if not path.exists():
            return cls()
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        known = set(cls.__dataclass_fields__)
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"{path.name}: chiavi sconosciute: {', '.join(sorted(unknown))}")
        return cls(**{k: v for k, v in data.items() if v is not None})
