#!/usr/bin/env python3
"""Generate all the figures of teoria/ (vector PDF, readable in black and white).

Every quantitative figure is computed from the formulas of the lecture notes
(latex_notes/): conics from r = p/(1+e cos), ground tracks from Kepler's equation,
zero-velocity curves from the CR3BP potential Omega, polhodes from the momentum
sphere and the energy ellipsoid, etc.

Usage:  cd teoria/figures/src && python3 make_figures.py      (writes ../*.pdf)
"""
import os
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, Arc, Polygon

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
plt.rcParams.update({
    "font.family": "serif",
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{amsmath,amssymb}",
    "font.size": 9,
    "axes.linewidth": 0.6,
    "lines.linewidth": 1.0,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
    "hatch.linewidth": 0.4,
})
K = "black"
G = "0.55"      # mid grey
LG = "0.85"     # light grey (forbidden regions, Earth)


def save(fig, name):
    fig.savefig(os.path.join(OUT, name))
    plt.close(fig)
    print("wrote", name)


def arrow(ax, p, q, lw=1.0, color=K, ms=8, ls="-", **kw):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=ms,
                                 lw=lw, color=color, linestyle=ls,
                                 shrinkA=0, shrinkB=0, **kw))


def clean(ax):
    ax.set_aspect("equal")
    ax.axis("off")


def conic(p, e, th_peri=0.0, n=2000, rmax=1e9):
    """Points of r = p/(1+e cos(th-th_peri)), clipped to r<=rmax."""
    if e < 1:
        th = np.linspace(0, 2 * np.pi, n)
    else:
        tm = np.arccos(-1 / e) - 1e-3
        th = np.linspace(-tm, tm, n)
    r = p / (1 + e * np.cos(th))
    r = np.where(r > rmax, np.nan, r)
    return r * np.cos(th + th_peri), r * np.sin(th + th_peri)


# ---------------------------------------------------------------- Chapter 2
def fig_vhoriz():
    """Trajectories from P0 (r0=1, mu=1) with horizontal velocity v0."""
    fig, ax = plt.subplots(figsize=(5.6, 3.6))
    vI, vII = 1.0, np.sqrt(2.0)
    cases = [(0.70, "(b) $0<v_0<v_I$", (0, (4, 2))),
             (1.00, "(c) $v_0=v_I$", "-"),
             (1.25, "(d) $v_I<v_0<v_{II}$", (0, (1, 1.2))),
             (vII, "(e) $v_0=v_{II}$", (0, (6, 2, 1, 2))),
             (1.75, "(f) $v_0>v_{II}$", (0, (2, 2)))]
    for v, lab, ls in cases:
        p = v * v                       # h = r0 v0, p = h^2/mu
        e = abs(p - 1.0)
        thp = 0.0 if v >= 1 else np.pi  # P0 is periapsis if v>=vI, apoapsis otherwise
        x, y = conic(p, e, thp, rmax=7)
        x = x - 0.0
        ax.plot(x, y, color=K, ls=ls, lw=1.0, label=lab)
    ax.plot([0, 1], [0, 0], color=K, lw=1.6, label="(a) $v_0=0$ (rectilinear)")
    ax.add_patch(Circle((0, 0), 0.08, color=LG, ec=K, lw=0.6, zorder=3))
    ax.text(-0.12, -0.25, "$B$", ha="center")
    ax.plot(1, 0, "o", color=K, ms=3, zorder=4)
    ax.text(1.05, -0.28, "$P_0$")
    arrow(ax, (1, 0), (1, 0.6), lw=1.2)
    ax.text(1.06, 0.45, r"$\underline{v}_0\perp\underline{r}$")
    ax.set_xlim(-3.2, 4.5)
    ax.set_ylim(-2.7, 2.7)
    clean(ax)
    ax.legend(loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=7.5, frameon=False, handlelength=3.2)
    save(fig, "vhoriz.pdf")


def fig_conics():
    """Conics with the same periapsis radius, different e."""
    fig, ax = plt.subplots(figsize=(4.6, 3.0))
    rp = 1.0
    for e, lab, ls in [(0.0, "$e=0$ circle", "-"), (0.5, "$0<e<1$ ellipse", (0, (4, 2))),
                       (1.0, "$e=1$ parabola", (0, (6, 2, 1, 2))), (1.6, "$e>1$ hyperbola", (0, (1.5, 1.5)))]:
        x, y = conic(rp * (1 + e), e, 0.0, rmax=6)
        ax.plot(x, y, color=K, ls=ls, label=lab)
    ax.add_patch(Circle((0, 0), 0.07, color=K))
    ax.text(-0.25, 0.12, "$F$")
    ax.plot([0, 1], [0, 0], color=G, lw=0.6)
    ax.text(0.5, -0.22, "$r_p$", ha="center")
    ax.set_xlim(-3.4, 1.5)
    ax.set_ylim(-2.4, 2.4)
    clean(ax)
    ax.legend(loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=7.5, frameon=False, handlelength=3.0)
    save(fig, "conics.pdf")


def kepler_E(M, e):
    E = M.copy() if e < 0.8 else np.pi * np.ones_like(M)
    for _ in range(60):
        E = E - (E - e * np.sin(E) - M) / (1 - e * np.cos(E))
    return E


def ground_track(a, e, i, Om, w, M0, thg0, t):
    mu, wE = 398600.4, 7.292115e-5
    n = np.sqrt(mu / a**3)
    M = M0 + n * t
    E = kepler_E(np.mod(M, 2 * np.pi), e)
    th = 2 * np.arctan(np.sqrt((1 + e) / (1 - e)) * np.tan(E / 2))
    tht = th + w
    phi = np.arcsin(np.sin(tht) * np.sin(i))
    cxi = (np.cos(tht) * np.cos(Om) - np.cos(i) * np.sin(tht) * np.sin(Om)) / np.cos(phi)
    sxi = (np.cos(tht) * np.sin(Om) + np.cos(i) * np.sin(tht) * np.cos(Om)) / np.cos(phi)
    xi = np.arctan2(sxi, cxi)
    lam = np.unwrap(xi - (thg0 + wE * t))
    lam = lam - np.angle(np.mean(np.exp(1j * lam)))      # centre the (closed) track on lambda_g = 0
    lam = np.mod(lam + np.pi, 2 * np.pi) - np.pi
    return np.degrees(lam), np.degrees(phi)


def _track_axes(ax, title):
    ax.axhline(0, color=G, lw=0.5)
    ax.axvline(0, color=G, lw=0.3, ls=":")
    ax.set_xlabel(r"$\lambda_g$ [deg]")
    ax.set_ylabel(r"$\phi$ [deg]")
    ax.set_title(title, fontsize=8.5)
    ax.tick_params(labelsize=7)


def _arrows_on(ax, lam, phi, k=(0.12, 0.37, 0.62, 0.87)):
    n = len(lam)
    for f in k:
        j = int(f * n)
        if np.hypot(lam[j + 3] - lam[j], phi[j + 3] - phi[j]) > 1e-6:
            ax.annotate("", xy=(lam[j + 3], phi[j + 3]), xytext=(lam[j], phi[j]),
                        arrowprops=dict(arrowstyle="-|>", color=K, lw=0.8, mutation_scale=8))


def fig_geosync():
    a = (398600.4 / 7.292115e-5**2) ** (1 / 3)
    T = 2 * np.pi / 7.292115e-5
    t = np.linspace(0, T, 4000)
    d = np.radians
    fig, axs = plt.subplots(2, 2, figsize=(6.3, 4.6))
    # (a) geostationary
    ax = axs[0, 0]
    ax.plot([0], [0], "o", color=K, ms=5)
    ax.set_xlim(-40, 40); ax.set_ylim(-15, 15)
    _track_axes(ax, "(a) $i=0,\\ e=0$: geostationary (fixed point)")
    # (b) i != 0, e = 0 : figure eight
    ax = axs[0, 1]
    lam, phi = ground_track(a, 0.0, d(30), 0.0, 0.0, 0.0, 0.0, t)
    ax.plot(lam, phi, color=K)
    _arrows_on(ax, lam, phi)
    ax.set_xlim(-10, 10); ax.set_ylim(-35, 35)
    _track_axes(ax, "(b) $i=30^\\circ,\\ e=0$: figure eight ($\\phi_{\\max}=i$)")
    # (c) i = 0, e != 0 : segment on the equator
    ax = axs[1, 0]
    lam, phi = ground_track(a, 0.2, 0.0, 0.0, 0.0, 0.0, 0.0, t)
    ax.plot(lam, phi + 0.0, color=K, lw=1.8)
    ax.annotate("", xy=(lam.max(), 1.6), xytext=(lam.min(), 1.6),
                arrowprops=dict(arrowstyle="<|-|>", color=K, lw=0.7, mutation_scale=7))
    ax.text(0, 2.6, "travelled back and forth", ha="center", fontsize=7)
    ax.text(lam.max() - 3, -3.8, "perigee: east", fontsize=6.5, ha="right")
    ax.set_xlim(-40, 40); ax.set_ylim(-15, 15)
    _track_axes(ax, "(c) $i=0,\\ e=0.2$: segment on the equator")
    # (d) i != 0 and e != 0, two arguments of perigee
    ax = axs[1, 1]
    lam, phi = ground_track(a, 0.4, d(10), 0.0, 0.0, 0.0, 0.0, t)
    ax.plot(lam, phi, color=K, label=r"$\omega=0$")
    _arrows_on(ax, lam, phi)
    lam2, phi2 = ground_track(a, 0.4, d(10), 0.0, d(90), 0.0, 0.0, t)
    ax.plot(lam2, phi2, color=K, ls=(0, (4, 2)), label=r"$\omega=90^\circ$")
    ax.set_xlim(-60, 60); ax.set_ylim(-12, 12)
    _track_axes(ax, "(d) $i=10^\\circ,\\ e=0.4$: distorted (drop) shape")
    ax.legend(fontsize=7, frameon=False, loc="upper left")
    fig.tight_layout()
    save(fig, "geosync.pdf")


def fig_kepler2():
    fig, ax = plt.subplots(figsize=(3.4, 2.2))
    e, a = 0.6, 1.0
    b = a * np.sqrt(1 - e * e)
    E = np.linspace(0, 2 * np.pi, 400)
    ax.plot(a * (np.cos(E) - e), b * np.sin(E), color=K)
    ax.add_patch(Circle((0, 0), 0.04, color=K))
    for M0, hatch in [(-0.25, "////"), (np.pi - 0.25, "\\\\\\\\")]:
        M = np.linspace(M0, M0 + 0.5, 100)
        EE = kepler_E(np.mod(M, 2 * np.pi), e)
        x, y = a * (np.cos(EE) - e), b * np.sin(EE)
        ax.add_patch(Polygon(np.c_[np.r_[0, x], np.r_[0, y]], closed=True, fill=False,
                             hatch=hatch, ec=K, lw=0.6))
    ax.text(0.55, 0.0, "$dA$", fontsize=8, ha="center", va="center",
            bbox=dict(fc="white", ec="none", pad=0.5))
    ax.text(-1.45, 0.38, "same $\\Delta t$\n$\\Rightarrow$ same area", fontsize=7, ha="center")
    ax.text(0.05, -0.17, "$F$", fontsize=8)
    clean(ax)
    save(fig, "kepler2.pdf")


# ---------------------------------------------------------------- Chapter 3
def fig_impulse():
    fig, ax = plt.subplots(figsize=(3.6, 2.6))
    mu = 1.0
    x, y = conic(1.0 * (1 - 0.2**2), 0.2, 0.0)
    ax.plot(x, y, color=K, ls=(0, (4, 2)), label="before ($-$)")
    th = np.radians(115)
    p, e = 0.96, 0.2
    r = p / (1 + e * np.cos(th))
    vr = np.sqrt(mu / p) * e * np.sin(th)
    vt = np.sqrt(mu / p) * (1 + e * np.cos(th))
    rh = np.array([np.cos(th), np.sin(th)]); th_h = np.array([-np.sin(th), np.cos(th)])
    P = r * rh
    vm = vr * rh + vt * th_h
    dv = 0.30 * rh + 0.05 * th_h
    vp = vm + dv
    # new orbit from (P, vp)
    h = P[0] * vp[1] - P[1] * vp[0]
    evec = (np.array([vp[1] * h, -vp[0] * h]) / mu) - P / r
    e2 = np.linalg.norm(evec); p2 = h * h / mu
    x2, y2 = conic(p2, e2, np.arctan2(evec[1], evec[0]))
    ax.plot(x2, y2, color=K, label="after ($+$)")
    ax.add_patch(Circle((0, 0), 0.05, color=K))
    ax.plot(*P, "o", color=K, ms=3)
    s = 1.1
    arrow(ax, P, P + s * vm, lw=0.9)
    arrow(ax, P + s * vm, P + s * vp, lw=0.9, ls="--")
    arrow(ax, P, P + s * vp, lw=1.3)
    ax.text(*(P + s * vm + np.array([-0.05, -0.25])), r"$\underline{v}^-$", fontsize=9)
    ax.text(*(P + s * vp + np.array([-0.15, 0.1])), r"$\underline{v}^+$", fontsize=9)
    ax.text(*(P + s * (vm + 0.5 * dv) + np.array([-0.4, 0.0])), r"$\Delta\underline{v}$", fontsize=9)
    ax.set_xlim(-2.3, 1.4); ax.set_ylim(-1.8, 1.9)
    ax.text(*(P + np.array([0.06, -0.12])), "$P$", fontsize=8)
    ax.text(0.05, -0.15, "$B$", fontsize=8)
    clean(ax)
    ax.legend(fontsize=7, frameon=False, loc="center left", bbox_to_anchor=(1.0, 0.5))
    save(fig, "impulse.pdf")


def fig_hohmann_bielliptic():
    fig, axs = plt.subplots(1, 2, figsize=(6.3, 2.9))
    Ri, Rf = 1.0, 2.5
    t = np.linspace(0, 2 * np.pi, 400)
    # Hohmann
    ax = axs[0]
    for R in (Ri, Rf):
        ax.plot(R * np.cos(t), R * np.sin(t), color=K, lw=0.8)
    aT = (Ri + Rf) / 2; eT = (Rf - Ri) / (Rf + Ri)
    th = np.linspace(0, np.pi, 200); r = aT * (1 - eT**2) / (1 + eT * np.cos(th))
    ax.plot(r * np.cos(th), r * np.sin(th), color=K, lw=1.3, ls=(0, (4, 2)))
    arrow(ax, (Ri, 0), (Ri, 0.65), lw=1.2); ax.text(Ri + 0.08, 0.3, r"$\Delta v_1$", fontsize=8)
    arrow(ax, (-Rf, 0), (-Rf, -0.6), lw=1.2); ax.text(-Rf + 0.08, -0.45, r"$\Delta v_2$", fontsize=8)
    ax.add_patch(Circle((0, 0), 0.06, color=K))
    ax.text(0.45, -0.25, "$R_i$", fontsize=8); ax.text(1.5, -1.95, "$R_f$", fontsize=8)
    ax.set_title("Hohmann (2 impulses, $\\Delta t=\\pi\\sqrt{a_T^3/\\mu}$)", fontsize=8.5)
    ax.set_xlim(-3.0, 2.8); ax.set_ylim(-2.8, 2.8); clean(ax)
    # Bielliptic
    ax = axs[1]
    rA = 4.0
    for R in (Ri, Rf):
        ax.plot(R * np.cos(t), R * np.sin(t), color=K, lw=0.8)
    a1 = (Ri + rA) / 2; e1 = (rA - Ri) / (rA + Ri)
    r1 = a1 * (1 - e1**2) / (1 + e1 * np.cos(th))
    ax.plot(r1 * np.cos(th), r1 * np.sin(th), color=K, lw=1.3, ls=(0, (4, 2)))
    a2 = (Rf + rA) / 2; e2 = (rA - Rf) / (rA + Rf)
    th2 = np.linspace(np.pi, 2 * np.pi, 200)
    r2 = a2 * (1 - e2**2) / (1 + e2 * np.cos(th2))
    ax.plot(r2 * np.cos(th2), r2 * np.sin(th2), color=K, lw=1.3, ls=(0, (1.5, 1.2)))
    arrow(ax, (Ri, 0), (Ri, 0.65), lw=1.2); ax.text(Ri + 0.08, 0.3, r"$\Delta v_1$", fontsize=8)
    arrow(ax, (-rA, 0), (-rA, -0.6), lw=1.2); ax.text(-rA + 0.1, -0.5, r"$\Delta v_2$", fontsize=8)
    arrow(ax, (Rf, 0), (Rf, 0.6), lw=1.2); ax.text(Rf + 0.08, 0.35, r"$\Delta v_3$", fontsize=8)
    ax.text(-rA + 0.05, 0.15, r"$r_A^{\max}$", fontsize=8)
    ax.text(-1.2, 1.55, "$T_1$", fontsize=8); ax.text(0.6, -2.85, "$T_2$", fontsize=8)
    ax.add_patch(Circle((0, 0), 0.06, color=K))
    ax.set_title("Bielliptic (3 impulses, $\\Delta v_3$ against motion)", fontsize=8.5)
    ax.set_xlim(-4.4, 2.9); ax.set_ylim(-3.2, 2.5); clean(ax)
    fig.tight_layout()
    save(fig, "hoh_be_geom.pdf")


def dv_hohmann(s):
    return np.sqrt(2 * s / (1 + s)) - 1 + 1 / np.sqrt(s) - np.sqrt(2 / (s * (1 + s)))


def dv_bielliptic(s, rho):
    d1 = np.sqrt(2 * rho / (1 + rho)) - 1
    d2 = np.sqrt(2 * s / (rho * (s + rho))) - np.sqrt(2 / (rho * (1 + rho)))
    d3 = np.sqrt(2 * rho / (s * (s + rho))) - 1 / np.sqrt(s)
    return d1 + d2 + d3


def fig_hoh_be_dv():
    fig, ax = plt.subplots(figsize=(5.4, 3.1))
    s = np.linspace(1, 40, 2000)
    ax.plot(s, dv_hohmann(s), color=K, lw=1.4, label="Hohmann")
    ax.plot(s, (np.sqrt(2) - 1) * (1 + 1 / np.sqrt(s)), color=K, ls=(0, (4, 2)), label=r"biparabolic ($\rho\to\infty$)")
    for rho, ls in [(15.58, (0, (1, 1.2))), (25, (0, (6, 2, 1, 2))), (60, (0, (2, 3)))]:
        ss = s[s <= rho]
        ax.plot(ss, dv_bielliptic(ss, rho), color=G, ls=ls, label=rf"bielliptic $\rho={rho:g}$")
    ax.axhline(np.sqrt(2) - 1, color=G, lw=0.5)
    ax.text(2, np.sqrt(2) - 1 + 0.002, r"asymptote $\sqrt{2}-1$", fontsize=7, ha="left", va="bottom")
    for x0, lab in [(11.94, "11.94"), (15.58, "15.58")]:
        ax.axvline(x0, color=K, lw=0.5, ls=":")
        ax.text(x0, 0.43, lab, fontsize=7, ha="center", va="bottom", bbox=dict(fc="white", ec="none", pad=0.4))
    ax.set_xlim(1, 40); ax.set_ylim(0.0, 0.56)
    ax.set_ylim(0.40, 0.56)
    ax.set_xlabel(r"$\sigma=R_f/R_i$")
    ax.set_ylabel(r"$\Delta v_{tot}/\sqrt{\mu/R_i}$")
    ax.legend(fontsize=7, frameon=False, loc="lower right")
    ax.tick_params(labelsize=7)
    save(fig, "hoh_be_dv.pdf")


def fig_ell_hyp():
    fig, axs = plt.subplots(1, 2, figsize=(6.6, 3.2))
    rp, rA = 1.0, 2.0
    a = (rp + rA) / 2; e = (rA - rp) / (rA + rp)
    # case 1
    ax = axs[0]
    x, y = conic(a * (1 - e * e), e); ax.plot(x, y, color=K)
    x, y = conic(rp * (1 + 1.8), 1.8, 0, rmax=4.5); ax.plot(x, y, color=K, ls=(0, (4, 2)))
    arrow(ax, (rp, 0), (rp, 0.7), lw=1.3); ax.text(rp + 0.08, 0.35, r"$\Delta v$ at $P$", fontsize=8)
    ax.add_patch(Circle((0, 0), 0.05, color=K))
    ax.set_title(r"(1) $\mathcal{E}_f<\mu/r_A^{\max}$: one impulse at periapsis", fontsize=8.5)
    ax.set_xlim(-2.4, 3.2); ax.set_ylim(-2.4, 2.4); clean(ax)
    # case 2
    ax = axs[1]
    x, y = conic(a * (1 - e * e), e); ax.plot(x, y, color=K)
    rAm, rpm = 4.0, 0.45
    a2 = (rp + rAm) / 2; e2 = (rAm - rp) / (rAm + rp)
    th = np.linspace(0, np.pi, 200); r = a2 * (1 - e2**2) / (1 + e2 * np.cos(th))
    ax.plot(r * np.cos(th), r * np.sin(th), color=K, ls=(0, (4, 2)))
    a3 = (rpm + rAm) / 2; e3 = (rAm - rpm) / (rAm + rpm)
    th = np.linspace(np.pi, 2 * np.pi, 200); r = a3 * (1 - e3**2) / (1 + e3 * np.cos(th))
    ax.plot(r * np.cos(th), r * np.sin(th), color=K, ls=(0, (1.5, 1.2)))
    x, y = conic(rpm * (1 + 2.5), 2.5, 0.0, rmax=2.6)
    m = (y >= 0)
    ax.plot(np.where(m, x, np.nan), np.where(m, y, np.nan), color=K, ls=(0, (6, 2, 1, 2)))
    arrow(ax, (rp, 0), (rp, 0.6), lw=1.2); ax.text(rp + 0.08, 0.25, "(a)", fontsize=8)
    arrow(ax, (-rAm, 0), (-rAm, -0.35), lw=1.2); ax.text(-rAm + 0.1, -0.35, "(b)", fontsize=8)
    arrow(ax, (rpm, 0), (rpm, 0.75), lw=1.2); ax.text(rpm - 0.38, 0.62, "(c)", fontsize=8)
    ax.text(-rAm - 0.1, 0.12, r"$r_A^{\max}$", fontsize=8, ha="left")
    ax.text(rpm - 0.1, -0.35, r"$r_p^{\min}$", fontsize=7)
    ax.add_patch(Circle((0, 0), 0.05, color=K))
    ax.set_title(r"(2) $\mathcal{E}_f>\mu/r_A^{\max}$: three impulses", fontsize=8.5)
    ax.set_xlim(-4.5, 2.6); ax.set_ylim(-2.4, 2.4); clean(ax)
    fig.tight_layout()
    save(fig, "ell_hyp.pdf")


# ---------------------------------------------------------------- Chapter 6
def fig_losses():
    fig, ax = plt.subplots(figsize=(3.2, 2.4))
    O = np.array([0, 0])
    ax.plot([-0.3, 2.3], [0, 0], color=G, lw=0.6)
    ax.text(2.25, 0.07, "local horizontal", fontsize=7, ha="right")
    gam = np.radians(35); al = np.radians(20)
    v = 1.8 * np.array([np.cos(gam), np.sin(gam)])
    T = 1.4 * np.array([np.cos(gam + al), np.sin(gam + al)])
    arrow(ax, O, v, lw=1.2); ax.text(*(v + [0.03, -0.05]), r"$\underline{v}$", fontsize=9)
    arrow(ax, O, T, lw=1.2); ax.text(*(T + [-0.05, 0.06]), r"$\underline{T}$", fontsize=9)
    arrow(ax, O, (0, -0.9), lw=1.0); ax.text(0.05, -0.8, r"$\underline{G}$", fontsize=9)
    arrow(ax, O, -0.7 * v / np.linalg.norm(v), lw=1.0, ls="--"); ax.text(-0.75, -0.48, r"$\underline{D}$", fontsize=9)
    ax.add_patch(Arc(O, 1.1, 1.1, theta1=0, theta2=np.degrees(gam), lw=0.6))
    ax.text(0.62, 0.15, r"$\gamma$", fontsize=9)
    ax.add_patch(Arc(O, 1.9, 1.9, theta1=np.degrees(gam), theta2=np.degrees(gam + al), lw=0.6))
    ax.text(0.68, 0.72, r"$\alpha$", fontsize=9)
    ax.set_xlim(-0.9, 2.4); ax.set_ylim(-1.0, 1.4); clean(ax)
    save(fig, "losses.pdf")


def fig_staging():
    fig, ax = plt.subplots(figsize=(5.0, 1.5))
    x0 = 0
    blocks = [("$m_s^{(1)}$\n$m_p^{(1)}$", 2.2), ("$m_s^{(2)}$\n$m_p^{(2)}$", 1.5), ("$m_s^{(3)}$\n$m_p^{(3)}$", 1.0)]
    for lab, w in blocks:
        ax.add_patch(plt.Rectangle((x0, 0), w, 0.8, fill=False, ec=K, lw=0.8))
        ax.text(x0 + w / 2, 0.4, lab, ha="center", va="center", fontsize=7.5)
        x0 += w
    ax.add_patch(Polygon([[x0, 0], [x0 + 0.6, 0.4], [x0, 0.8]], closed=True, fill=False, ec=K, lw=0.8))
    ax.text(x0 + 0.2, 0.4, "PL", ha="center", va="center", fontsize=7)
    def brace(xa, xb, y, lab):
        ax.annotate("", xy=(xa, y), xytext=(xb, y), arrowprops=dict(arrowstyle="<->", lw=0.6))
        ax.text((xa + xb) / 2, y + 0.06, lab, ha="center", fontsize=7.5)
    brace(0, x0 + 0.6, 1.05, "$m_0^{(1)}$")
    brace(2.2, x0 + 0.6, -0.25, r"$m_u^{(1)}=m_0^{(2)}$")
    brace(3.7, x0 + 0.6, -0.55, r"$m_u^{(2)}=m_0^{(3)}$")
    brace(x0, x0 + 0.6, -0.85, r"$m_u^{(3)}$ (payload)")
    ax.set_xlim(-0.1, x0 + 0.9); ax.set_ylim(-1.0, 1.3); clean(ax)
    save(fig, "staging.pdf")


# ---------------------------------------------------------------- Chapter 5 (CR3BP)
MU_EM = 1 / 82.27


def omega2(x, y, mu):
    r1 = np.hypot(x + mu, y); r2 = np.hypot(x + mu - 1, y)
    return x * x + y * y + 2 * (1 - mu) / r1 + 2 * mu / r2


def collinear(mu):
    def f(x):
        return x - (1 - mu) * (x + mu) / abs(x + mu)**3 - mu * (x + mu - 1) / abs(x + mu - 1)**3
    def bis(a, b):
        for _ in range(200):
            m = (a + b) / 2
            if f(a) * f(m) <= 0:
                b = m
            else:
                a = m
        return (a + b) / 2
    return bis(-mu + 1e-9, 1 - mu - 1e-9), bis(1 - mu + 1e-9, 2.0), bis(-2.0, -mu - 1e-9)


def jacobi_values(mu):
    L1, L2, L3 = collinear(mu)
    C = [omega2(L1, 0, mu), omega2(L2, 0, mu), omega2(L3, 0, mu), omega2(0.5 - mu, np.sqrt(3) / 2, mu)]
    return (L1, L2, L3), C


def zvc_panel(ax, C, mu=MU_EM, lim=1.55, labels=True, title=None, npts=700):
    x = np.linspace(-lim, lim, npts); y = np.linspace(-lim, lim, npts)
    X, Y = np.meshgrid(x, y)
    W = omega2(X, Y, mu) - C           # allowed where W >= 0 (v^2 = 2Omega - C)
    ax.contourf(X, Y, W, levels=[-1e9, 0], colors=[LG], hatches=["////"])
    ax.contour(X, Y, W, levels=[0], colors=[K], linewidths=0.9)
    (L1, L2, L3), _ = jacobi_values(mu)
    ax.plot(-mu, 0, "o", color=K, ms=4)
    ax.plot(1 - mu, 0, "o", color=K, ms=2.5)
    if labels:
        ax.text(-mu, -0.14, "E", ha="center", va="top", fontsize=7)
        ax.text(1 - mu, -0.14, "M", ha="center", va="top", fontsize=7)
        for xx, yy, n in [(L1, 0, "$L_1$"), (L2, 0, "$L_2$"), (L3, 0, "$L_3$"),
                          (0.5 - mu, np.sqrt(3) / 2, "$L_4$"), (0.5 - mu, -np.sqrt(3) / 2, "$L_5$")]:
            ax.plot(xx, yy, "x", color=K, ms=3.5, mew=0.8)
            ax.text(xx + 0.04, yy + 0.07, n, fontsize=6.5)
    if title:
        ax.set_title(title, fontsize=8)
    ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim); ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])


def fig_zvc_cases():
    (_, _, _), (C1, C2, C3, C4) = jacobi_values(MU_EM)
    vals = [(C1 + 0.03, f"(5) $C>C_1$"), ((C1 + C2) / 2, "(4) $C_2<C<C_1$"),
            ((C2 + C3) / 2, "(3) $C_3<C<C_2$"), ((C3 + C4) / 2, "(2) $C_{4,5}<C<C_3$")]
    fig, axs = plt.subplots(1, 4, figsize=(6.6, 1.9))
    for ax, (C, t) in zip(axs, vals):
        zvc_panel(ax, C, title=t + f"\n$C={C:.4f}$", labels=False)
    fig.tight_layout(w_pad=0.4)
    save(fig, "zvc_cases.pdf")


def fig_zvc_single(C, name, title, lim=1.55, zoom=None):
    fig, ax = plt.subplots(figsize=(3.1, 3.1))
    zvc_panel(ax, C, title=title, lim=lim)
    ax.text(-1.45, 1.35, "hatched = forbidden\n($2\\Omega<C$)", fontsize=6.5, va="top",
            bbox=dict(fc="white", ec=K, lw=0.4, pad=1.5))
    save(fig, name)


def fig_lagrange():
    mu = MU_EM
    (L1, L2, L3), _ = jacobi_values(mu)
    fig, ax = plt.subplots(figsize=(4.2, 3.4))
    arrow(ax, (-1.35, 0), (1.45, 0), lw=0.7); ax.text(1.42, -0.12, "$x\\ (\\hat\\imath)$", fontsize=8, ha="right")
    arrow(ax, (0, -1.05), (0, 1.1), lw=0.7); ax.text(0.04, 1.03, "$y\\ (\\hat\\jmath)$", fontsize=8)
    ax.add_patch(Circle((-mu, 0), 0.07, color=LG, ec=K, lw=0.6, zorder=3))
    ax.add_patch(Circle((1 - mu, 0), 0.035, color=LG, ec=K, lw=0.6, zorder=3))
    ax.text(-mu - 0.05, 0.1, "$m_1$", fontsize=8, ha="right")
    ax.text(1 - mu + 0.02, 0.2, "$m_2$", fontsize=8, ha="left")
    ax.text(0.02, -0.12, "$O'$ (c.m.)", fontsize=7)
    P4, P5 = (0.5 - mu, np.sqrt(3) / 2), (0.5 - mu, -np.sqrt(3) / 2)
    for P in (P4, P5):
        ax.plot([-mu, P[0], 1 - mu], [0, P[1], 0], color=G, lw=0.6, ls="--")
    for xx, yy, n in [(L1, 0, "$L_1$"), (L2, 0, "$L_2$"), (L3, 0, "$L_3$"), (*P4, "$L_4$"), (*P5, "$L_5$")]:
        ax.plot(xx, yy, "x", color=K, ms=6, mew=1.2, zorder=4)
        dy = -0.17 if n == "$L_1$" else (0.08 if yy >= 0 else -0.16)
        ax.text(xx + 0.03 - (0.1 if n == "$L_1$" else 0), yy + dy, n, fontsize=8)
    ax.text(0.15, 0.48, "1", fontsize=7, color=G); ax.text(0.8, 0.48, "1", fontsize=7, color=G)
    ax.add_patch(Arc((0, 0), 0.5, 0.5, theta1=20, theta2=110, lw=0.8))
    arrow(ax, (0.25 * np.cos(np.radians(105)), 0.25 * np.sin(np.radians(105))),
          (0.25 * np.cos(np.radians(112)), 0.25 * np.sin(np.radians(112))), lw=0.8)
    ax.text(0.12, 0.27, r"$\omega$", fontsize=8)
    ax.text(-1.33, 0.95, rf"Earth–Moon: $\mu={mu:.5f}$" + "\n" +
            rf"$L_1: x={L1:.3f}$, $L_2: x={L2:.3f}$, $L_3: x={L3:.3f}$", fontsize=6.5)
    ax.set_xlim(-1.4, 1.5); ax.set_ylim(-1.1, 1.15); clean(ax)
    save(fig, "lagrange.pdf")


def fig_synodic():
    fig, ax = plt.subplots(figsize=(3.2, 2.7))
    wt = np.radians(30)
    arrow(ax, (0, 0), (1.5, 0), lw=0.7, color=G); ax.text(1.5, -0.12, r"$\hat c_1$", fontsize=8)
    arrow(ax, (0, 0), (0, 1.4), lw=0.7, color=G); ax.text(-0.15, 1.35, r"$\hat c_2$", fontsize=8)
    i_ = np.array([np.cos(wt), np.sin(wt)]); j_ = np.array([-np.sin(wt), np.cos(wt)])
    arrow(ax, (0, 0), 1.5 * i_, lw=1.1); ax.text(*(1.5 * i_ + [0.03, 0.02]), r"$\hat\imath$", fontsize=9)
    arrow(ax, (0, 0), 1.3 * j_, lw=1.1); ax.text(*(1.3 * j_ + [-0.12, 0.02]), r"$\hat\jmath$", fontsize=9)
    ax.add_patch(Arc((0, 0), 1.0, 1.0, theta1=0, theta2=30, lw=0.6)); ax.text(0.55, 0.1, r"$\omega t$", fontsize=8)
    mu = 0.25
    ax.add_patch(Circle(tuple(-mu * 1.2 * i_), 0.09, color=LG, ec=K, lw=0.6, zorder=3))
    ax.add_patch(Circle(tuple((1 - mu) * 1.2 * i_), 0.05, color=LG, ec=K, lw=0.6, zorder=3))
    ax.text(*(-mu * 1.2 * i_ + [-0.1, -0.22]), "$m_1$", fontsize=8)
    ax.text(*((1 - mu) * 1.2 * i_ + [0.0, -0.2]), "$m_2$", fontsize=8)
    ax.text(-0.25, -0.65, r"$\hat k=\hat c_3\parallel\underline{H}$ (out of page)" + "\n" + r"origin $O'$ = centre of mass", fontsize=6.5)
    ax.set_xlim(-0.6, 1.8); ax.set_ylim(-0.75, 1.5); clean(ax)
    save(fig, "synodic.pdf")


def fig_nbody():
    fig, ax = plt.subplots(figsize=(3.3, 2.5))
    rng = np.random.default_rng(3)
    pts = rng.uniform([-1.1, -0.4], [1.1, 0.5], size=(6, 2))
    m = rng.uniform(0.5, 1.5, size=6)
    C = (pts * m[:, None]).sum(0) / m.sum()
    plane = np.array([[-1.5, -0.6], [1.0, -0.6], [1.5, 0.35], [-1.0, 0.35]])
    ax.add_patch(Polygon(plane, closed=True, fill=False, ec=G, lw=0.8, ls="--"))
    ax.text(1.05, -0.55, "Laplace plane", fontsize=7, color=K)
    for p, mm in zip(pts, m):
        ax.plot(*p, "o", color=K, ms=2.5 + 2 * mm)
    ax.text(*(pts[0] + [0.05, 0.05]), "$m_i$", fontsize=8)
    ax.plot(*C, "+", color=K, ms=8, mew=1.2); ax.text(C[0] + 0.06, C[1] - 0.12, "$C$", fontsize=8)
    arrow(ax, C, C + [0, 1.0], lw=1.3); ax.text(C[0] + 0.05, C[1] + 0.9, r"$\underline{H}_c$", fontsize=9)
    ax.set_xlim(-1.6, 1.7); ax.set_ylim(-0.75, 1.5); clean(ax)
    save(fig, "nbody.pdf")


# ---------------------------------------------------------------- Chapter 8
def fig_eclipse():
    fig, axs = plt.subplots(1, 2, figsize=(6.3, 2.5))
    rS = 3.2
    for ax, (rs, Th, title) in zip(axs, [(1.9, np.radians(105), "illuminated: $\\Theta\\le\\theta_1+\\theta_2$"),
                                         (1.9, np.radians(160), "shadow: $\\Theta>\\theta_1+\\theta_2$")]):
        ax.add_patch(Circle((0, 0), 1, fc=LG, ec=K, lw=0.8))
        ax.text(0, -0.55, "Earth", ha="center", fontsize=7.5)
        S = np.array([rS, 0.0]); P = rs * np.array([np.cos(Th), np.sin(Th)])
        arrow(ax, (0, 0), S, lw=1.0); ax.text(S[0] - 0.1, 0.1, r"$\underline{r}_{SUN}$", fontsize=8, ha="right")
        arrow(ax, (0, 0), P, lw=1.0); ax.text(P[0] - 0.05, P[1] + 0.08, r"$\underline{r}$", fontsize=8, ha="right")
        th1 = np.arccos(1 / rs); th2 = np.arccos(1 / rS)
        T1 = np.array([np.cos(Th - th1), np.sin(Th - th1)]); T2 = np.array([np.cos(th2), np.sin(th2)])
        ax.plot(*zip(P, T1), color=K, lw=0.6, ls="--"); ax.plot(*zip(S, T2), color=K, lw=0.6, ls="--")
        ax.plot(*zip((0, 0), T1), color=G, lw=0.6, ls=":"); ax.plot(*zip((0, 0), T2), color=G, lw=0.6, ls=":")
        ax.add_patch(Arc((0, 0), 0.7, 0.7, theta1=np.degrees(Th - th1), theta2=np.degrees(Th), lw=0.6))
        ax.add_patch(Arc((0, 0), 0.5, 0.5, theta1=0, theta2=np.degrees(th2), lw=0.6))
        ax.add_patch(Arc((0, 0), 1.25, 1.25, theta1=0, theta2=np.degrees(Th), lw=0.5, ls="-."))
        mid1 = (Th - th1 / 2); ax.text(0.47 * np.cos(mid1), 0.47 * np.sin(mid1), r"$\theta_1$", fontsize=7)
        ax.text(0.3 * np.cos(th2 / 2) + 0.02, 0.3 * np.sin(th2 / 2), r"$\theta_2$", fontsize=7)
        ax.text(0.68 * np.cos(Th / 2 + 0.3), 0.68 * np.sin(Th / 2 + 0.3), r"$\Theta$", fontsize=8)
        ax.plot(*zip(P, S), color=K, lw=0.7, ls=(0, (1, 1)))
        ax.set_title(title, fontsize=8.5)
        ax.set_xlim(-2.2, 3.4); ax.set_ylim(-1.2, 2.1); clean(ax)
    fig.tight_layout()
    save(fig, "eclipse.pdf")


def fig_srp():
    fig, axs = plt.subplots(1, 2, figsize=(5.0, 1.6))
    for ax, refl, title in [(axs[0], False, "absorbed: $C_R=1$"), (axs[1], True, "reflected: $C_R=2$")]:
        ax.plot([0, 0], [-0.8, 0.8], color=K, lw=2.0)
        for y in (-0.4, 0.0, 0.4):
            arrow(ax, (-1.4, y), (-0.05, y), lw=0.7, ms=6)
            if refl:
                arrow(ax, (-0.05, y + 0.05), (-1.1, y + 0.05), lw=0.7, ms=6, ls="--")
        arrow(ax, (0.1, 0), (0.6 if not refl else 1.1, 0), lw=1.6)
        ax.text(0.15, 0.12, "momentum\nto S/C", fontsize=6.5)
        ax.text(-1.4, 0.6, "photons", fontsize=6.5)
        ax.set_title(title, fontsize=8)
        ax.set_xlim(-1.5, 1.3); ax.set_ylim(-0.9, 0.9); clean(ax)
    save(fig, "srp.pdf")


def orthographic_field(ax, f, tilt=20.0, n=500, title=""):
    """Sign map of f(lat, lon) on an orthographic globe (grey = negative)."""
    x = np.linspace(-1, 1, n); X, Y = np.meshgrid(x, x)
    R2 = X**2 + Y**2
    inside = R2 <= 1
    Z = np.sqrt(np.clip(1 - R2, 0, None))
    t = np.radians(tilt)
    # view rotated about x-axis: body coords (bx, by, bz) with bz = polar axis
    bx = X; by = Z * np.cos(t) - Y * np.sin(t) * 0 + 0 * Y
    # use: screen up (Y) -> mostly polar axis tilted toward viewer
    by = Z * np.cos(t) - Y * np.sin(t)
    bz = Z * np.sin(t) + Y * np.cos(t)
    lat = np.arcsin(np.clip(bz, -1, 1)); lon = np.arctan2(bx, by)
    F = np.where(inside, f(lat, lon), np.nan)
    ax.contourf(X, Y, F, levels=[-1e9, 0, 1e9], colors=[LG, "white"], hatches=["////", None])
    ax.contour(X, Y, F, levels=[0], colors=[K], linewidths=0.9)
    th = np.linspace(0, 2 * np.pi, 300)
    ax.plot(np.cos(th), np.sin(th), color=K, lw=0.8)
    ax.set_title(title, fontsize=8)
    ax.set_xlim(-1.05, 1.05); ax.set_ylim(-1.05, 1.05); ax.set_aspect("equal"); ax.axis("off")


def fig_harmonics():
    fig, axs = plt.subplots(1, 3, figsize=(6.3, 2.3))
    P20 = lambda s: (3 * s**2 - 1) / 2
    P22 = lambda s: 3 * (1 - s**2)
    P32 = lambda s: 15 * s * (1 - s**2)
    orthographic_field(axs[0], lambda la, lo: -P20(np.sin(la)) + 0 * lo,
                       title="zonal $J_2$ ($l=2,\\,m=0$)\n2 parallels ($\\pm35.3^\\circ$), 0 meridians")
    orthographic_field(axs[1], lambda la, lo: P22(np.sin(la)) * np.cos(2 * lo) + 1e-9,
                       title="sectoral $J_{22}$ ($l=m=2$)\n0 parallels, 2 meridians")
    orthographic_field(axs[2], lambda la, lo: P32(np.sin(la)) * np.cos(2 * lo),
                       title="tesseral $J_{32}$ ($l=3,\\,m=2$)\n1 parallel (equator), 2 meridians")
    fig.tight_layout()
    save(fig, "harmonics.pdf")


def fig_j2_effects():
    fig, axs = plt.subplots(1, 2, figsize=(6.0, 2.5))
    # nodal regression (top view of equatorial plane)
    ax = axs[0]
    ax.add_patch(Circle((0, 0), 0.35, fc=LG, ec=K, lw=0.6))
    for k, ang in enumerate([0, 25, 50]):
        a = np.radians(ang)
        ls = ["-", (0, (4, 2)), (0, (1, 1.2))][k]
        ax.plot([-1.3 * np.cos(a), 1.3 * np.cos(a)], [-1.3 * np.sin(a), 1.3 * np.sin(a)], color=K, lw=0.9, ls=ls)
    ax.add_patch(Arc((0, 0), 2.2, 2.2, theta1=0, theta2=50, lw=0.6))
    arrow(ax, (1.1 * np.cos(np.radians(10)), 1.1 * np.sin(np.radians(10))), (1.1, 0.0), lw=0.7)
    ax.text(1.18, 0.52, r"$\langle\dot\Omega\rangle<0$" + "\n(direct orbit)", fontsize=7)
    ax.text(-1.35, -1.3, "line of nodes, seen from $\\hat c_3$", fontsize=7)
    ax.set_xlim(-1.5, 2.1); ax.set_ylim(-1.4, 1.3); clean(ax)
    ax.set_title("(1) regression/precession of the node", fontsize=8.5)
    # apsidal rotation
    ax = axs[1]
    for k, ang in enumerate([0, 30]):
        x, y = conic(0.8, 0.5, np.radians(ang))
        ax.plot(x, y, color=K, ls=["-", (0, (4, 2))][k])
        ax.plot([0, 1.6 * np.cos(np.radians(ang)) / 3], [0, 1.6 * np.sin(np.radians(ang)) / 3], color=K, lw=0.6)
    ax.add_patch(Circle((0, 0), 0.04, color=K))
    ax.add_patch(Arc((0, 0), 1.2, 1.2, theta1=0, theta2=30, lw=0.6))
    ax.text(0.65, 0.12, r"$\Delta\omega$", fontsize=8)
    ax.text(-2.4, -1.3, r"$\langle\dot\omega\rangle=0$ at $i=63.4^\circ,\,116.6^\circ$", fontsize=7)
    ax.set_xlim(-2.5, 1.0); ax.set_ylim(-1.4, 1.4); clean(ax)
    ax.set_title("(2) rotation of the apsidal line", fontsize=8.5)
    fig.tight_layout()
    save(fig, "j2_effects.pdf")


def fig_sso():
    fig, axs = plt.subplots(1, 2, figsize=(6.0, 2.8))
    for ax, sso in [(axs[0], False), (axs[1], True)]:
        ax.add_patch(Circle((0, 0), 0.18, fc="white", ec=K, lw=0.8))
        for k in range(8):
            ax.plot([0.14 * np.cos(k * np.pi / 4), 0.26 * np.cos(k * np.pi / 4)],
                    [0.14 * np.sin(k * np.pi / 4), 0.26 * np.sin(k * np.pi / 4)], color=K, lw=0.6)
        th = np.linspace(0, 2 * np.pi, 300)
        ax.plot(np.cos(th), np.sin(th), color=G, lw=0.6, ls="--")
        for k, ang in enumerate(np.radians([0, 90, 180, 270])):
            E = np.array([np.cos(ang), np.sin(ang)])
            ax.add_patch(Circle(tuple(E), 0.06, fc=LG, ec=K, lw=0.6, zorder=3))
            d = ang + np.radians(60) if sso else np.radians(60)
            u = 0.3 * np.array([np.cos(d), np.sin(d)])
            ax.plot(*zip(E - u, E + u), color=K, lw=1.4)
        ax.add_patch(Arc((0, 0), 2.5, 2.5, theta1=20, theta2=70, lw=0.6))
        arrow(ax, (1.25 * np.cos(np.radians(65)), 1.25 * np.sin(np.radians(65))),
              (1.25 * np.cos(np.radians(72)), 1.25 * np.sin(np.radians(72))), lw=0.7)
        ax.text(0.95, 1.05, "1 year", fontsize=7)
        ax.set_title("sun-synchronous: orbit plane turns with the Sun" if sso else
                     "not sun-synchronous: plane fixed in space", fontsize=8)
        ax.text(-0.15, -0.38, "Sun", fontsize=7)
        ax.set_xlim(-1.5, 1.6); ax.set_ylim(-1.45, 1.45); clean(ax)
    axs[0].text(-1.5, -1.45, "thick segment = trace of the orbit plane\n(seen from the ecliptic pole)", fontsize=6.5)
    fig.tight_layout()
    save(fig, "sso.pdf")


def fig_drag():
    fig, ax = plt.subplots(figsize=(3.6, 2.6))
    ax.add_patch(Circle((0, 0), 1.0, fc=LG, ec=K, lw=0.6))
    th = np.linspace(0, 2 * np.pi, 300)
    ax.plot(1.08 * np.cos(th), 1.08 * np.sin(th), color=G, lw=0.5, ls=":")
    lss = ["-", (0, (4, 2)), (0, (6, 2, 1, 2)), (0, (1.5, 1.2)), (0, (2, 3))]
    for k, (rp, ra) in enumerate([(1.12, 3.2), (1.115, 2.5), (1.11, 1.9), (1.105, 1.45), (1.10, 1.14)]):
        a = (rp + ra) / 2; e = (ra - rp) / (ra + rp)
        x, y = conic(a * (1 - e * e), e, 0.0)
        ax.plot(x, y, color=K, lw=0.8, ls=lss[k])
    ax.text(1.25, -0.15, "perigee:\ndrag\nconcentrated", fontsize=6.5)
    ax.text(-3.2, -2.1, "apogee height decreases: $a\\downarrow,\\ e\\downarrow$ (circularisation)", fontsize=6.5)
    ax.set_xlim(-3.3, 2.0); ax.set_ylim(-2.2, 1.5); clean(ax)
    save(fig, "drag.pdf")


def fig_thirdbody():
    fig, ax = plt.subplots(figsize=(3.6, 2.3))
    E = np.array([0, 0]); S = np.array([0.9, 0.7]); B = np.array([3.2, 0.2])
    ax.add_patch(Circle(tuple(E), 0.12, fc=LG, ec=K, lw=0.6, zorder=3))
    ax.add_patch(Circle(tuple(B), 0.16, fc="white", ec=K, lw=0.8, zorder=3))
    ax.plot(*S, "s", color=K, ms=4)
    arrow(ax, E, S, lw=1.1); ax.text(0.25, 0.48, r"$\underline{r}_{1S}$", fontsize=9)
    arrow(ax, E, B, lw=1.1); ax.text(1.6, -0.08, r"$\underline{r}_{12}$", fontsize=9)
    arrow(ax, B, S, lw=1.1, ls="--"); ax.text(2.0, 0.58, r"$\underline{r}_{2S}$", fontsize=9)
    ax.text(-0.15, -0.35, "1 (Earth)", fontsize=7.5); ax.text(2.9, -0.25, "2 (Sun / Moon)", fontsize=7.5)
    ax.text(0.8, 0.85, "S/C", fontsize=7.5)
    ax.text(-0.3, -0.75, r"$\underline{r}_{2S}=\underline{r}_{21}+\underline{r}_{1S}$,  $\underline{r}_{21}=-\underline{r}_{12}$", fontsize=7.5)
    ax.set_xlim(-0.5, 3.6); ax.set_ylim(-0.9, 1.1); clean(ax)
    save(fig, "thirdbody.pdf")


# ---------------------------------------------------------------- Chapter 9 (angle sequences)
def R1(a):
    c, s = np.cos(a), np.sin(a); return np.array([[1, 0, 0], [0, c, s], [0, -s, c]])


def R2(a):
    c, s = np.cos(a), np.sin(a); return np.array([[c, 0, -s], [0, 1, 0], [s, 0, c]])


def R3(a):
    c, s = np.cos(a), np.sin(a); return np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]])


def proj(v):
    """Simple axonometric projection of a 3D vector to the page."""
    az, el = np.radians(-35), np.radians(20)
    x = v[0] * np.cos(az) * 0 + 0
    # rotate world so that the view is pleasant: axis1 toward lower-left, axis2 right, axis3 up
    e1 = np.array([-0.72, -0.50]); e2 = np.array([1.0, -0.08]); e3 = np.array([0.0, 1.0])
    return v[0] * e1 + v[1] * e2 + v[2] * e3


def draw_frame(ax, R, names, ls="-", lw=1.1, color=K, scale=1.0, label_off=0.08):
    for k in range(3):
        v = proj(scale * R[k])
        arrow(ax, (0, 0), tuple(v), lw=lw, color=color, ls=ls, ms=7)
        ax.text(v[0] + label_off * np.sign(v[0] if abs(v[0]) > 0.1 else 1), v[1] + 0.04, names[k],
                fontsize=8, color=color)


def draw_arc(ax, axis_row_frame, k_axis, ang, R_before, label, r=0.55):
    """Arc of rotation by ang about axis k of frame R_before (rows = unit vectors)."""
    i, j = [(1, 2), (2, 0), (0, 1)][k_axis]
    t = np.linspace(0, ang, 40)
    pts = np.array([proj(r * (np.cos(tt) * R_before[i] + np.sin(tt) * R_before[j])) for tt in t])
    ax.plot(pts[:, 0], pts[:, 1], color=K, lw=0.7)
    ax.annotate("", xy=pts[-1], xytext=pts[-4], arrowprops=dict(arrowstyle="-|>", lw=0.7, color=K, mutation_scale=7))
    m = pts[len(pts) // 2]
    ax.text(m[0] + 0.03, m[1] + 0.03, label, fontsize=9)


def fig_sequence(kind):
    psi, th, ph = np.radians(40), np.radians(35), np.radians(35)
    N = np.eye(3)
    if kind == "euler":   # 3-1-3
        A = R3(psi) @ N; Bp = R1(th) @ A; B = R3(ph) @ Bp
        steps = [(N, A, 2, psi, r"$\psi$", ["$\\hat E_1$", "$\\hat E_2$", "$\\hat E_3$"], ["$\\hat\\imath$", "", ""],
                  r"1) $\underline{\underline{R}}_3(\psi)$ about $\hat E_3$"),
                 (A, Bp, 0, th, r"$\theta$", ["$\\hat\\imath$", "", "$\\hat E_3$"], ["", "$\\hat\\jmath\\,''$", "$\\hat e_3$"],
                  r"2) $\underline{\underline{R}}_1(\theta)$ about $\hat\imath$ (line of nodes)"),
                 (Bp, B, 2, ph, r"$\phi$", ["", "", "$\\hat e_3$"], ["$\\hat e_1$", "$\\hat e_2$", ""],
                  r"3) $\underline{\underline{R}}_3(\phi)$ about $\hat e_3$")]
        name = "euler313.pdf"
    else:                 # Bryant 3-2-1
        A = R3(psi) @ N; Bp = R2(th) @ A; B = R1(ph) @ Bp
        steps = [(N, A, 2, psi, r"$\psi$", ["$\\hat E_1$", "$\\hat E_2$", "$\\hat E_3$"], ["", "$\\hat\\jmath$", ""],
                  r"1) yaw $\underline{\underline{R}}_3(\psi)$ about $\hat E_3$"),
                 (A, Bp, 1, th, r"$\theta$", ["", "$\\hat\\jmath$", ""], ["$\\hat e_1$", "", "$\\hat k''$"],
                  r"2) pitch $\underline{\underline{R}}_2(\theta)$ about $\hat\jmath$"),
                 (Bp, B, 0, ph, r"$\phi$", ["$\\hat e_1$", "", ""], ["", "$\\hat e_2$", "$\\hat e_3$"],
                  r"3) roll $\underline{\underline{R}}_1(\phi)$ about $\hat e_1$")]
        name = "bryant321.pdf"
    fig, axs = plt.subplots(1, 3, figsize=(6.4, 2.3))
    for ax, (Rb, Ra, k, ang, lab, nb, na, title) in zip(axs, steps):
        draw_frame(ax, Rb, nb, ls=(0, (3, 2)), lw=0.8, color=G)
        draw_frame(ax, Ra, na, lw=1.2)
        draw_arc(ax, None, k, ang, Rb, lab)
        ax.set_title(title, fontsize=7.5)
        ax.set_xlim(-1.0, 1.25); ax.set_ylim(-0.95, 1.2); clean(ax)
    fig.tight_layout(w_pad=0.2)
    save(fig, name)


# ---------------------------------------------------------------- Chapter 11
def sphere_curves(I, levels, n=600):
    """Contours of 2T = sum H_i^2/I_i on the unit momentum sphere |H|=1."""
    lat = np.linspace(-np.pi / 2, np.pi / 2, n); lon = np.linspace(-np.pi, np.pi, 2 * n)
    LON, LAT = np.meshgrid(lon, lat)
    H1 = np.cos(LAT) * np.cos(LON); H2 = np.cos(LAT) * np.sin(LON); H3 = np.sin(LAT)
    F = H1**2 / I[0] + H2**2 / I[1] + H3**2 / I[2]
    fig = plt.figure(); ax = fig.add_subplot()
    cs = ax.contour(LON, LAT, F, levels=sorted(levels))
    out = []
    for lev, segs in zip(cs.levels, cs.allsegs):
        for seg in segs:
            lo, la = seg[:, 0], seg[:, 1]
            out.append((lev, np.c_[np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)]))
    plt.close(fig)
    return out


def view(P, az=np.radians(35), el=np.radians(22)):
    """Orthographic view: returns screen x, y and depth for 3D points (N,3)."""
    ca, sa, ce, se = np.cos(az), np.sin(az), np.cos(el), np.sin(el)
    x = -sa * P[:, 0] + ca * P[:, 1]
    y = -ca * se * P[:, 0] - sa * se * P[:, 1] + ce * P[:, 2]
    d = ca * ce * P[:, 0] + sa * ce * P[:, 1] + se * P[:, 2]
    return x, y, d


def plot3(ax, P, front_style, back_style):
    x, y, d = view(P)
    xf = np.where(d >= 0, x, np.nan); yf = np.where(d >= 0, y, np.nan)
    xb = np.where(d < 0, x, np.nan); yb = np.where(d < 0, y, np.nan)
    ax.plot(xb, yb, **back_style); ax.plot(xf, yf, **front_style)


def sphere_frame(ax, labels=("$H_1$", "$H_2$", "$H_3$")):
    t = np.linspace(0, 2 * np.pi, 400)
    ax.plot(np.cos(t), np.sin(t), color=K, lw=0.8)       # silhouette
    for k, lab in enumerate(labels):
        e = np.zeros(3); e[k] = 1.0
        x, y, d = view(np.array([e * 1.0, e * 1.35]))
        ax.annotate("", xy=(x[1], y[1]), xytext=(x[0], y[0]),
                    arrowprops=dict(arrowstyle="-|>", lw=0.7, color=K, mutation_scale=7))
        ax.text(x[1] + 0.03, y[1] + 0.03, lab, fontsize=8)


def fig_polhodes():
    I = (3.0, 2.0, 1.0)          # I1 > I2 > I3 as in the notes
    sep = 1 / I[1]
    lev = [1 / I[0] + 0.02, 0.38, 0.43, 0.47, sep - 0.004, sep + 0.004, 0.56, 0.65, 0.8, 1 / I[2] - 0.03]
    curves = sphere_curves(I, lev + [sep])
    fig, ax = plt.subplots(figsize=(3.5, 3.4))
    sphere_frame(ax)
    for lv, P in curves:
        if abs(lv - sep) < 1e-9:
            plot3(ax, P, dict(color=K, lw=1.6), dict(color=K, lw=0.9, ls=(0, (2, 2))))
        else:
            plot3(ax, P, dict(color=K, lw=0.7), dict(color=G, lw=0.5, ls=(0, (1, 1.5))))
    for k, lab in [(0, "max $I$\n$T_{\\min}$"), (1, "intermediate\n(separatrix)"), (2, "min $I$\n$T_{\\max}$")]:
        e = np.zeros(3); e[k] = 1
        x, y, d = view(e[None, :]); ax.plot(x, y, "o", color=K, ms=3)
    ax.text(-1.25, -1.35, "$I_1>I_2>I_3$; thick = separatrices ($T=H^2/2I_2$)", fontsize=6.5)
    ax.set_xlim(-1.45, 1.55); ax.set_ylim(-1.45, 1.55); clean(ax)
    save(fig, "polhodes.pdf")


def fig_polhodes_diss():
    I = np.array([3.0, 2.0, 1.0])
    H = np.array([0.08, 0.05, 1.0]); H /= np.linalg.norm(H)
    k, dt = 0.05, 0.01
    traj = [H.copy()]
    def rhs(H):
        w = H / I
        return np.cross(H, w) - k * (w - (w @ H) * H)     # |H| preserved, T decreases
    for _ in range(60000):
        k1 = rhs(H); k2 = rhs(H + dt / 2 * k1); k3 = rhs(H + dt / 2 * k2); k4 = rhs(H + dt * k3)
        H = H + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4); H /= np.linalg.norm(H)
        traj.append(H.copy())
    P = np.array(traj)
    fig, ax = plt.subplots(figsize=(3.5, 3.4))
    sphere_frame(ax)
    for lv, C in sphere_curves(tuple(I), [1 / I[1]]):
        plot3(ax, C, dict(color=K, lw=1.2), dict(color=K, lw=0.7, ls=(0, (2, 2))))
    plot3(ax, P, dict(color=K, lw=0.55), dict(color=G, lw=0.4, ls=(0, (1, 1))))
    x, y, _ = view(P[:1]); ax.plot(x, y, "o", color=K, ms=3.5); ax.text(x[0] + 0.05, y[0] + 0.02, "start\n(near min $I$)", fontsize=6.5)
    x, y, _ = view(P[-1:]); ax.plot(x, y, "s", color=K, ms=3.5); ax.text(x[0] - 0.1, y[0] - 0.22, "end: spin about max $I$", fontsize=6.5)
    ax.text(-1.3, -1.38, r"$|\underline{H}|$ const, $T_{rot}\downarrow$: path crosses the separatrix", fontsize=6.5)
    ax.set_xlim(-1.45, 1.55); ax.set_ylim(-1.45, 1.55); clean(ax)
    save(fig, "polhodes_diss.pdf")


def fig_parallel_axis():
    fig, ax = plt.subplots(figsize=(3.0, 2.2))
    t = np.linspace(0, 2 * np.pi, 200)
    ax.fill(1.6 + 0.9 * np.cos(t) + 0.15 * np.cos(3 * t), 0.9 + 0.6 * np.sin(t), fc=LG, ec=K, lw=0.7)
    P = np.array([0, 0]); C = np.array([1.6, 0.9]); dm = np.array([1.15, 1.3])
    ax.plot(*P, "o", color=K, ms=3); ax.text(-0.15, -0.15, "$P$", fontsize=8)
    ax.plot(*C, "+", color=K, ms=8, mew=1.2); ax.text(C[0] - 0.1, C[1] - 0.25, "$C$", fontsize=8)
    ax.plot(*dm, "o", color=K, ms=2); ax.text(dm[0] + 0.05, dm[1] + 0.05, "$dm$", fontsize=8)
    arrow(ax, P, C, lw=1.0); ax.text(0.85, 0.3, r"$\underline{R}_C$", fontsize=9)
    arrow(ax, C, dm, lw=1.0); ax.text(1.42, 1.2, r"$\underline{r}$", fontsize=9)
    arrow(ax, P, dm, lw=1.0, ls="--"); ax.text(0.4, 0.75, r"$\underline{\sigma}$", fontsize=9)
    ax.set_xlim(-0.3, 2.8); ax.set_ylim(-0.3, 1.7); clean(ax)
    save(fig, "parallel_axis.pdf")


if __name__ == "__main__":
    fig_vhoriz(); fig_conics(); fig_geosync(); fig_kepler2()
    fig_impulse(); fig_hohmann_bielliptic(); fig_hoh_be_dv(); fig_ell_hyp()
    fig_losses(); fig_staging()
    (_, _, _), (C1, C2, C3, C4) = jacobi_values(MU_EM)
    print("Earth-Moon Jacobi constants: C1=%.6f C2=%.6f C3=%.6f C4,5=%.6f" % (C1, C2, C3, C4))
    fig_zvc_cases()
    fig_zvc_single((C1 + C2) / 2, "zvc_noescape.pdf", "$C_2<C<C_1$: Earth–Moon transfer via $L_1$, no escape")
    fig_zvc_single((C2 + C3) / 2, "zvc_escape.pdf", "$C_3<C<C_2$: escape route through $L_2$")
    fig_lagrange(); fig_synodic(); fig_nbody()
    fig_eclipse(); fig_srp(); fig_harmonics(); fig_j2_effects(); fig_sso(); fig_drag(); fig_thirdbody()
    fig_sequence("euler"); fig_sequence("bryant")
    fig_polhodes(); fig_polhodes_diss(); fig_parallel_axis()
