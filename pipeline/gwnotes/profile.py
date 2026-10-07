"""Profilo del dispositivo (geometria dello schermo e parametri di impaginazione).

Fonte: Connect IQ Device Reference, vivoactive5 — schermo rotondo 390x390.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Profile:
    id: str = "vivoactive5"
    size: int = 390
    margin: int = 10           # distanza minima del testo dal bordo del cerchio
    top: int = 30              # primo pixel utile (in alto c'è l'indicatore di avanzamento)
    bottom: int = 352          # ultimo pixel utile (sotto c'è il numero di pagina)
    min_line_w: int = 150      # righe più strette di così vengono saltate
    line_gap: int = 3          # interlinea aggiuntiva
    para_gap: int = 8
    heading_gap: int = 12
    indent: int = 20           # rientro per livello (elenchi, riquadri)
    box_bar_w: int = 3
    sub_drop: int = 6
    sup_rise: int = 11
    eq_maxw: int = 300
    inline_maxw: int = 280
    fig_maxw: int = 300
    img_maxh: int = 300
    fit_radius: float = 182.0
    zoom_threshold: float = 0.8
    zoom_max: int = 900
    eq_indent: int = 24
    eq_line_gap: int = 6
    title_w: int = 290         # larghezza delle voci nei menu dell'orologio

    @property
    def r(self) -> float:
        return self.size / 2

    def half_width(self, y: float) -> float:
        dy = y - self.r
        if abs(dy) >= self.r:
            return 0.0
        return math.sqrt(self.r * self.r - dy * dy) - self.margin

    def band(self, top: float, bottom: float) -> tuple[int, int]:
        """(x_sinistra, larghezza) disponibili per una riga che occupa [top, bottom]."""
        hw = min(self.half_width(top), self.half_width(bottom))
        if top <= self.r <= bottom:
            hw = min(hw, self.half_width(self.r))
        if hw <= 0:
            return int(self.r), 0
        return int(math.ceil(self.r - hw)), int(math.floor(2 * hw))

    def to_dict(self):
        return asdict(self)


VIVOACTIVE5 = Profile()
