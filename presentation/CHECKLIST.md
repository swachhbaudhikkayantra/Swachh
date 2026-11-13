# Presentation + Poster: Task Checklist

Any agent can pick this up. Tick items (`[x]`) as they finish and add a one-line note.
Working folder: `presentation/` (generator scripts and intermediates in `presentation/build/`).

## Deliverables
- `presentation/Swachh_Final_Presentation.pptx`: judges' deck (industry panel)
- `presentation/Swachh_Poster.pptx`: poster in the `Sample-Poster.pptx` format
- `presentation/CONTENT_FACTS.md`: every number/claim used, with its source (single source of truth so deck and poster stay consistent)

## Hard requirements (from the user)
- Deck slide 1 must be IDENTICAL to slide 1 of `Major Project Phase 2 PPT.pptx`
- BMS logo top-right on EVERY deck slide
- Focus: the 2 subsystems (Navigation, Object Detection) + manual mode on hardware; also show full project scope, what is DONE, what is LEFT
- Submitted Paper.pdf / my_paper.txt is the primary source; nothing invented beyond the sources
- Poster follows Sample-Poster.pptx format
- Deck and poster content consistent

## Steps
### 1. Source extraction
- [x] Extract text of `my_paper.txt` (paper) → key facts
- [x] Extract `Major Project Phase 2 PPT.pptx` text + thumbnails; locate BMS logo image + slide-1 XML
- [x] Extract `SBY_IEEE_Video_Deck.pptx` text + thumbnails + reusable figures
- [x] Extract `Sample-Poster.pptx` structure (size, sections, fonts)
- [x] Skim `Major Project Phase 1.pdf` (low priority, scope/vision only)
- [x] Paper figures available (docs/paper_out or results)?

### 2. Navigation verification (subagent)
- [x] Subagent verifies README.md claims vs code and results → `presentation/NAV_VERIFICATION.md`
- [x] Reconcile its findings into CONTENT_FACTS.md

### 3. Content
- [x] Write `CONTENT_FACTS.md` (facts + sources, done vs left)
- [x] Storyline / slide outline (in this file, below)

### 4. Deck
- [x] Generator script `build/build_deck.py` (python-pptx; opens Phase 2 PPT, keeps slide 1, adds 18 slides; helpers in `build/lib_pptx.py`)
- [x] Merge: slide 1 copied verbatim from Phase 2 PPT + logo on every slide
- [x] validate.py passes
- [x] Render to images, visual QA, fix

### 5. Poster
- [x] Build from Sample-Poster.pptx format (`build/build_poster.py`: keeps sample master, logo, title placeholder, author table)
- [x] validate.py passes
- [x] Render, visual QA, fix

### 6. Final
- [x] Cross-check deck vs poster vs CONTENT_FACTS numbers
- [x] Report to user

## Notes / status log
- Tooling (no system installs): node + pptxgenjs + python-pptx venv live in the session scratchpad; if gone, recreate: Linux node tarball + `npm i pptxgenjs`, `python3 -m venv --without-pip` + get-pip + `pip install python-pptx`. Rendering: `build/tools/render.sh deck.pptx outdir` (Windows PowerPoint COM, accurate). Contact sheets: `build/tools/grid.py`.
- Sources extracted: `build/phase2.md`, `build/video.md`, `build/poster.md`, `build/paper_rest.txt` (paper body, comments stripped), `build/paper_pdf.txt`; paper images in `build/paperimg/` (img-014 architecture, img-016 robot, img-017 HMI, img-021..026 dataset samples, img-029 YOLO arch, img-032 RF-DETR arch, img-039 actual-vs-explored, img-041 trajectories). Phase 2 unpacked in `build/p2x/` (BMS logo = ppt/media/image5.jpg; robot-driving photo image11.jpg; HMI-on-robot image14.jpg).
- Submitted PDF == my_paper.txt on all headline numbers (checked).
- NAV_VERIFICATION.md done. Decision: manual mode presented only with code-verified features (HMI touchscreen, MOVE/SPEED 1-9/ESTOP/RESET, ACK + 1 Hz status, 2 PWM + direction relays). Paper claims with no code (voice STOP, encoders, 30cm/15deg commands, HMI video, startup self-check, vacuum/arm actuation) go under 'designed / left to do', never 'done'.
- Deck DONE (19 slides): `presentation/Swachh_Final_Presentation.pptx`. Slide 1 verified c14n-identical to Phase 2 slide 1 incl. media. validate.py PASS. Rebuild: `<venv>/bin/python build/build_deck.py`; outline is in CONTENT_FACTS.md. Speaker notes on every slide.
- Poster DONE: `presentation/Swachh_Poster.pptx` (22 x 14.1 in, Sample-Poster format: Introduction / Objectives / Proposed System | Methodology | Results / Conclusion). validate.py PASS; PowerPoint render checked, nothing overflows.
- Numbers cross-check: every number in deck + poster text found verbatim in paper / NAV_VERIFICATION / Phase 2 / video deck, except 3-decimal roundings on the poster (0.821, 0.894, 0.900).
- Alt text added to all photos and figures (lib_pptx.ALT).
- Open items for the user (not blocking): (1) paper claims voice STOP / encoders / 30 cm-15 deg commands / HMI video with no code behind them; deck lists them as 'left' only. (2) Paper-internal inconsistencies: spec table says '12 V DC servo motors', text says BLDC hub motors (deck uses BLDC); dataset text says 873 images, tables say 877 (deck uses 877). (3) Poster 5th author column credits Anand Iyer + Vishwajeet Gokhale as 'In collaboration with' (from Phase 2 slide 4 + paper acknowledgement); confirm wording.

## Round 2 (user feedback 2026-11-12): "looks AI-generated"
Feedback: deck looks AI-made; add paper Fig. 7 (exploration trajectories) to deck AND poster; poster: remove green/red coloured boxes; make it look hand-made by a professional.
Design direction (researched: assertion-evidence (Alley, Penn State), consulting action titles + source notes, #betterposter whitespace):
- Sentence headlines (assertion), evidence = real figure / photo / chart; no icon circles, no pastel card grids, no chips/chevrons, no caps kickers, no section tracker.
- White, charcoal text, ONE accent (deep blue 1F4E79) + muted grey for context; red only to mark a failure in a chart.
- Segoe UI / Segoe UI Semibold; booktabs tables (rules only, no fills); charts with direct labels, grey context + accent highlight; "Source: paper Fig./Table" notes.
- Status shown as a matrix with ● ◐ ○ markers instead of coloured boxes.
v1 backed up in build/ (*_v1.*).
- [x] Deck v2 (build/build_deck.py rewritten)
- [x] Fig. 7 on deck (exploration slide)
- [x] Poster v2: Fig. 7 added; green/red boxes removed; stat cards + stage boxes de-boxed
- [x] Validate + PowerPoint render QA both
- Round 2 DONE. Deck v2 = 20 slides (assertion-evidence; Fig. 7 on slide 10, Fig. 6 on slide 11; status matrix slide 4). Poster v2: Fig. 7 beside Fig. 6 in Results; no coloured boxes; tables white with rules only. Both validate.py PASS; PowerPoint renders checked. Numbers cross-check: deck 0 unmatched; poster only 3-decimal roundings.
- Fonts: deck uses Segoe UI / Segoe UI Semibold (on every Windows PC; a Mac would substitute). Poster keeps the sample's Times New Roman + Calibri.
- Non-breaking spaces bind numbers to units in both builders (regex pass); keep using '\u00a0' in new text.

## Round 3 (user): "a touch more colour", reduce to 13 slides (keep content), old slide 8 (formula + 6 numbered steps grid) looks AI
Plan (v2 backed up as build/*_v2.*): 1 title | 2 problem | 3 architecture | 4 prototype+manual mode | 5 nav loop + explorer (explorer as spec table, no numbered grid) | 6 exploration Fig.7 + method | 7 mapping Fig.6 | 8 goals + avoidance + reaction | 9 dataset | 10 models + accuracy | 11 Jetson edge | 12 status matrix + next steps | 13 lessons + sim-vs-real + thank you.
Colour: key phrase of each headline in accent blue; teal second accent (done/on-robot, 2nd chart series); light blue tinted panels behind one block per slide; red only for failures.
- [x] Deck v3 built (13 slides)
- [x] Validate + render QA
- Round 3 DONE. Mid-round user requests also done:
  - Applied slideworks.io McKinsey guide: slide 2 is now an SCR executive summary (Situation, Complication, Resolution); action titles <= 2 lines, same size; source + page number on every slide; next steps start with verbs.
  - All en/em dashes removed from deck (incl. notes) and poster (ranges written 'X to Y'; 'n/a' in status matrix). Verified 0 in extracted text. Formula keeps the mathematical minus sign (U+2212).
  - Poster tables: no white fill; navy rules + muted inner hairlines on the panel colour. Proposed System figure: white converted to transparency (build/arch_transparent.png). Figs 6/7: framed white plates with a thin border.
  - Poster is now EXACT A3 landscape (420 x 297 mm): build_poster.py builds at sample size (saved as build/Swachh_Poster_large.pptx) then rescales master + content (pictures keep aspect; fonts x0.80, min 8 pt). Print file: presentation/Swachh_Poster_A3.pdf (pdfinfo: A3).
- Deck v3 = 13 slides: 1 title (verbatim) | 2 exec summary SCR | 3 architecture | 4 prototype + manual mode | 5 nav loop + explorer spec table | 6 exploration (Fig. 7) + method | 7 mapping (Fig. 6) | 8 goals + avoidance + reaction | 9 dataset | 10 models + accuracy | 11 Jetson edge | 12 status matrix + next | 13 lessons + sim-vs-real + thank you.
- Dropped vs v2 (content kept elsewhere or in notes): test-worlds figure (method summarised on slide 6), YOLO/RF-DETR architecture diagrams, motor-controller and camera spec rows (in notes / slide 3), closing big-number row.
- Round 4 (user: Proposed System diagram too small to read): paper Fig. 1 redrawn natively in PowerPoint shapes in build_poster.py (same layers, boxes, labels, connections; stacked Interface|Sensor / Processing / Actuator to fit the column). Labels print at ~8 pt on A3 (the image version printed ~3 pt). The layer paragraph under the figure was dropped (the diagram now carries it); operating modes condensed to one paragraph. A3 PDF re-exported.
- Round 4 REVERTED at user's request: Proposed System is back to the paper Fig. 1 image (transparent background) with the layer paragraph and three-line operating modes. A3 PDF re-exported.
- Round 5 (poster readability, user list): Operating Modes = 3 boxed items under Introduction (Manual box has a heavier border, marked IMPLEMENTED); frontier equation now has a lead-in ("How the explorer chooses where to go") + 3-column legend; custom dataset highlighted in a callout (877 images, 6,349 annotations, 8 classes, split) and results headings/notes say "on our custom dataset"; manual mode = boxed signal chain (HMI > Jetson > Arduino > PWM + relays > hub motors) + 3 bullets; section A renamed "Hardware prototype, HMI and manual mode"; navigation stages in boxes; Proposed System layers as 4 bullets; nav results table narrowed with key numbers (29.2 %, 19/20, 4/6, 260 ms) to its right (old number row removed). Previous builder kept as build/build_poster_v2.py. A3 PDF re-exported.
- Round 6: operating modes = plain ruled table (Mode / What the operator does / Status; Manual = Working); dataset callout box removed (bold lead sentence instead); formula paragraph now says where S is used (inside the frontier explorer, between mapping and planning; result goes to Smac Hybrid-A* as the next goal) and the explorer box reads 'chooses goal by S'. A3 PDF re-exported.
- Round 7: operating modes table = 2 columns (Mode | What it does), each row 1 to 2 lines, status folded into the text. A3 PDF re-exported.
- Round 8 (story order): deck v4 = 15 slides: 1 title | 2 problem | 3 solution SBY (architecture, what it does, how it closes gaps) | 4 operating modes table | 5 what we built (status matrix) | 6 prototype + manual mode | 7 navigation (formula with context + n/d/p table) | 8 custom dataset | 9 models | 10 results exploration Fig 7 | 11 results mapping Fig 6 | 12 results goals/avoidance | 13 results detection on custom dataset + Jetson | 14 conclusion | 15 future work + thank you. v3 kept as build/build_deck_v3.py.
  Poster: col 1 Introduction > Proposed System (SBY sentence + Fig 1 + layers) > Operating Modes (2-col table, mode + status, 3-line descriptions, one-execution-path note); Objectives removed. Col 2 heading 'What We Built'; formula block now 'How the robot decides where to explore next' with lead-in, legend and what happens to the result. Col 3 Conclusion then Future Work heading (Done list removed; covered by col 2). v3 kept as build/build_poster_v3.py.
- Round 9 (user: headings must not be stories; remove status-matrix slide; custom dataset separate; more content everywhere; follow Phase 1/2 style): deck v5 = 21 slides with topic titles (Outline, Problem Statement, Proposed Solution, Operating Modes, Hardware Prototype, Manual Mode on Hardware, Navigation Subsystem, Frontier Exploration, Custom Built Dataset, Custom Dataset: Annotation and Augmentation, Trash Detection Models, Evaluation Setup, Results x5, Conclusion, Future Work, Thank You). Dense sub-headed bullets beside figures/tables, like Phase 2. Status-matrix slide removed. v4 kept as build/build_deck_v4.py.
- Round 10: deck v6 = 22 slides. Added 'Project Scope' (slide 6: platform + 2 subsystems built; beyond-this-phase strip; CSE/ECE split). Flow fixed: section-labelled titles (Navigation: ..., Trash Detection: ...); Evaluation Setup now covers BOTH subsystems (Gazebo campaigns + custom-dataset/Jetson protocol) so it bridges design -> results. Conclusion rebuilt around the 3 scope areas + lessons + limitations panel. Gaps on slides 4, 7, 16, 17 filled. v5 kept as build/build_deck_v5.py.
- Round 11: deck v7 = EXACTLY 15 slides (user cap: 15 max). Merged: hardware+manual mode; dataset+annotation; exploration+mapping results; detection accuracy+Jetson; future work+thank you. Outline and separate Evaluation Setup removed (test method now stated on each results slide). Operating modes and manual mode use the Project Scope column-with-dividers style; every table has column dividers (lib2.btable vgrid); slide-10 blue box removed; conclusion panel removed. v6 kept as build/build_deck_v6.py.
- Round 12: poster column 2 heading 'What We Built' -> 'Methodology' (no other text change needed). A3 PDF re-exported.
- Round 13: second poster, CONCISE version (same layout/sections/headings/figures/tables, text cut to talking points, larger type): presentation/Swachh_Poster_Concise.pptx + Swachh_Poster_Concise_A3.pdf (exact A3). Builder: build/build_poster_concise.py. Original poster untouched.

## Round 14: standalone "What Has Been Built?" slide
- [x] One-slide file What_Has_Been_Built_Slide.pptx (build/build_built_slide.py): intro line + 3 parallel boxes (prototype + manual mode, navigation, trash detection). Deck style, BMS logo, validate passes, 0 dashes. Main 15-slide deck untouched.
- [x] Reference slide Navigation_Reference_Slide.pptx (build/build_nav_ref_slide.py): deck slide 7 flowchart + first-principles story (SLAM, sensing, fusion/loop closure, next) arriving at RTAB-Map and Nav2. Validate passes, 0 dashes. Main deck untouched.
