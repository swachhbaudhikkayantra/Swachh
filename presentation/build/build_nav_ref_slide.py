"""Standalone reference slide 'Navigation Subsystem': deck slide 7 flowchart on top, then a first-principles
story (SLAM -> sensing -> drift -> loop closure -> where to go) on the left that arrives at RTAB-Map and Nav2 on the right.
Output: presentation/Navigation_Reference_Slide.pptx. No en/em dashes. Facts: paper Section VI, deck slide 7.
"""
import re, sys
sys.path.insert(0, '/home/hrishikesh/Swachh/presentation/build')
from lib2 import *
from pptx import Presentation

SRC = R + '/Major Project Phase 2 PPT.pptx'
OUT = R + '/presentation/Navigation_Reference_Slide.pptx'
TEAL = '17806D'; TINT = 'EAF1F8'; NB = ' '
LM = 0.5; RM = 9.5; CWD = RM - LM; TOP = 1.22

prs = Presentation(SRC)
sld = prs.slides._sldIdLst
for s_ in list(sld):
    prs.part.drop_rel(s_.rId); sld.remove(s_)
BLANK = [l for l in prs.slide_layouts if l.name == 'BLANK'][0]


def u(t):
    return re.sub(r'(?<=\d) (?=(%|ms|m|W|FPS|s|MB|M|h|kg|Hz|GB|Ah|V|cm|m/s)(?![A-Za-z0-9]))', NB, t)


s = prs.slides.add_slide(BLANK)
for ph in list(s.placeholders):
    ph._element.getparent().remove(ph._element)
s.shapes.add_picture(LOGO, Inches(8.98), Inches(0.2), Inches(0.56), Inches(0.552)).name = 'BMS logo'
T(s, LM, 0.3, 8.3, 0.6, 'Navigation Subsystem', size=26, color=K, font=FS, anchor='m', name='Title')

# ---- flowchart (same as deck slide 7) ----
stages = [('RTAB-Map SLAM', u('RGB-D + wheel odometry\n2D map, 5 cm cells'), ACC), ('Frontier explorer', u('our code, 2 Hz\npicks the next goal'), TEAL),
          ('Smac Hybrid-A*', u('Dubins, forward-only\n0.25 m turning radius'), ACC), ('MPPI controller', u('20 Hz, 2,000 samples\nup to 0.30 m/s'), ACC)]
bw, gap = 1.95, 0.4
for i, (h_, d_, col) in enumerate(stages):
    x = LM + 0.05 + i * (bw + gap)
    outline_box(s, x, TOP, bw, 0.78, color=col, lw=1.75 if col == TEAL else 1.0, fill=TINT if col == TEAL else None)
    T(s, x + 0.12, TOP + 0.03, bw - 0.24, 0.72, [{'t': h_, 'font': FS, 'size': 11.5, 'after': 1, 'color': col if col == TEAL else K}] + [{'t': ln, 'size': 9.5, 'color': K2} for ln in d_.split('\n')], anchor='m')
    if i < 3: arrow(s, x + bw + 0.04, TOP + 0.39, x + bw + gap - 0.04, TOP + 0.39, color=K2, w=1.0)
xl = LM + 0.05 + bw / 2; xr = LM + 0.05 + 3 * (bw + gap) + bw / 2
vline(s, xr, TOP + 0.78, TOP + 0.96, color=K2, w=1.0); hline(s, xl, TOP + 0.96, xr, color=K2, w=1.0); arrow(s, xl, TOP + 0.96, xl, TOP + 0.81, color=K2, w=1.0)
# bracket: the planner and controller are both Nav2
x3 = LM + 0.05 + 2 * (bw + gap); x4e = LM + 0.05 + 3 * (bw + gap) + bw; yb = TOP - 0.1
hline(s, x3, yb, x4e, color=ACC, w=1.0); vline(s, x3, yb, TOP - 0.02, color=ACC, w=1.0); vline(s, x4e, yb, TOP - 0.02, color=ACC, w=1.0)
lbl = T(s, (x3 + x4e) / 2 - 0.3, yb - 0.12, 0.6, 0.24, [{'t': 'Nav2', 'align': 'c'}], size=10.5, color=ACC, font=FS, anchor='m')
lbl.fill.solid(); lbl.fill.fore_color.rgb = rgb('FFFFFF')
T(s, 3.0, TOP + 0.98, 4.0, 0.2, [{'t': 'the map keeps growing, so the loop repeats until no frontier is left', 'align': 'c'}], size=8.5, color=G)


def H(t_, first=False):
    return {'t': t_, 'font': FS, 'color': ACC, 'size': 12, 'after': 3, 'before': 0 if first else 6}


def B(lead, t_, num=None):
    runs = ([(lead + ' ', {'font': FS})] if lead else []) + [(u(t_), {})]
    d = {'runs': runs, 'size': 11, 'after': 6, 'indent': 0.18}
    d.update({'bullet': True, 'bucolor': ACC})
    return d


y0 = TOP + 1.3; hh = 5.05 - y0
# ---- left: first principles ----
lw = 4.0
T(s, LM, y0, lw, hh, [
    H('From first principles', True),
    {'runs': [('SLAM ', {'font': FS, 'color': TEAL}), ('(Simultaneous Localisation and Mapping): build a map of an unknown space while locating the robot on it.', {})], 'size': 11, 'after': 6},
    B('Problem:', 'no floor plan and no known position.'),
    B('Sensing:', 'wheel odometry drifts; the depth camera sees the room, and recognising a revisited place (loop closure) removes the drift.'),
    B('Next:', 'choose where to go, plan a path the robot can drive, follow it safely.')],
  size=11, color=K)
vline(s, LM + lw + 0.2, y0 + 0.05, 5.0, color=HAIR)
# ---- right: our stack ----
rx = LM + lw + 0.4; rw = RM - rx
T(s, rx, y0, rw, hh, [
    H('RTAB-Map: our SLAM', True),
    B(None, 'Depth camera + wheel odometry into a 2D grid of 5 cm cells, with loop closure'),
    B('Why:', 'open source, fits the 8 GB Jetson, most accurate indoors vs ORB-SLAM3 and OpenVSLAM'),
    H('Nav2: planning and control'),
    B('Plan:', 'Smac Hybrid-A* finds a drivable path: forward-only, 0.25 m turning radius'),
    B('Follow:', 'MPPI tries 2,000 motions, 20 times a second, and runs the best')],
  size=11, color=K)

T(s, LM, 5.12, 7.6, 0.2, 'Source: paper Section VI, Tables 4 and 5; RTAB-Map comparison: Merzlyakov and Macenski, IROS 2021', size=8, color=G, name='Source note')
T(s, LM, 5.33, 4.0, 0.18, 'Swachh Bauddhika Yantra  |  Department of CSE, BMSCE', size=8, color=G, name='Footer')
s.notes_slide.notes_text_frame.text = (
    "Start from the basic problem. Dropped into a new building, the robot has no floor plan and does not know where it is, and it needs both to move with purpose. "
    "SLAM, simultaneous localisation and mapping, solves both at once: it builds the map while locating the robot on it. Wheel odometry tells us how far the wheels turned, "
    "but small errors add up into drift. The depth camera sees the room in colour and depth. Fusing the two keeps the pose in check, and when the robot recognises a place "
    "it has seen before, a loop closure corrects the drift. We use RTAB-Map for this: it produces a 2D grid of 5 centimetre cells, updated once a second. We chose it because "
    "it is open source, works with any odometry, fits the 8 gigabyte Jetson and was the most accurate indoors in a published comparison. But a map alone does not move the robot. "
    "Our frontier explorer picks where to go next, and Nav2 gets it there: Smac Hybrid-A star plans a path the robot can actually drive, forward only with a 0.25 metre turning radius, "
    "and the MPPI controller tries 2,000 possible motions twenty times a second and executes the best, while the costmaps keep a safety margin from obstacles. "
    "As the robot moves the map grows, and the loop repeats until no frontier is left.")
prs.save(OUT)
print('saved', OUT)
