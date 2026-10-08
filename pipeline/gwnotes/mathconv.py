"""Conversione di formule TeX "semplici" in testo ricco (Unicode + stili).

Se la formula contiene costrutti non rappresentabili in una riga di testo
(matrici, \\underbrace, ambienti, caratteri assenti nel font...) viene sollevata
`Unconvertible` e la pipeline la renderizza come immagine.
Le regole utente (`pipeline/rules.yaml`, sezione `math_symbols`) estendono le tabelle.
"""
from __future__ import annotations

import re

from .rich import Styled, normalize, plain

# ------------------------------------------------------------------ tabelle

GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ϵ", "varepsilon": "ε",
    "zeta": "ζ", "eta": "η", "theta": "θ", "vartheta": "ϑ", "iota": "ι", "kappa": "κ",
    "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ", "omicron": "ο", "pi": "π", "varpi": "ϖ",
    "rho": "ρ", "varrho": "ϱ", "sigma": "σ", "varsigma": "ς", "tau": "τ", "upsilon": "υ",
    "phi": "ϕ", "varphi": "φ", "chi": "χ", "psi": "ψ", "omega": "ω",
    "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ", "Pi": "Π",
    "Sigma": "Σ", "Upsilon": "Υ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
}

SYMBOLS = {
    "times": "×", "cdot": "·", "cdots": "⋯", "ldots": "…", "dots": "…", "vdots": "⋮",
    "pm": "±", "mp": "∓", "div": "÷", "ast": "∗", "star": "∗", "circ": "∘", "bullet": "•",
    "to": "→", "rightarrow": "→", "leftarrow": "←", "gets": "←", "uparrow": "↑", "downarrow": "↓",
    "leftrightarrow": "↔", "updownarrow": "↕", "Rightarrow": "⇒", "Leftarrow": "⇐",
    "Leftrightarrow": "⇔", "Uparrow": "⇑", "Downarrow": "⇓", "longrightarrow": "⟶",
    "longleftarrow": "⟵", "Longrightarrow": "⟹", "Longleftarrow": "⟸", "Longleftrightarrow": "⟺",
    "iff": "⟺", "implies": "⟹", "mapsto": "↦", "nearrow": "↗", "searrow": "↘",
    "le": "≤", "leq": "≤", "ge": "≥", "geq": "≥", "ne": "≠", "neq": "≠", "ll": "≪", "gg": "≫",
    "simeq": "≃", "cong": "≅", "approx": "≈", "sim": "∼", "equiv": "≡", "propto": "∝",
    "prec": "≺", "succ": "≻", "doteq": "≐",
    "in": "∈", "notin": "∉", "ni": "∋", "subset": "⊂", "supset": "⊃", "subseteq": "⊆",
    "supseteq": "⊇", "cap": "∩", "cup": "∪", "setminus": "∖", "emptyset": "∅", "varnothing": "∅",
    "forall": "∀", "exists": "∃", "neg": "¬", "lnot": "¬", "land": "∧", "wedge": "∧", "lor": "∨", "vee": "∨",
    "infty": "∞", "partial": "∂", "nabla": "∇", "angle": "∠", "measuredangle": "∡",
    "parallel": "∥", "nparallel": "∦", "perp": "⊥", "oplus": "⊕", "otimes": "⊗", "odot": "⊙",
    "therefore": "∴", "because": "∵",
    "sum": "∑", "prod": "∏", "int": "∫", "iint": "∬", "oint": "∮",
    "langle": "⟨", "rangle": "⟩", "lfloor": "⌊", "rfloor": "⌋", "lceil": "⌈", "rceil": "⌉",
    "ell": "ℓ", "hbar": "ℏ", "Re": "ℜ", "Im": "ℑ", "wp": "℘", "imath": "ı", "jmath": "ȷ",
    "prime": "′", "degree": "°", "S": "§", "P": "¶", "blacksquare": "■", "square": "□",
    "checkmark": "✓", "lvert": "|", "rvert": "|", "vert": "|", "mid": "|", "lVert": "‖",
    "rVert": "‖", "Vert": "‖", "|": "‖", "{": "{", "}": "}", "%": "%", "#": "#", "&": "&",
    "_": "_", "$": "$", "colon": ":", "coloneqq": "≔", "triangleq": "≝",
    "lbrace": "{", "rbrace": "}", "lbrack": "[", "rbrack": "]", "backslash": "\\",
    "oplus": "⊕", "AA": "Å",
}

FUNCTIONS = {
    "sin", "cos", "tan", "cot", "sec", "csc", "arcsin", "arccos", "arctan", "sinh", "cosh", "tanh",
    "ln", "log", "exp", "max", "min", "det", "lim", "sup", "inf", "deg", "dim", "ker", "arg",
    "gcd", "Pr", "tr", "sgn", "sign",
}

SPACES = {",": " ", ";": " ", ":": " ", " ": " ", "quad": "  ", "qquad": "   ", "!": "", "enspace": " ",
          "thinspace": " ", "medspace": " ", "thickspace": " ", "nobreakspace": " "}

IGNORED = {"displaystyle", "textstyle", "scriptstyle", "scriptscriptstyle", "limits", "nolimits",
           "big", "Big", "bigg", "Bigg", "bigl", "bigr", "Bigl", "Bigr", "biggl", "biggr", "Biggl", "Biggr",
           "left", "right", "middle", "nonumber", "notag", "allowbreak", "mathstrut", "strut", "relax"}

ACCENTS = {"hat": "hat", "widehat": "hat", "dot": "dot", "ddot": "ddot", "tilde": "tilde",
           "widetilde": "tilde", "bar": "bar", "overline": "bar", "vec": "vec",
           "overrightarrow": "vec", "underline": "ul", "underrightarrow": "uarr"}

TEXTCMDS = {"text", "textrm", "textup", "mathrm", "operatorname", "mbox", "textnormal", "mathsf",
            "textsf", "texttt", "mathtt", "mathit", "textit", "emph", "textsl", "mathnormal"}
BOLDCMDS = {"mathbf", "boldsymbol", "bm", "textbf", "pmb", "mathbfit"}

CALLIGRAPHIC = {"E": "ℰ", "F": "ℱ", "H": "ℋ", "I": "ℐ", "L": "ℒ", "M": "ℳ", "R": "ℛ", "B": "ℬ", "e": "ℯ"}

UNSUPPORTED = {"frac_too_deep", "begin", "end", "underbrace", "overbrace", "underset", "overset",
               "stackrel", "xrightarrow", "xleftarrow", "boxed", "cancel", "substack", "binom",
               "cfrac", "phantom", "hphantom", "vphantom", "smash", "sideset", "tag", "label",
               "overleftarrow", "array", "matrix", "pmatrix", "bmatrix", "cases", "atop", "choose",
               "color", "textcolor", "hline"}


class Unconvertible(Exception):
    pass


class _Func(str):
    """Nome di funzione (sin, max...): spaziato rispetto agli operandi."""


# ------------------------------------------------------------------ tokenizer

TOKEN_RE = re.compile(r"\\([a-zA-Z]+)\*?|\\(.)|([{}^_&~'])|(\s+)|(.)", re.S)


def tokenize(tex: str):
    toks = []
    for m in TOKEN_RE.finditer(tex):
        if m.group(1):
            toks.append(("cmd", m.group(1)))
        elif m.group(2) is not None:
            toks.append(("cmd", m.group(2)))
        elif m.group(3):
            toks.append(("sp", m.group(3)))
        elif m.group(4):
            toks.append(("ws", " "))
        else:
            toks.append(("ch", m.group(5)))
    return toks


class _Parser:
    def __init__(self, tex: str, extra_symbols: dict | None = None, text_mode_cb=None):
        self.toks = tokenize(tex)
        self.i = 0
        self.frac_depth = 0
        self.sym = dict(SYMBOLS)
        if extra_symbols:
            self.sym.update(extra_symbols)
        self.text_mode_cb = text_mode_cb

    # -- primitive
    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else None

    def take(self):
        t = self.peek()
        self.i += 1
        return t

    def skip_ws(self):
        while self.peek() and self.peek()[0] == "ws":
            self.i += 1

    def raw_group(self) -> str:
        """Legge un argomento come testo TeX grezzo (per \\text{...})."""
        self.skip_ws()
        t = self.take()
        if t is None:
            raise Unconvertible("argomento mancante")
        if t == ("sp", "{"):
            depth, out = 1, []
            while True:
                t = self.take()
                if t is None:
                    raise Unconvertible("graffa non chiusa")
                if t == ("sp", "{"):
                    depth += 1
                elif t == ("sp", "}"):
                    depth -= 1
                    if depth == 0:
                        break
                out.append(_untok(t))
            return "".join(out)
        return _untok(t)

    def optional_arg(self):
        self.skip_ws()
        if self.peek() == ("ch", "["):
            self.take()
            out = []
            depth = 0
            while True:
                t = self.take()
                if t is None:
                    raise Unconvertible("argomento opzionale non chiuso")
                if t == ("ch", "]") and depth == 0:
                    break
                if t == ("sp", "{"):
                    depth += 1
                if t == ("sp", "}"):
                    depth -= 1
                out.append(_untok(t))
            return "".join(out)
        return None

    # -- grammatica
    def parse_list(self, stop_at_brace=False):
        out = []
        while True:
            t = self.peek()
            if t is None:
                if stop_at_brace:
                    raise Unconvertible("graffa non chiusa")
                return out
            if t == ("sp", "}"):
                if stop_at_brace:
                    self.take()
                    return out
                raise Unconvertible("graffa chiusa in eccesso")
            if t in (("sp", "^"), ("sp", "_")):
                self.take()
                kind = "sup" if t[1] == "^" else "sub"
                arg = self.script_arg()
                if kind == "sup" and arg in (["°"], ["′"], ["″"]):
                    out.extend(arg)
                else:
                    out.append(_script(kind, arg))
                continue
            if t == ("sp", "'"):
                self.take()
                out.append("′")
                continue
            out.extend(self.atom())

    def script_arg(self):
        self.skip_ws()
        t = self.peek()
        if t is None:
            raise Unconvertible("apice/pedice senza argomento")
        if t == ("cmd", "circ"):
            self.take()
            return ["°"]
        if t == ("cmd", "prime"):
            self.take()
            return ["′"]
        if t == ("sp", "{"):
            self.take()
            inner = self.parse_list(stop_at_brace=True)
            p = plain(inner)
            if p == "∘":
                return ["°"]
            if p and set(p) == {"′"}:
                return ["″" if len(p) == 2 else p]
            return inner
        return self.atom()

    def arg(self):
        self.skip_ws()
        t = self.peek()
        if t is None:
            raise Unconvertible("argomento mancante")
        if t == ("sp", "{"):
            self.take()
            return self.parse_list(stop_at_brace=True)
        return self.atom()

    def atom(self):
        t = self.take()
        kind, val = t
        if kind == "ws":
            return []
        if kind == "sp":
            if val == "{":
                return self.parse_list(stop_at_brace=True)
            if val == "~":
                return [" "]
            if val == "&":
                raise Unconvertible("allineamento &")
            raise Unconvertible(f"token {val}")
        if kind == "ch":
            if val == "-":
                return ["−"]
            if val == "*":
                return ["∗"]
            return [val]
        return self.command(val)

    def command(self, name: str):
        if name in UNSUPPORTED:
            raise Unconvertible(f"\\{name}")
        if name == "\\":
            raise Unconvertible("a capo")
        if name in GREEK:
            return [GREEK[name]]
        if name in self.sym:
            return [self.sym[name]]
        if name in SPACES:
            return [SPACES[name]] if SPACES[name] else []
        if name in IGNORED:
            if name in ("left", "right", "middle"):
                self.skip_ws()
                t = self.take()
                if t is None:
                    raise Unconvertible("delimitatore mancante")
                if t == ("ch", "."):
                    return []
                if t[0] == "cmd":
                    return self.command(t[1])
                return [t[1]]
            return []
        if name in FUNCTIONS:
            return [_Func(name)]
        if name in ("frac", "dfrac", "tfrac"):
            self.frac_depth += 1
            if self.frac_depth > 2:
                raise Unconvertible("frazioni annidate")
            num = self.arg()
            den = self.arg()
            self.frac_depth -= 1
            return _wrap(num, "num") + ["/"] + _wrap(den, "den")
        if name == "sqrt":
            idx = self.optional_arg()
            body = self.arg()
            out = []
            if idx:
                out.append(Styled("sup", [idx]))
            out.append("√")
            out.extend(_wrap(body, "sqrt"))
            return out
        if name in ACCENTS:
            body = self.arg()
            k = ACCENTS[name]
            if k == "ul" and len(body) == 1 and isinstance(body[0], Styled) and body[0].kind == "ul":
                return [Styled("uul", body[0].children)]
            return [Styled(k, body)]
        if name in BOLDCMDS:
            return [Styled("bold", self.arg())]
        if name in TEXTCMDS:
            raw = self.raw_group()
            if self.text_mode_cb:
                return self.text_mode_cb(raw)
            return [_text_mode(raw)]
        if name == "mathcal" or name == "mathscr":
            body = plain(self.arg())
            return ["".join(CALLIGRAPHIC.get(c, c) for c in body)]
        if name == "mathbb":
            return [Styled("bold", self.arg())]
        if name == "not":
            self.skip_ws()
            t = self.take()
            if t in (("ch", "="),):
                return ["≠"]
            if t == ("cmd", "in"):
                return ["∉"]
            raise Unconvertible("\\not")
        raise Unconvertible(f"\\{name} sconosciuto")


def _untok(t) -> str:
    kind, val = t
    if kind == "cmd":
        return "\\" + val + (" " if val.isalpha() else "")
    return val


def _text_mode(raw: str) -> str:
    s = raw.replace("~", " ").replace("--", "–")
    s = re.sub(r"\\([,;: ])", " ", s)
    if "\\" in s or "$" in s:
        raise Unconvertible("comando in \\text")
    return s


def _script(kind, arg):
    return Styled(kind, list(arg))


_OPS_NUM = set("+−-±∓=<>≤≥≈≃,;/")
_OPS_DEN = _OPS_NUM | set("·×/ ")


def _wrap(nodes, where):
    p = plain([n for n in nodes if not (isinstance(n, Styled) and n.kind in ("sub", "sup"))]).strip()
    nodes = normalize(nodes)
    if where == "sqrt":
        need = len(p) > 1 and not p.isdigit()
    elif where == "num":
        need = any(c in _OPS_NUM for c in p)
    else:
        need = any(c in _OPS_DEN for c in p) or _has_two_factors(p)
    if need:
        return ["("] + nodes + [")"]
    return nodes


def _has_two_factors(p: str) -> bool:
    # "2a" al denominatore è ambiguo: μ/(2a) è più chiaro di μ/2a ("dt" invece resta dt)
    return any(c.isdigit() for c in p) and any(not c.isdigit() and c not in ".," for c in p)


def convert(tex: str, charset: set | None = None, extra_symbols: dict | None = None, text_mode_cb=None):
    """TeX (senza $) -> nodi ricchi. Solleva Unconvertible."""
    p = _Parser(tex, extra_symbols, text_mode_cb)
    nodes = normalize(_space_functions(p.parse_list()))
    _check_depth(nodes, 0)
    if charset is not None:
        from .rich import chars

        missing = {c for c in chars(nodes) if c not in charset and c != " "}
        if missing:
            raise Unconvertible("caratteri non nel font: " + "".join(sorted(missing)))
    return nodes


def _space_functions(nodes):
    out = []
    for i, n in enumerate(nodes):
        if isinstance(n, Styled):
            n = Styled(n.kind, _space_functions(n.children), n.param)
        out.append(n)
    res = []
    for i, n in enumerate(out):
        if isinstance(n, _Func):
            prev = res[-1] if res else None
            if isinstance(prev, Styled) or (isinstance(prev, str) and prev and (prev[-1].isalnum() or prev[-1] in ")′")):
                res.append(" ")
            res.append(str(n))
            nxt = out[i + 1] if i + 1 < len(out) else None
            if isinstance(nxt, Styled) and nxt.kind in ("sub", "sup"):
                # max_i x: spazio dopo il pedice
                res.append(nxt)
                out[i + 1] = None
                nxt = out[i + 2] if i + 2 < len(out) else None
            if nxt is not None and not (isinstance(nxt, str) and (nxt[:1] in "( " or not nxt)):
                res.append(" ")
            continue
        if n is not None:
            res.append(n)
    return res


def _check_depth(nodes, depth):
    for n in nodes:
        if isinstance(n, Styled):
            d = depth + (1 if n.kind in ("sub", "sup") else 0)
            if d > 2:
                raise Unconvertible("pedici annidati troppo in profondità")
            _check_depth(n.children, d)
