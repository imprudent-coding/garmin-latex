# Elenco delle domande di teoria (Passo 1 di `docs/prompt_teoria.md`)

Fonti: `Theory_Questions_SFM.pdf` (EN) e `domande teoria mech.pdf` (IT), confrontate.
Regola: **una voce per ogni domanda così come è uscita**; si uniscono solo le ripetizioni (×n).
Sottoinsiemi → riga "If only X is asked" nella voce più ampia; aggiunte → voce a sé subito dopo la base.
Righe del sorgente riferite a `latex_notes/` (dopo l'errata #20).

## A. Orbital mechanics – Capp. 2, 3, 6

| Q | Domanda (sintesi) | Cap. | Sessioni / frequenza | Sorgente |
|---|---|---|---|---|
| A1 | Prove the first integral of angular momentum; application examples | 2 | Feb 2025 (×1, "2025's Q") | cap02.tex l.168–201 (+ l.589–615 θ̇*=h/r², l.797–848 circular) |
| A2 | General classification of Keplerian orbits in terms of *a* and *e* | 2 | elenco per capitolo (×1) | cap02.tex l.253–300, 554–587, 881–927 |
| A3 | Horizontal velocity at given altitude: trajectories vs. velocity magnitude | 2 | elenco per capitolo (×1) | cap02.tex l.532–552, 929–1005 |
| A4 | Geosynchronous/geostationary orbits; ground tracks for i, e zero/non-zero | 2 | Jan 2023 (×1) | cap02.tex l.850–868, 1657–1843 |
| A5 | Impulsive-thrust approximation: assumptions, effect on r and v, example valid / not valid | 3 | elenco per capitolo (×1) | cap03.tex l.18–113 |
| A6 | Compare Hohmann and bielliptic transfers (conditions under which each is optimal) | 3 | ×2 nell'elenco, Jan 2025, Jun 2025 | cap03.tex l.115–377 |
| A7 | Two optimal ways from an elliptic orbit to a hyperbolic path; global optimality | 3 | elenco per capitolo (×1) | cap03.tex l.379–401 |
| A8 | Losses w.r.t. Tsiolkovsky: ΔV-loss integrals and physical meaning | 6 | ×2, Sep 2024 | cap06.tex l.504–571 |
| A9 | Propulsive velocity; misalignment, gravity, drag losses; dependence on trajectory and LV features | 6 | Jul 2025 ("2025's Q") | cap06.tex l.356–571 |
| A10 | Staging: mass-distribution parameters of each stage; why staging | 6 | elenco per capitolo (×1) | cap06.tex l.164–224, 225–354 |
| A11 | Tsiolkovsky's law; total ΔV of a multistage rocket in m_p, m_s, m_u; structural coefficient, I_sp | 6 | Sep 2025 | cap06.tex l.21–224 |

Adiacenze: A8 ↔ A9 (stessi integrali; A9 chiede anche la velocità propulsiva e la dipendenza da traiettoria/veicolo);
A10 ↔ A11 (stessi parametri; A11 chiede la formula del ΔV totale e l'effetto di ε_s e I_sp).

## B. Capitolo 5 – Multibody / CR3BP

| Q | Domanda (sintesi) | Sessioni / frequenza | Sorgente |
|---|---|---|---|
| B1 | Earth–Moon CR3BP: Jacobi interval for Earth–Moon transfers without escape; zero-velocity curves (sketch) | ×2 nell'elenco, Jan 2023, Jul 2025 (+ "definition of the Jacobi integral") | cap05.tex l.379–445, 573–613 |
| B2 | Synodic frame and the five libration points; ZVC with no escape **and** with an escape route; C intervals | ×2, Feb 2025 ("single escape route outward") | cap05.tex l.259–305, 469–535, 573–613 |
| B3 | Collinear libration points: conditions and equation for their position | ×1 | cap05.tex l.469–508 |
| B4 | Synodic frame and coordinates; prove the Jacobi integral from the equations of motion | ×2, Sep 2024 ("Jacobi integral"), Jan 2025 ("from the Ω-derivative equations to the Jacobi integral"), Mar 2025 ("Jacobi integral") | cap05.tex l.259–413 |
| B5 | Synodic frame origin; positions of the primaries and gravitational parameters in terms of μ | ×1 | cap05.tex l.259–305 |
| B6 | Integrals of motion of the N-body problem; Laplace plane and its normal vector; prove H constant | ×2, Jun 2025, Sep 2025 (solo Laplace plane + vettore normale = sottoinsieme) | cap05.tex l.28–109 |

Adiacenze: B1 ↔ B2 (B2 aggiunge sinodico, 5 punti e il caso con via di fuga); B3 ↔ B2 (punti); B4 ↔ B5 (sinodico).

## C. Capitolo 8 – Perturbazioni

| Q | Domanda (sintesi) | Sessioni / frequenza | Sorgente |
|---|---|---|---|
| C1 | Solar radiation pressure: physical nature, fundamental formula, each term | ×3, Jan 2023 | cap08.tex l.561–687, 714–726 |
| C2 | SRP + geometry of eclipsing due to Earth (aggiunta a C1) | Jun 2025 | cap08.tex l.561–726 |
| C3 | J2: physical nature, two main averaged effects, dependence on latitude/longitude | ×1 | cap08.tex l.838–1062 |
| C4 | Physical nature of J2 and J22; number of meridians/parallels | ×1, Sep 2024 (insieme a C5) | cap08.tex l.728–868 |
| C5 | Three types of geopotential harmonics; dependence on lat/long; equipotential lines of J32 | ×1, Sep 2024 (insieme a C4) | cap08.tex l.728–836 |
| C6 | Sun-synchronous orbit: definition, perturbation used, prograde/retrograde (justify) | ×1 | cap08.tex l.1029–1099 |
| C7 | Exact third-body perturbing acceleration; effect on h of a circular Earth orbit | ×1 ("2025's Q"); Jan 2025 = natura fisica + formula esatta (sottoinsieme) | cap08.tex l.1101–1205, 1331–1453 |
| C8 | Gravity-gradient dyadic from the third-body formula; fundamental condition | ×2, Feb 2025, Sep 2025 | cap08.tex l.1211–1329 |
| C9 | Drag acceleration; effect on two orbit elements | Jul 2025, Mar 2025 ("aerodynamic drag") | cap08.tex l.398–559 |

Adiacenze: C1 ↔ C2; C3 ↔ C4 ↔ C5 ↔ C6 (J2/armoniche/SSO); C7 ↔ C8 (terzo corpo).

## D. Attitude dynamics – Capp. 9–11

| Q | Domanda (sintesi) | Cap. | Sessioni / frequenza | Sorgente |
|---|---|---|---|---|
| D1 | Bryant angles: names, intervals, elementary rotation sequence (inertial → body) | 9 | Jan 2023 | cap09.tex l.258–305 |
| D2 | Euler angles: names, sequence, ranges; geometric illustration | 9 | ×1, Mar 2025 ("Euler angles") | cap09.tex l.213–256 |
| D3 | Pros and cons of angle sequences vs Euler parameters | 9 | ×1 | cap09.tex l.207–212, 879–892 |
| D4 | Euler parameters: definition (principal axis/angle), fundamental properties | 9 | ×2, Sep 2025 ("at least two properties") | cap09.tex l.426–466, 681–701 |
| D5 | Euler parameters: definition; advantages over 3-angle sequences | 9 | ×1 | cap09.tex l.681–701, 879–892 |
| D6 | State and prove the parallel axis theorem | 11 | Jul 2025 | cap11.tex l.289–327 |
| D7 | Inertia dyad (no derivation) and inertia matrix; rotation of the inertia matrix between two frames | 11 | ×2, Jan 2025; Sep 2024 = solo diade + matrice (sottoinsieme) | cap11.tex l.60–274 |
| D8 | Torque-free equilibria; stability without dissipation; sketch momentum sphere ∩ energy ellipsoid | 11 | ×2, Feb 2025 | cap11.tex l.709–905 |
| D9 | Torque-free equilibria; stability **with** dissipation; define sphere and ellipsoid; sketch while energy decreases | 11 | Jun 2025 | cap11.tex l.709–905 |

Adiacenze: D1 ↔ D2 (sequenze); D3 ↔ D4 ↔ D5 (quaternioni); D6 ↔ D7 (inerzia); D8 ↔ D9 (equilibri).

## E. Possible further questions (argomenti T mai usciti finora)

Argomenti marcati T o T&N in `Exam_Course_INFO.pdf` non coperti da A–D. Stesso formato, risposte più brevi.

| Q | Argomento | Sorgente |
|---|---|---|
| E1 | Restricted two-body problem; potential of a spherical mass distribution | cap02.tex l.35–166 |
| E2 | Eccentricity vector: proof that it is a first integral, polar equation | cap02.tex l.203–251 |
| E3 | Specific energy, vis-viva, cosmic velocities | cap02.tex l.372–587, 929–945 |
| E4 | Position in time: eccentric anomaly and Kepler's equation | cap02.tex l.589–792 |
| E5 | Special trajectories: circular (force balance), ballistic, rectilinear | cap02.tex l.794–891 |
| E6 | 3D representation: ECI, LVLH, orbit elements | cap02.tex l.1007–1156 |
| E7 | Ground track: latitude limits, symmetry, motion along the track | cap02.tex l.1657–1855 |
| E8 | Three-dimensional impulsive transfers (in-plane / out-of-plane velocity changes) | cap03.tex l.451–565 |
| E9 | Sphere of influence; qualitative effect of a flyby | cap04.tex l.20–126, 522–600 |
| E10 | Problem of two bodies: relative and absolute motion | cap05.tex l.111–242 |
| E11 | Newton's law with propulsion: thrust, effective exhaust velocity, specific impulse | cap06.tex l.21–110 |
| E12 | Optimal staging (similar stages) and the ΔV limit | cap06.tex l.225–354 |
| E13 | Ascent trajectory: phases, launch-site equation, osculating elements | cap06.tex l.356–502 |
| E14 | Orbit perturbations: classification, magnitude vs altitude, Lagrange equations in vector form | cap08.tex l.41–118 |
| E15 | Euler's principal rotation theorem (statement) and remarks | cap09.tex l.426–680 |
| E16 | Euler's equations of attitude dynamics and kinetic energy | cap11.tex l.386–473 |
| E17 | Properties of the inertia matrix; symmetric spacecraft | cap11.tex l.178–384 |
| E18 | Torque-free motion of an axisymmetric body | cap11.tex l.475–678 |
| E19 | Attitude maneuvers of spinning satellites (spin-up/down, impulsive) | cap11.tex l.979–1100 |

Non inclusi: Cap. 10 (commentato in `latex_notes/main.tex`; i suoi contenuti T — quantità di moto, energia cinetica e
momento angolare di sistemi di punti e continui — sono richiamati in B6, D7, E16); Cap. 7 (solo N, tranne l'introduzione).

## Domande ambigue e interpretazione

- **Set. 2024, Q3**: "…stessa domanda dell'Ω di gennaio" (EN: "same question as the January one about Ω, i.e. the
  right-ascension-of-ascending-node problem"). Una sessione di gennaio prima di set. 2024 non è nella raccolta.
  Interpretazione: la seconda parte chiedeva la **regressione del nodo ⟨Ω̇⟩ dovuta a J2** (coperta da C3 e C6). Se invece
  si intendeva la funzione potenziale Ω del CR3BP (come in gen. 2025), è coperta da B4. Nota in testa a C3 e B4.
- **Gen. 2025, Q1**: "dalle eq. delle derivate di Ω fino all'integrale di Jacobi" = B4 (Ω è il potenziale del CR3BP).
- **Mar. 2025**: argomenti raccolti solo per titolo. "Jacobi integral" → B4 (e B1); "Euler angles" → D2;
  "Perturbations" (generico) → gruppo C (in particolare C3 e la panoramica E14); "Aerodynamic drag" → C9.
- **Set. 2024, Q2**: unione di C5 (tre tipi di armoniche, J32) e C4 (J2, J22): non è una voce nuova; C4 e C5 sono
  adiacenti e in testa a C5 c'è la nota.
- **Gen. 2025, Q3** (third body: natura fisica + formula esatta) ⊂ C7.
- **Giu. 2025, Q1** (Hohmann vs biellittico "discussing the conditions under which each option is optimal") = A6.
- **Lug. 2025, Q1** ("provide the definition of the Jacobi integral" + curve + intervallo) = B1.
- Formula di f₃B nei testi d'esame: `f3B = −μS/r2S³ (r21 + r1S) + μS/r21³ r21` = forma delle dispense (l.1257–1259)
  con 2 = S (Sole); in C8 è scritta con i simboli delle dispense.

## Checklist di copertura (Passo 4, verificata il 2026-10-07)

Ogni richiesta di ogni domanda (e delle varianti/sottoinsiemi) → dove è coperta nella risposta (paragrafo di `teoria/qX.tex`).

| Q | Sottorichieste | Coperta in |
|---|---|---|
| A1 | prova dell'integrale; esempi di applicazione | "Definition and proof"; "Application examples" (8 esempi) |
| A2 | classificazione in *a*; in *e* | "From the first integrals to the conics", "Semi-major axis", "Energy", tabella riassuntiva; rettilinee |
| A3 | traiettorie al variare di v₀ (orizzontale, quota data) | "The cases" (a)–(g) + figura calcolata; nota balistica |
| A4 | def. geosincrona; def. geostazionaria; proprietà; ground track i=0/≠0, e=0/≠0 | "Definitions"; "The four cases" + figura 2×2; "Properties" |
| A5 | ipotesi di validità; variazione di r e v; esempio valido; esempio non valido | "Validity assumptions"; "Effect of an impulse"; "Examples" |
| A6 | confronto Hohmann/biellittico; condizioni di ottimalità (giu. 2025) | Hohmann + prova di ottimalità; biellittico/biparabolico; "Comparison" con soglie 11.94/15.58 e tabella |
| A7 | due modi ottimali; ottimalità globale | "The two globally optimal strategies"; "Global optimality (discussion)" |
| A8 | definizione degli integrali; significato fisico | "Losses equation"; "Physical meaning"; "Typical values" |
| A9 | velocità propulsiva; perdite (disallineamento, gravità, aerodinamiche); dipendenza da traiettoria e veicolo | "Propulsive velocity"; tre paragrafi per perdita (traiettoria + veicolo); "Trade-off" |
| A10 | parametri di massa di ogni stadio; giustificazione dello staging | "Definitions" (ε_s, u₀, masse); "Why staging" |
| A11 | legge di Tsiolkovsky; ΔV totale in m_p, m_s, m_u; ε_s; I_sp; effetti su ΔV | "Tsiolkovsky's law"; formula riquadrata multistadio; due paragrafi sugli effetti |
| B1 | (def. integrale di Jacobi, lug. 2025); intervallo senza fuga; curve a velocità zero (disegno) | "Jacobi integral (definition)"; "Critical values"; riquadro C₂<C<C₁ + figura calcolata |
| B2 | sistema sinodico (def.); 5 punti (disegno); ZVC senza fuga; caso con via di fuga; intervalli | "Synodic frame"; "Libration points" + figura; "The two requested cases" + 2 figure; "All regimes" |
| B3 | disegno dei punti; condizioni dei collineari; equazione della posizione | figura; "Equilibrium conditions"; equazione riquadrata + 3 intervalli + forma in γ |
| B4 | def. sinodico e coordinate; prova dell'integrale; espressione | "Problem and synodic frame"; "Proof"; formula riquadrata; "Meaning" |
| B5 | def. sinodico e origine; posizioni dei primari in μ; parametri gravitazionali in μ | "Synodic frame"; "Positions of the primaries"; formula riquadrata |
| B6 | integrali del moto + espressioni; prova H costante; piano di Laplace; vettore normale (set. 2025) | punti 1–3; "Proof that it is constant"; "Laplace (invariant) plane" con n̂ = H_c/|H_c| |
| C1 | natura fisica; formula; ogni termine | "Physical nature"; "Radiation pressure"; elenco dei termini |
| C2 | come C1 + geometria dell'eclissi | "Physical nature and acceleration"; "Geometry of the eclipse" + figura; "Comments" |
| C3 | natura fisica di J₂; due effetti medi; dipendenza da latitudine/longitudine | "Physical nature"; "Dependence on latitude and longitude"; "The two main effects" |
| C4 | natura di J₂ e J₂₂; numero di meridiani/paralleli | due paragrafi + tabella; regola l−m paralleli, m meridiani |
| C5 | tre tipi; dipendenza lat/long; linee di J₃₂ (numero e tipo) | "The three types"; "The J₃₂ harmonic" + figura + tabella |
| C6 | definizione; perturbazione usata; diretta o retrograda + giustificazione | "Definition"; "Perturbation used"; "Prograde or retrograde?" |
| C7 | (natura fisica, gen. 2025); derivazione esatta; effetto su h in orbita circolare | "Physical nature"; "Derivation of the exact acceleration"; "Effect on the angular momentum" (4 passi) |
| C8 | prova del diadico; condizione fondamentale | "Starting point"; "Fundamental condition" (riquadrata); "The gravity-gradient dyad" |
| C9 | espressione; effetto su due elementi | "Drag acceleration"; "Effect on the elements: a and e decrease"; analisi quasi-circolare |
| D1 | angoli di Bryant: nomi, intervalli, sequenza inerziale→corpo | tabella; "Sequence of elementary rotations" + figura |
| D2 | nomi, sequenza, intervalli; illustrazione geometrica | tabella; "Sequence" + figura in 3 pannelli |
| D3 | pro e contro angoli vs quaternioni | tabella di confronto; "Discussion" |
| D4 | def. da asse e angolo principali; proprietà fondamentali (almeno due) | "Principal axis and angle"; "Definition"; proprietà (a)–(g) + matrice, cinematica |
| D5 | def. da asse e angolo; vantaggi sulle sequenze di 3 angoli | "Definition"; "Main advantages" (5 punti) |
| D6 | enunciato; dimostrazione | "Statement"; "Proof"; forma matriciale |
| D7 | diade (senza derivazione); relazione con la matrice; derivazione della trasformazione tra due sistemi | "Inertia dyad"; "Relation with the inertia matrix"; "Inertia matrix in two frames (derivation)" |
| D8 | condizioni di equilibrio; stabilità senza dissipazione; schizzo sfera ∩ ellissoide | "Equilibrium solutions"; "Linear stability"; "Momentum sphere and energy ellipsoid" + figura; tabella |
| D9 | condizioni di equilibrio; stabilità con dissipazione; def. sfera e ellissoide; schizzo con energia decrescente | "Equilibria"; "Momentum sphere and energy ellipsoid"; "Effect of internal energy dissipation" + figura; tabella |

Domande ambigue: nota in testa a B4 e C3 (Set. 2024 "Ω"), Mar. 2025 coperto da B4, D2, C9 e dal gruppo C/E14.
