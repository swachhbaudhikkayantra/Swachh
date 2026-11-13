"""v7 deck: exactly 15 slides. Topic titles, Phase 1/2 content density, column layouts with vertical dividers
(the 'Project Scope' style the user liked), every table with column dividers, no blue boxes except the scope strip.
Story: problem -> solution (SBY) -> modes -> scope -> prototype + manual mode -> navigation -> frontier explorer
-> custom dataset -> models -> results (navigation x2, detection) -> conclusion -> future work + thank you. No en/em dashes.
Slide 1 = slide 1 of 'Major Project Phase 2 PPT.pptx', verbatim. BMS logo top-right on every slide.
Run: <venv>/bin/python build_deck.py      (earlier versions kept as build_deck_v1.py .. build_deck_v6.py)
"""
import re
import sys
sys.path.insert(0, '/home/hrishikesh/Swachh/presentation/build')
from lib2 import *
from lib2 import btable as _btable
from pptx import Presentation

SRC = R + '/Major Project Phase 2 PPT.pptx'
OUT = R + '/presentation/Swachh_Final_Presentation.pptx'
TEAL = '17806D'; TINT = 'EAF1F8'; NB = ' '; DIV = 'BFC7D2'

prs = Presentation(SRC)
sld = prs.slides._sldIdLst
for s_ in list(sld)[1:]:
    prs.part.drop_rel(s_.rId); sld.remove(s_)
BLANK = [l for l in prs.slide_layouts if l.name == 'BLANK'][0]
state = {'n': 1}
LM = 0.5; RM = 9.5; CWD = RM - LM
TOP = 1.12


def btable(*a, **k):
    """every deck table gets column dividers and row hairlines"""
    k.setdefault('vgrid', DIV); k.setdefault('grid', 'D6DCE4')
    return _btable(*a, **k)


def u(t):
    return re.sub(r'(?<=\d) (?=(%|ms|m|W|FPS|s|MB|M|h|kg|Hz|GB|Ah|V|cm|g|rpm|rad/s|m/s)(?![A-Za-z0-9]))', NB, t)


def slide(title, notes, source=None):
    s = prs.slides.add_slide(BLANK)
    for ph in list(s.placeholders):
        ph._element.getparent().remove(ph._element)
    state['n'] += 1
    s.shapes.add_picture(LOGO, Inches(8.98), Inches(0.2), Inches(0.56), Inches(0.552)).name = 'BMS logo'
    T(s, LM, 0.3, 8.3, 0.6, title, size=26, color=K, font=FS, anchor='m', name='Title')
    if source:
        T(s, LM, 5.12, 7.6, 0.2, source, size=8, color=G, name='Source note')
    T(s, LM, 5.33, 4.0, 0.18, 'Swachh Bauddhika Yantra  |  Department of CSE, BMSCE', size=8, color=G, name='Footer')
    T(s, 9.0, 5.33, 0.5, 0.18, [{'t': str(state['n']), 'align': 'r'}], size=8, color=G, name='Slide number')
    s.notes_slide.notes_text_frame.text = notes
    return s


def panel(s, x, y, w, h, fill=TINT):
    p = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    p.fill.solid(); p.fill.fore_color.rgb = rgb(fill); p.line.fill.background(); p.shadow.inherit = False
    p.name = 'Panel'
    return p


def cap(s, x, y, w, txt, h=0.22, align='l'):
    return T(s, x, y, w, h, [{'t': u(txt), 'align': align}], size=8.5, color=G)


def blk(s, x, y, w, h, items, size=10.5, hcolor=ACC):
    """items: ('h', heading) | ('s', status line) | ('b', text) | ('b', lead, text) | ('p', text) | ('m', monospace line)"""
    paras = []
    for it in items:
        k = it[0]
        if k == 'h':
            paras.append({'t': it[1], 'font': FS, 'color': hcolor, 'size': size + 1, 'after': 2, 'before': 5 if paras else 0})
        elif k == 's':
            paras.append({'t': it[1], 'font': FS, 'color': it[2] if len(it) > 2 else TEAL, 'size': size, 'after': 4})
        elif k == 'b':
            runs = ([(it[1] + ' ', {'font': FS})] if len(it) == 3 else []) + [(u(it[-1]), {})]
            paras.append({'runs': runs, 'bullet': True, 'bucolor': ACC, 'size': size, 'after': 2, 'indent': 0.15})
        elif k == 'm':
            paras.append({'t': it[1], 'font': MONO2, 'size': size - 1, 'color': K, 'after': 2})
        else:
            paras.append({'t': u(it[1]), 'size': size, 'after': 3})
    return T(s, x, y, w, h, paras, size=size, color=K)


def columns(s, y0, h, cols, size=10, gap=0.25, x0=LM, width=CWD):
    """slide-6 style: equal columns separated by vertical divider lines"""
    n = len(cols); cw = (width - gap * (n - 1)) / n
    for i, items in enumerate(cols):
        x = x0 + i * (cw + gap)
        if i: vline(s, x - gap / 2, y0 + 0.03, y0 + h - 0.05, color=HAIR)
        blk(s, x, y0, cw, h, items, size=size)
    return cw


# ======================= 2. Problem statement =======================
s = slide('Problem Statement',
          "Large indoor spaces like offices, campuses, hospitals and factories are still cleaned largely by hand. That is slow and inconsistent, and in industrial settings workers can unknowingly handle hazardous waste. The robots on the market vacuum or mop, but none of them combines autonomous navigation, AI-based trash detection and arm-based collection. Our literature survey found two specific gaps: deep-learning trash detection in cleaning robots relies on external processing, and onboard detection has not been integrated with autonomous navigation. That creates the need for one robot that can navigate, detect trash with deep learning and collect it, with continuous, partial or no human intervention. The work also aligns with SDG 11. The photo is from our own dataset: what the robot actually sees.",
          source='Source: paper Sections I and II; Major Project Phase 1 and Phase 2 problem statement and SDG slides; photo from the SBY dataset')
blk(s, LM, TOP + 0.05, 5.2, 3.95, [
    ('h', 'The problem'),
    ('b', 'Labour-heavy.', 'Manual cleaning of large indoor environments relies on human labour, making it slow, inconsistent and unproductive.'),
    ('b', 'Unsafe.', 'In industrial settings, workers may unknowingly handle hazardous or dangerous waste during routine cleaning.'),
    ('b', 'Narrow robots.', 'Current robotic systems only address tasks like vacuuming and scrubbing; they lack the combination of autonomous navigation, AI-based trash detection and robotic arm-based collection.'),
    ('h', 'Gaps identified in the literature survey'),
    ('b', 'Deep-learning trash detection in cleaning robots relies on external processing rather than running on the robot.'),
    ('b', 'Onboard deep-learning trash detection is not integrated with autonomous navigation.'),
    ('h', 'Need'),
    ('b', 'A scalable, reliable, autonomous robot that navigates, detects trash using deep learning and collects it, with continuous, partial or no human intervention.'),
    ('b', 'SDG 11:', 'consistent sanitation without over-reliance on human labour, in line with the Swachh Bharat Mission.')], size=10.5)
picture(s, PIMG + '/img-022.png', 5.95, TOP + 0.08, 3.55, 3.75, crop='fill')
cap(s, 5.95, TOP + 3.85, 3.55, 'Paper waste on a lab floor, seen from the robot\'s camera')

# ======================= 3. Proposed solution =======================
s = slide('Proposed Solution: Swachh Bauddhika Yantra',
          "Our proposed solution is Swachh Bauddhika Yantra, SBY: an autonomous indoor cleaning robot with a six-degree-of-freedom robotic arm. It navigates, detects and classifies trash, picks it up and vacuums dust, with all computation on board. The architecture has four layers. The interface layer is the HMI, with a microphone and speaker in the design. The sensor layer is an RGB camera, a RealSense D435i depth camera and wheel encoders. The processing layer runs on a Jetson Orin Nano with two major modules, object detection and visual SLAM, and a Decision module that fuses them into one action. The actuator layer is an Arduino Uno that drives the motors, arm and vacuum, and it is actuator-agnostic. The table shows the fusion rule. Because detection runs on the robot and is joined to navigation through the Decision module, SBY addresses both gaps.",
          source='Source: paper Section III (Fig. 1, Table 6); Major Project Phase 2 High Level and Detailed Design')
picture(s, PIMG + '/img-014.png', LM - 0.05, TOP + 0.02, 5.4, 2.29)
cap(s, LM, TOP + 2.33, 5.3, 'Four-layer architecture of SBY (paper Fig. 1)')
dec = [['Detected class', 'Action (automatic mode)'], ['bottle, plastic wrapper, paper, foil', 'activate robotic arm'], ['obstacle', 're-plan path']]
btable(s, LM, TOP + 2.65, 5.3, dec, [2.8, 2.5], row_h=0.27, size=10, align=['l', 'l'], hcolor=ACC,
       cell_colors={(1, 1): TEAL, (2, 1): ACC}, cell_fonts={(1, 1): FS, (2, 1): FS})
T(s, LM, TOP + 3.5, 5.3, 0.45, 'Decision fusion: classes are defined by the cleaning action they need, so detections map straight to an action.', size=9.5, color=K2)
vline(s, 5.88, TOP + 0.05, TOP + 3.9, color=HAIR)
blk(s, 6.05, TOP + 0.02, 3.45, 3.95, [
    ('h', 'What SBY is'),
    ('p', 'An autonomous indoor cleaning robot with a 6-DOF arm: it navigates, detects and classifies trash, picks it up and vacuums dust, with all computation on board.'),
    ('h', 'Four layers'),
    ('b', 'Interface:', 'HMI touchscreen; audio input and speaker in the design'),
    ('b', 'Sensor:', 'RGB camera, RealSense D435i depth camera, wheel encoders'),
    ('b', 'Processing:', 'Jetson Orin Nano runs object detection and visual SLAM; the Decision module fuses them'),
    ('b', 'Actuator:', 'Arduino Uno drives motors, arm and vacuum; new actuators can be added'),
    ('h', 'How it closes the gaps'),
    ('b', 'Detection runs on the robot\'s own Jetson, not an external computer'),
    ('b', 'The Decision module joins detection with navigation')], size=10)

# ======================= 4. Operating modes =======================
s = slide('Operating Modes',
          "SBY is designed for three operating modes. Dividing the functionality into modes is a core design choice: it makes the robot easy to use and gives a clear structure to what each part does. In manual mode, the operator monitors the area on the HMI and controls direction, speed, cleaning area and tasks, and sees warnings, alerts and robot status. It suits precise control in high-traffic or sensitive areas, and it runs on the robot today. In semi-automatic mode, the operator selects the area, the type of cleaning and the duration, and the robot takes over and cleans that area on its own. In automatic mode the operator only monitors: the robot uses its map to find areas that need cleaning, and its detector decides the action. Semi-automatic and automatic modes are planned; they will run on the navigation and detection subsystems we built in this phase. In every mode, manual and autonomous commands share one execution path, and the emergency stop halts the robot until it is reset.",
          source='Source: paper Section III (operating modes); Major Project Phase 2; manual mode verified in firmware and HMI code')
T(s, LM, TOP, CWD, 0.5, 'SBY works in three modes. Dividing functionality into modes keeps the robot easy to use and gives each part a clear role, from full operator control to fully hands-off cleaning.', size=11, color=K2)
columns(s, TOP + 0.62, 2.75, [
    [('h', 'Manual mode'), ('s', 'Working on the robot today'),
     ('b', 'Operator:', 'monitors the area on the HMI; controls direction, speed, cleaning area and tasks such as vacuuming and spot cleaning'),
     ('b', 'Robot:', 'executes each command; the HMI shows warnings, alerts and robot status'),
     ('b', 'Best for:', 'precise control in high-traffic or sensitive areas')],
    [('h', 'Semi-automatic mode'), ('s', 'Planned', G),
     ('b', 'Operator:', 'selects the area, the type of cleaning (vacuuming, mopping, scrubbing) and the duration; watches alerts'),
     ('b', 'Robot:', 'takes over and cleans the defined area on its own'),
     ('b', 'Best for:', 'routine or less complex cleaning; frees the operator for other tasks')],
    [('h', 'Automatic mode'), ('s', 'Planned', G),
     ('b', 'Operator:', 'gives no input; only monitors the analysis and alerts'),
     ('b', 'Robot:', 'uses its map to find areas that need cleaning; its detector decides the action and adapts as the scene changes'),
     ('b', 'Best for:', 'large or complex areas needing continuous, hands-off cleaning')]], size=10.5)
hline(s, LM, TOP + 3.45, RM, color=HAIR)
T(s, LM, TOP + 3.52, CWD, 0.45, [
    {'runs': [('Safety in every mode: ', {'font': FS, 'color': ACC}), ('manual and autonomous commands share one execution path, and the HMI emergency stop halts the robot until it is reset.', {})], 'after': 2},
    {'runs': [('This phase: ', {'font': FS, 'color': TEAL}), ('manual mode runs on the robot; the other two modes will use the navigation and detection subsystems built next.', {})]}],
  size=10, color=K2)

# ======================= 5. Project scope =======================
s = slide('Project Scope',
          "This slide sets the scope. SBY as a whole is meant to navigate, detect trash, pick it up with the arm and vacuum, in three operating modes. This project builds its foundation in three parts. First, the platform: the hardware prototype, with manual mode running on the robot through the HMI. Second, subsystem one, navigation: mapping with RTAB-Map, our frontier explorer for autonomous exploration, and Nav2 planning and control with obstacle avoidance, built and evaluated in the Gazebo simulator. Third, subsystem two, trash detection: our custom dataset, three detectors trained and compared, and benchmarked on a Jetson Orin Nano. Outside this phase are the Decision module that joins the two subsystems, arm and vacuum actuation, running navigation on the physical robot, and the semi-automatic and automatic modes; those are our future work. The work is shared between the CSE team, on software and intelligence, and the ECE team, on hardware and communication.",
          source='Source: paper Sections I, III and VIII; Major Project Phase 2 collaboration slide; firmware and HMI code')
T(s, LM, TOP, CWD, 0.5, 'SBY as a whole navigates, detects trash, picks it up and vacuums. This project builds its foundation: the robot platform with manual mode, and the two intelligent subsystems, navigation and trash detection.', size=11, color=K2)
columns(s, TOP + 0.62, 2.55, [
    [('h', 'Platform: hardware prototype and manual mode'), ('s', 'Built and running on the robot'),
     ('b', 'Three-rack chassis, BLDC hub-motor drive, 24 V power'), ('b', 'Jetson Orin Nano for compute, Arduino Uno for actuators'),
     ('b', 'Touchscreen HMI with manual control, 9 speed levels, emergency stop'), ('b', 'Acknowledged serial command protocol')],
    [('h', 'Subsystem 1: Navigation'), ('s', 'Built and evaluated in Gazebo'),
     ('b', 'RTAB-Map visual SLAM: 2D map and robot pose'), ('b', 'Our frontier explorer for autonomous exploration'),
     ('b', 'Nav2: Smac Hybrid-A* planning and MPPI control with obstacle avoidance'), ('b', 'Ground-truth evaluation in held-out worlds')],
    [('h', 'Subsystem 2: Trash detection'), ('s', 'Built and benchmarked on a Jetson'),
     ('b', 'Custom dataset: 877 robot-view images, 6,349 annotations'), ('b', 'YOLOv8n, YOLOv11n-seg and RF-DETR trained and compared'),
     ('b', 'Classes mapped to cleaning actions'), ('b', 'Speed and power measured on a Jetson Orin Nano')]], size=10.5)
panel(s, LM, TOP + 3.22, CWD, 0.74)
T(s, LM + 0.15, TOP + 3.24, CWD - 0.3, 0.7, [
    {'runs': [('Beyond this phase (future work): ', {'font': FS, 'color': ACC}), ('Decision module joining both subsystems; arm and vacuum actuation; navigation on the robot; autonomous modes.', {})], 'after': 2},
    {'runs': [('Team: ', {'font': FS, 'color': ACC}), ('CSE: software and intelligence (navigation, trash detection). ECE: hardware and communication.', {})]}],
  size=10, color=K2, anchor='m')

# ======================= 6. Hardware prototype and manual mode =======================
s = slide('Hardware Prototype and Manual Mode',
          "Here is the physical robot and how manual mode works on it. The prototype is a three-rack metal chassis, about 0.61 by 0.46 metres and 0.91 metres tall, weighing 50 kilograms with a 20-kilogram payload. Two six-inch BLDC hub motors at the rear are driven by YL 12, 24-volt sine-wave controllers, with a free caster at the front; a 24-volt, 26 amp-hour battery gives about two hours. The Jetson Orin Nano is the brain, and the Arduino Uno executes simple low-level commands, which keeps heavy computation isolated from actuator signals. The arm is six-degree-of-freedom, 3D-printed in PLA+, for up to 500 grams. Manual mode runs on this hardware today. The operator uses a fullscreen touchscreen app written in C++ with GTK4: forward, left, right, stop, nine speed levels, an emergency stop with reset, and toggles for vacuum, arm, wiper and UV. Each touch becomes a newline-terminated text command, such as SPEED:8 or MOVE:FORWARD, sent over a 115200-baud serial link to the Arduino. The Arduino replies with an acknowledgement or an error, reports status every second, maps speed to a PWM duty from 80 to 255 and sets direction through relays. Emergency stop has priority: all motion is rejected until a reset. The vacuum, arm, wiper and UV toggles are tracked as state today; wiring them to actuators is next.",
          source='Source: paper Table 1, Sections III-B to III-D; Arduino firmware (swacch_robot.ino) and HMI source; photos from Major Project Phase 2')
cw = (CWD - 0.5) / 3
picture(s, PIMG + '/img-016.png', LM, TOP, cw, 1.7, crop='fill')
picture(s, P2M + '/image14.jpg', LM + cw + 0.25, TOP, cw, 1.7, crop='fill')
picture(s, P2M + '/image11.jpg', LM + 2 * (cw + 0.25), TOP, cw, 1.7, crop='fill')
for i, c_ in enumerate(['SBY prototype (paper Fig. 2a)', 'HMI touchscreen on the robot', 'Prototype under manual control']):
    cap(s, LM + i * (cw + 0.25), TOP + 1.72, cw, c_)
columns(s, TOP + 2.0, 2.05, [
    [('h', 'Hardware prototype'),
     ('b', u('3-rack chassis, 0.61 × 0.46 × 0.91 m, 50 kg; 20 kg payload')),
     ('b', u('2 × 6-inch BLDC hub motors, 24 V controllers; 24 V 26 Ah battery, about 2 h')),
     ('b', 'Jetson Orin Nano (brain) + Arduino Uno (actuators); C270 RGB and D435i depth cameras'),
     ('b', u('6-DOF PLA+ arm, MG996R and MG90S servos, up to 0.5 kg'))],
    [('h', 'HMI and manual control'),
     ('b', 'Fullscreen C++/GTK4 touchscreen app on the robot'),
     ('b', 'Forward, left, right, stop; 9 speed levels (PWM 80 to 255); emergency stop and reset'),
     ('b', 'Vacuum, arm, wiper, UV toggles (state tracked today)'),
     ('b', 'touch → Jetson → serial 115200 baud → Arduino → PWM + relays → motors')],
    [('h', 'Command protocol and safety'),
     ('m', 'MOVE:FORWARD|BACKWARD|LEFT|RIGHT|STOP'), ('m', 'SPEED:1 … SPEED:9   ESTOP   RESET'),
     ('b', 'Every command answered with ACK or ERR; STATUS every 1 s'),
     ('b', 'ESTOP stops the motors and rejects motion until RESET; motion blocked while auto is on'),
     ('b', 'Plain text: easy to debug, light on the Arduino')]], size=9.5)

# ======================= 7. Navigation subsystem =======================
s = slide('Navigation Subsystem',
          "Now the first subsystem: navigation, on ROS 2 Jazzy with Nav2, developed and evaluated in Gazebo. The robot gets no floor plan, so it builds its own map and decides where to go in a closed loop. RTAB-Map fuses the depth camera's colour and depth images with wheel odometry. Because the floor is flat, registration is limited to three degrees of freedom. It outputs a 2D occupancy grid with 5-centimetre cells: points up to 3 centimetres high count as floor, and 3 to 30 centimetres as obstacles. Loop closures use a bag-of-words appearance model. We chose RTAB-Map because it is open source, works with any odometry source and manages memory well on the 8-gigabyte Jetson; in a published comparison on TUM RGB-D it was more accurate indoors than ORB-SLAM3 and OpenVSLAM. Our frontier explorer, next slide, picks the goal. Nav2's Smac Hybrid-A-star planner draws a forward-only Dubins path with a 0.25-metre turning radius, and the MPPI controller follows it: 2,000 sampled trajectories over a 2.8-second horizon, 20 times a second, up to 0.30 metres per second. The costmaps combine the SLAM grid, a voxel layer from the depth camera and a 0.28-metre inflation.",
          source='Source: paper Section VI, Tables 4 and 5; nav2_params.yaml, rtabmap.yaml; RTAB-Map comparison: Merzlyakov and Macenski, IROS 2021')
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
T(s, 3.0, TOP + 0.98, 4.0, 0.2, [{'t': 'the map keeps growing, so the loop repeats until no frontier is left', 'align': 'c'}], size=8.5, color=G)
picture(s, FIG + '/fig_costmap_layers.png', LM - 0.05, TOP + 1.3, 4.4, 1.47)
cap(s, LM, TOP + 2.78, 4.3, 'Live costmaps: SLAM grid, global costmap, 4 × 4 m local window')
blk(s, LM, TOP + 3.05, 4.3, 0.95, [
    ('h', 'Why RTAB-Map'),
    ('b', 'Open source; RGB-D input independent of the odometry source; memory management suits the 8 GB Jetson; most accurate indoors against ORB-SLAM3 and OpenVSLAM')], size=9.5)
vline(s, 4.88, TOP + 1.35, TOP + 3.95, color=HAIR)
blk(s, 5.0, TOP + 1.3, 4.5, 2.75, [
    ('h', 'Mapping and localisation (RTAB-Map)'),
    ('b', 'Colour + depth from the D435i fused with wheel odometry; 3-DoF registration on the flat floor'),
    ('b', '2D grid, 5 cm cells: up to 0.03 m is floor, 0.03 to 0.30 m is obstacle; map updated at 1 Hz'),
    ('b', 'Bag-of-words appearance model for loop closure'),
    ('h', 'Planning and control (Nav2)'),
    ('b', 'Smac Hybrid-A*: Dubins, forward-only, 0.25 m turning radius, 0.30 m goal tolerance, 5 s planning cap'),
    ('b', 'Costmaps: SLAM grid + depth voxel layer + 0.28 m inflation; 4 × 4 m local window at 5 Hz'),
    ('b', 'MPPI: 2,000 samples over a 2.8 s horizon at 20 Hz; up to 0.30 m/s and 1.0 rad/s')], size=9.5)

# ======================= 8. Frontier exploration =======================
s = slide('Navigation: Frontier Exploration',
          "This is the part we designed ourselves: the frontier explorer, which decides where the robot explores next. The robot has no floor plan, so it must keep choosing an unexplored area to visit. A frontier is a free cell next to unknown space, in other words the edge of the mapped area. Twice a second, the explorer finds every frontier, groups them into clusters and scores each one with this utility. n is the frontier's size in cells, a proxy for how much new map a visit would reveal; the logarithm means size helps, with diminishing returns. d is the straight-line distance in metres, so far frontiers cost more. p is a penalty for frontiers within half a metre of an obstacle, so the robot does not drive itself into corners. The weights 1.0, 1.5 and 0.8 balance the three. The highest-scoring frontier becomes the next goal for the planner. The table on the right is the full loop from the paper's Algorithm 1, including the guard rails: a goal is cancelled if Nav2 fails, after 30 seconds, or if the robot moves less than 30 centimetres in 15 seconds, and that frontier is blacklisted for a minute.",
          source='Source: paper Section VI-B, Algorithm 1 and Table 5; code verified (exploration_manager.py)')
blk(s, LM, TOP, 4.3, 1.05, [
    ('h', 'Why it is needed'),
    ('p', 'The robot has no floor plan, so it must keep choosing which unexplored area to visit next. A frontier is a free cell next to unknown space: the edge of the mapped area. Each frontier is scored:')], size=10)
T(s, LM, TOP + 1.12, 4.3, 0.42, [{'t': 'S = 1.0 ln(1 + n) − 1.5 d − 0.8 p', 'align': 'c'}], size=18, font=MATH, color=ACC)
leg = [['Term', 'Meaning', 'Effect'], ['n', 'frontier size in cells: how much new map a visit would reveal', 'raises S'],
       ['d', 'straight-line distance from the robot to the frontier (m)', 'lowers S'],
       ['p', u('max(0, 1 − d_obs / 0.5): obstacle within 0.5 m'), 'lowers S']]
btable(s, LM, TOP + 1.62, 4.3, leg, [0.5, 2.95, 0.85], row_h=[0.27, 0.42, 0.42, 0.42], size=9, align=['c', 'l', 'c'], hcolor=ACC,
       cell_fonts={(r, 0): MATH for r in range(1, 4)}, cell_colors={(r, 0): ACC for r in range(1, 4)})
blk(s, LM, TOP + 3.25, 4.3, 0.8, [
    ('b', 'Highest S becomes the next goal; weights 1.0, 1.5, 0.8 trade new map against travel and safety'),
    ('b', 'Centroids lie in unknown space, so each goal is snapped to a known free cell')], size=9.5)
vline(s, 4.98, TOP + 0.05, TOP + 3.95, color=HAIR)
T(s, 5.15, TOP, 4.35, 0.3, 'Exploration loop (paper Algorithm 1)', size=11.5, font=FS, color=ACC)
loop = [['Step', 'What happens'],
        ['Bootstrap', u('no map 3 s after start: rotate at 0.4 rad/s for 8 s')],
        ['Detect', u('find frontier cells on the latest grid at 2 Hz')],
        ['Cluster', u('flood fill in a 0.5 m window; drop clusters under 5 cells or 0.5 m')],
        ['Score', 'rank remaining frontiers by S; skip blacklisted ones'],
        ['Snap', u('goal = nearest free cell with 0.30 m clearance, within 1.5 m')],
        ['Monitor', u('cancel if Nav2 fails, after 30 s, or < 0.30 m moved in 15 s')],
        ['Blacklist', u('failed frontier skipped for 60 s; also if reached but < 10 new cells')],
        ['Stop', u('5 empty cycles, < 10 new free cells in 15 s, robot stationary')]]
btable(s, 5.15, TOP + 0.33, 4.35, loop, [0.95, 3.4], row_h=0.4, size=9, align=['l', 'l'], hcolor=ACC,
       cell_fonts={(r, 0): FS for r in range(1, 9)})

# ======================= 9. Custom built dataset =======================
s = slide('Trash Detection: Custom Built Dataset',
          "The second subsystem is trash detection, and it starts with data. Existing datasets such as TrashNet and ImageNet did not fit: their classes did not match ours, their images are taken at human eye level, and they were shot with high-quality cameras rather than a robot's RGB camera. So we built our own from scratch. We mounted a 1280 by 720 RGB camera low on the robot, tilted 30 degrees down: the low, tilted mount widens the visible floor and keeps what the robot sees within reach of the arm. Trash was captured against varied backgrounds, orientations, speeds and lighting, over about 10 person-hours by two people: 877 images of six waste classes. Every object was annotated in Roboflow as an instance-segmentation polygon that follows its real outline, by hand, by two annotators, with no auto-labelling, and every label was verified. That gives 6,349 annotations over eight labels, the six waste classes plus floor and obstacle. Obstacle annotations outnumber wooden dust about 21.7 to one, which mirrors what the robot sees; under-represented classes were augmented. The data was split 70, 20, 10 into 611, 175 and 91 images, and augmentation was applied only after the split, to training images only. Classes are defined by the cleaning action they need, so detections drive the decision table directly. The dataset is public on GitHub.",
          source='Source: paper Section IV-A to IV-D, Table 2 and Fig. 3; dataset at github.com/manaswi-siripurapu/swachh-bauddhika-yantra')
samples = [('img-021.png', 'Bottle'), ('img-022.png', 'Paper'), ('img-023.png', 'Plastic wrapper'),
           ('img-024.png', 'Aluminium foil'), ('img-025.png', 'Cement dust'), ('img-026.png', 'Wooden dust')]
pw, ph, gx = 1.52, 0.92, 0.06
for i, (f, nm) in enumerate(samples):
    col, row = i % 3, i // 3
    x = LM + col * (pw + gx); y = TOP + row * (ph + 0.24)
    picture(s, PIMG + '/' + f, x, y, pw, ph, crop='fill')
    T(s, x, y + ph + 0.02, pw, 0.2, nm, size=8.5, color=K2)
ann = [['Label', 'Images', 'Annotations'], ['Obstacle', 'n/a', '3,517'], ['Floor', 'n/a', '917'], ['Paper', '210', '691'], ['Bottle', '210', '351'],
       ['Wrapper', '151', '283'], ['Aluminium foil', '175', '259'], ['Cement dust', '68', '169'], ['Wooden dust', '63', '162'], ['Total', '877', '6,349']]
btable(s, 5.45, TOP, 4.05, ann, [1.65, 1.05, 1.35], row_h=0.232, size=8.5, hcolor=ACC,
       cell_fonts={(9, 0): FS, (9, 1): FS, (9, 2): FS}, cell_colors={(7, 2): RED, (8, 2): RED})
columns(s, TOP + 2.5, 1.55, [
    [('h', 'Why and how it was captured'),
     ('b', 'Public sets: wrong classes, eye-level shots, high-end cameras'),
     ('b', u('1280 × 720 camera mounted low, tilted 30° down, within the arm\'s reach')),
     ('b', 'Varied backgrounds, lighting and motion; 10 person-hours')],
    [('h', 'Annotation'),
     ('b', 'Instance polygons in Roboflow, drawn by hand by two annotators'),
     ('b', 'No auto-labelling; every label verified; YOLO and COCO export'),
     ('b', 'Obstacle vs wooden dust imbalance about 21.7 to 1')],
    [('h', 'Split and augmentation'),
     ('b', 'Split 70 : 20 : 10 into 611 / 175 / 91 images'),
     ('b', 'Augmentation after the split, training images only'),
     ('b', 'Flips, ±15° rotation, crop, perspective, ±30 % brightness and contrast, motion blur')]], size=9)

# ======================= 10. Trash detection models =======================
s = slide('Trash Detection: Models',
          "On our dataset we trained and compared two families of detectors. YOLO frames detection as a single regression from pixels to boxes and classes in one forward pass. YOLOv8 has a CSP-Darknet backbone with C2f blocks, a PAN plus FPN neck that fuses three scales, and a decoupled, anchor-free head that predicts box edges with Distribution Focal Loss. We used YOLOv8n and YOLOv11n-seg, which also predicts instance masks; both are about three million parameters and six megabytes. RF-DETR Medium is a real-time detection transformer from Roboflow: a pretrained DINOv2 vision-transformer backbone with a deformable multi-scale decoder. It treats detection as set prediction with Hungarian matching, so it needs no anchors and no non-maximum suppression, and its global attention helps tell look-alike debris such as wooden and cement dust apart. It is about 22 times larger. For tuning, a full grid over learning rate, batch size, input resolution, gradient accumulation and weight decay would be 450 trials, over six GPU-days, so we used random search: five trials of 20 epochs each, on an RTX A6000 with mixed precision.",
          source='Source: paper Section IV-E, IV-F, Figs. 4 and 5, Table 7, Section VII-A')
picture(s, PIMG + '/img-029.png', LM, TOP, 4.4, 1.6)
picture(s, PIMG + '/img-032.png', 5.1, TOP, 4.4, 1.6)
vline(s, 4.95, TOP + 0.05, TOP + 2.6, color=HAIR)
blk(s, LM, TOP + 1.65, 4.3, 1.0, [
    ('h', 'YOLO (YOLOv8n, YOLOv11n-seg)'),
    ('b', 'Single pass; CSP-Darknet + C2f backbone, PAN + FPN neck over 3 scales'),
    ('b', 'Anchor-free decoupled head; box edges via Distribution Focal Loss')], size=9.5)
blk(s, 5.1, TOP + 1.65, 4.4, 1.0, [
    ('h', 'RF-DETR Medium (transformer)'),
    ('b', 'Pretrained DINOv2 backbone with a deformable multi-scale decoder'),
    ('b', 'Set prediction with Hungarian matching: no anchors, no NMS')], size=9.5)
mt = [['Model', 'Type', 'Parameters', 'File size', 'Training'], ['YOLOv8n', 'CNN, boxes', u('3.01 M'), u('6.23 MB'), u('0.36 h')],
      ['YOLOv11n-seg', 'CNN, boxes + instance masks', u('2.84 M'), u('5.98 MB'), u('0.95 h')], ['RF-DETR Medium', 'transformer, DINOv2 backbone', u('33.3 M'), u('133.02 MB'), u('3.61 h')]]
btable(s, LM, TOP + 2.72, 5.6, mt, [1.3, 1.95, 0.8, 0.8, 0.75], row_h=0.28, size=9.5, align=['l', 'l', 'c', 'c', 'c'], hcolor=ACC)
blk(s, 6.35, TOP + 2.75, 3.15, 1.3, [
    ('h', 'Training'),
    ('b', 'Random search: 5 trials × 20 epochs over learning rate, batch, resolution, gradient accumulation, weight decay'),
    ('b', 'A full grid would be 450 trials (> 6 GPU-days); RTX A6000, mixed precision')], size=9.5)

# ======================= 11. Results: exploration and mapping =======================
s = slide('Results: Exploration and Mapping',
          "Now the results, starting with navigation. All navigation tests ran in Gazebo worlds held out from development, with noise injected into the wheel odometry, and everything was checked against the simulator's ground truth rather than the robot's own report; code and test split were frozen, and the tables were regenerated from raw data with zero mismatches. On the left is Figure 7: the path the robot drove in each of nine exploration runs, three worlds by three seeds. In the office and the multi-room loop the paths sweep every room, and coverage of the reachable floor averaged 83.8 and 86.3 percent. The maze is our open failure case: in two of three runs the explorer never issued a goal, so the maze averaged 14.3 percent and the pooled figure is 61.4. Next to it is Figure 6: the true floor plan and the maps the robot built. Warped shapes are SLAM drift. Trajectory error was 0.57 metres on average, and the main cause was contact: in four of nine runs, wheel slip during contact corrupted the heading. Before the first such event the error was 0.33 metres, and 98.4 percent of obstacle encounters were passed without contact. Half the reachable area was explored in 67.7 seconds on average.",
          source='Source: paper Figs. 6 and 7, Tables 13 and 15, Section VII-B; tested in held-out Gazebo worlds, 3 worlds × 3 seeds, wheel-odometry noise injected')
picture(s, PIMG + '/img-041.png', LM, TOP, 2.85, 2.32)
picture(s, PIMG + '/img-039.png', LM + 2.95, TOP + 0.02, 3.05, 2.3)
cap(s, LM, TOP + 2.33, 2.85, 'Paths of the nine runs (paper Fig. 7)')
cap(s, LM + 2.95, TOP + 2.33, 3.05, 'True plan vs explored maps (paper Fig. 6)')
vline(s, 6.62, TOP + 0.05, TOP + 2.5, color=HAIR)
blk(s, 6.75, TOP, 2.75, 2.6, [
    ('h', 'How it was tested'),
    ('b', 'Held-out Gazebo worlds; 3 worlds × 3 seeds; wheel-odometry noise injected'),
    ('b', 'Checked against simulator ground truth'),
    ('h', 'What drives the error'),
    ('b', 'Contact slip corrupted the heading in 4 of 9 runs'),
    ('b', u('ATE 0.33 m before the first slip; 98.4 % of encounters without contact')),
    ('b', u('Half the reachable area in 67.7 s'))], size=9)
hline(s, LM, TOP + 2.65, RM, color=HAIR)
worlds = [('Multi-room loop', '86.3 %', u('completeness 65.4 %, ATE 0.74 m'), ACC), ('Office', '83.8 %', u('completeness 65.9 %, ATE 0.35 m'), ACC),
          ('Maze (dead ends)', '14.3 %', 'no goal issued in 2 of 3 runs; ATE 0.76 m', RED), ('Pooled, 9 runs', '61.4 %', u('completeness 47.7 %, ATE 0.57 m'), TEAL)]
wc = (CWD - 0.75) / 4
for i, (w_, v_, d_, col) in enumerate(worlds):
    x = LM + i * (wc + 0.25)
    if i: vline(s, x - 0.125, TOP + 2.78, TOP + 3.95, color=HAIR)
    T(s, x, TOP + 2.73, wc, 1.25, [{'t': w_, 'font': FS, 'size': 10.5, 'color': K, 'after': 0},
                                   {'t': u(v_), 'font': FS, 'size': 22, 'color': col, 'after': 0},
                                   {'t': 'reachable floor explored', 'size': 8.5, 'color': G, 'after': 1},
                                   {'t': d_, 'size': 9, 'color': K2}])

# ======================= 12. Results: goals and avoidance =======================
s = slide('Results: Goal Navigation and Obstacle Avoidance',
          "Point-to-point navigation is where checking against ground truth matters most. In twelve episodes with 178 random goals, using AMCL on a ground-truth map, Nav2 reported half as reached, but only 29.2 percent were truly within 30 centimetres, and 9.0 percent within 15. Nav2 declared success while the robot was elsewhere, which points at the pose estimate: AMCL's mean position error was 0.318 metres. A diagnostic confirms it: with the same planner and controller, AMCL reached 6 of 19 goals and ground-truth localisation 19 of 20. That is one episode per setting, so it is indicative, but it tells us to invest in localisation, not planning. Reached goals took paths only 1.21 times the shortest. For safety, the robot escaped the static U-trap in all three trials but avoided a box that suddenly moves out at half a metre per second only once in three. Reaction time is good: 166 milliseconds to half speed and 260 to stop, inside the 0.5-second deadline.",
          source='Source: paper Table 14, Sections VII-B to VII-D; avoidance success = goal reached with no contact')
chart(s, LM - 0.05, TOP - 0.05, 4.9, 2.5, ['Two rooms + door', 'Office', 'Maze', 'Pooled (178)'],
      [('Reported by Nav2', (82.5, 37.9, 2.5, 50.0)), (u('Verified within 0.30 m'), (48.8, 20.7, 2.5, 29.2))],
      [G3, ACC], fmt='0.0', suffix=NB + '%', maxv=95, legend=True, gap=60, overlap=-5, label_size=9)
cap(s, LM, TOP + 2.47, 4.8, 'Goals reached (%), Nav2\'s report vs ground truth')
av = [['Avoidance scenario', 'Trials', 'Succeeded'], ['Static U-trap', '3', '3 of 3'], [u('Box moving out at 0.5 m/s'), '3', '1 of 3'], ['Total', '6', '4 of 6']]
btable(s, LM, TOP + 2.78, 4.8, av, [2.6, 0.9, 1.3], row_h=0.28, size=9.5, cell_colors={(1, 2): TEAL, (2, 2): RED},
       cell_fonts={(3, 0): FS, (3, 2): FS}, hcolor=ACC)
vline(s, 5.45, TOP + 0.05, TOP + 3.95, color=HAIR)
blk(s, 5.6, TOP, 3.9, 4.0, [
    ('h', 'How it was tested'),
    ('b', '12 episodes, 178 random goals in 3 held-out worlds; AMCL on a ground-truth map'),
    ('b', u('Success = truly within 0.30 m per the simulator, not Nav2\'s report')),
    ('h', 'Goal navigation'),
    ('b', u('Nav2 reported 50.0 %; ground truth 29.2 % within 0.30 m, 9.0 % within 0.15 m')),
    ('b', u('AMCL error 0.318 m: success declared while the robot was elsewhere')),
    ('b', 'Diagnostic:', '19 of 20 goals with a perfect pose vs 6 of 19 with AMCL'),
    ('b', 'Reached goals: paths 1.21 × the shortest'),
    ('h', 'Safety and reaction'),
    ('b', u('93.2 % of encounters without contact; min clearance 0.159 m')),
    ('b', u('166 ms to half speed, 260 ms to stop (deadline 0.5 s)'))], size=9.5)

# ======================= 13. Results: trash detection =======================
s = slide('Results: Trash Detection',
          "Now trash detection. Accuracy was measured on our custom dataset: overall metrics on the 175 validation images, and per-class AP on the 91 test images. Speed, latency and power were measured on a Jetson Orin Nano at half precision, with 10 warm-up and 100 timed passes. All three models exceed 0.92 mAP at an IoU of 0.5, within 0.7 percent of each other. RF-DETR draws the tightest boxes, 0.839 mAP averaged over 0.5 to 0.95, or 0.843 with its EMA checkpoint. YOLOv11n-seg has the highest recall, which matters for a robot that shouldn't miss trash, and YOLOv8n the highest precision. The per-class chart shows foil is easy for every model, while dust, with its diffuse texture, is hardest: RF-DETR scored only 64.6 percent AP on cement dust. On the Jetson, end-to-end throughput was 76.4, 79.3 and 41.4 frames per second, all above the 30-frames-per-second camera rate, at 12.7 to 14.9 watts. YOLOv11n-seg is the most efficient at 6.15 frames per second per watt and also gives masks, so it is our choice for the robot. RF-DETR is the most accurate but 22 times larger at about half the frame rate, so it suits a GPU base station.",
          source='Source: paper Tables 10, 11 and 12 (custom dataset: 175 validation and 91 test images; Jetson Orin Nano, FP16, 10 warm-up and 100 timed passes)')
dt = [['Metric', 'YOLOv8n', 'YOLOv11n-seg', 'RF-DETR'],
      ['mAP@0.5', '0.927', '0.930', '0.934'], ['mAP@0.75', '0.882', '0.890', '0.880'], ['mAP@0.5:0.95', '0.820', '0.821', '0.839'],
      ['Precision', '0.935', '0.913', '0.927'], ['Recall', '0.900', '0.920', '0.894'],
      ['End-to-end FPS (Jetson)', '76.4', '79.3', '41.4'], ['End-to-end latency (ms)', '13.35', '12.61', '24.23'],
      ['Board power (W)', '12.66', '12.90', '14.85'], ['FPS per watt', '6.05', '6.15', '2.79'], ['Peak RAM (MB)', '244', '341', '323']]
hl = {(1, 3): ACC, (2, 2): ACC, (3, 3): ACC, (4, 1): ACC, (5, 2): TEAL, (6, 2): TEAL, (7, 2): TEAL, (9, 2): TEAL}
btable(s, LM, TOP, 4.75, dt, [1.85, 0.9, 1.1, 0.9], row_h=0.235, size=8.5, hcolor=ACC, cell_colors=hl, cell_fonts={k: FS for k in hl})
cap(s, LM, TOP + 2.6, 4.75, 'Accuracy: custom dataset, 175 validation images. Speed: Jetson Orin Nano, FP16')
blk(s, LM, TOP + 2.88, 4.75, 1.15, [
    ('h', 'Choice for the robot: YOLOv11n-seg'),
    ('b', u('Fastest end-to-end (79.3 FPS), most efficient (6.15 FPS/W), highest recall, predicts masks')),
    ('b', 'RF-DETR: tightest boxes but ~22× larger at about half the frame rate; suits a GPU base station')], size=9, hcolor=TEAL)
vline(s, 5.38, TOP + 0.05, TOP + 3.95, color=HAIR)
chart(s, 5.45, TOP - 0.08, 4.1, 2.95, ['Foil', 'Bottle', 'Wrapper', 'Paper', 'Floor', 'Obstacle', 'Wood dust', 'Cement dust'],
      [('YOLOv11n-seg', (98.94, 93.09, 96.52, 93.65, 91.93, 89.07, 93.97, 82.68)), ('RF-DETR', (96.49, 86.34, 88.46, 83.56, 89.32, 77.29, 74.83, 64.56))],
      [TEAL, ACC], point_colors={1: {7: RED, 6: RED}}, fmt='0', maxv=105, minv=50, legend=True, gap=40, overlap=-5, label_size=7, axis_size=8, bar=True)
cap(s, 5.55, TOP + 2.85, 3.95, 'Per-class AP (%), 91 test images; axis starts at 50')
blk(s, 5.55, TOP + 3.12, 3.95, 0.9, [
    ('b', 'All three exceed 0.92 mAP@0.5, within 0.7 % of each other'),
    ('b', 'Dust is hardest: cement dust 64.6 % AP for RF-DETR')], size=9)

# ======================= 14. Conclusion =======================
s = slide('Conclusion',
          "To conclude, across the three parts of our scope. The platform: the prototype runs manual mode from its touchscreen through an acknowledged serial protocol with an emergency stop. Subsystem one, navigation: RTAB-Map with our frontier explorer and Nav2 explores 84 to 86 percent of the reachable floor in room-like simulated worlds, 61.4 percent pooled, with a trajectory error of 0.57 metres; the planner works, and localisation is what limits goal accuracy. Subsystem two, trash detection: on our own 877-image dataset all three detectors exceed 0.92 mAP, and YOLOv11n-seg runs at 79 frames per second on a Jetson Orin Nano at about 13 watts. Our paper is submitted to IEEE Access and the dataset is public. Four lessons we carry forward: verify, don't trust; localisation is the bottleneck; contact breaks the map; and small models are enough on the edge. The limits are clear: navigation is tested only in simulation on a smaller base, and the detectors on the Jetson board, not yet on the robot.",
          source='Source: paper Sections VII and VIII')
columns(s, TOP, 1.95, [
    [('h', 'Platform'), ('b', 'Prototype runs manual mode from the touchscreen HMI'), ('b', 'Acknowledged serial protocol, 9 speed levels, emergency stop'),
     ('b', 'Jetson for compute, Arduino for actuators'), ('b', u('50 kg three-rack chassis, BLDC hub motors, 24 V power'))],
    [('h', 'Subsystem 1: navigation'), ('b', u('84 to 86 % of the reachable floor in room-like Gazebo worlds; 61.4 % pooled')),
     ('b', u('Trajectory error 0.57 m; 0.33 m before contact')), ('b', 'Planner sound: 19 of 20 goals with a true pose'), ('b', 'Static U-trap passed 3 of 3; sudden box 1 of 3')],
    [('h', 'Subsystem 2: trash detection'), ('b', 'Custom 877-image dataset, 6,349 annotations'), ('b', 'All three detectors exceed 0.92 mAP@0.5'),
     ('b', u('YOLOv11n-seg: 79 FPS at 12.9 W on a Jetson Orin Nano')), ('b', 'YOLOv11n-seg chosen for the robot')]], size=10.5)
hline(s, LM, TOP + 2.02, RM, color=HAIR)
columns(s, TOP + 2.1, 1.95, [
    [('h', 'What we learned'),
     ('b', 'Verify, don\'t trust.', u('Nav2 reported 50 % of goals reached; ground truth confirmed 29.2 %.')),
     ('b', 'Localisation is the bottleneck.', 'Same planner: 6 of 19 goals with AMCL, 19 of 20 with a true pose.'),
     ('b', 'Contact breaks the map.', 'Wheel slip on contact corrupted the heading in 4 of 9 runs.'),
     ('b', 'Small models are enough.', 'Nano models lose only 0.7 to 1.1 points of mAP@0.5 for a twenty-fold smaller model.')],
    [('h', 'Limitations'),
     ('b', u('Navigation tested only in simulation, on a 0.30 × 0.25 m base')),
     ('b', 'Detectors benchmarked on the Jetson board, not yet on the robot'),
     ('b', 'Three or four seeds per world give wide intervals'),
     ('h', 'Output'),
     ('b', 'Paper submitted to IEEE Access; dataset public')]], size=9.5)

# ======================= 15. Future work + thank you =======================
s = slide('Future Work',
          "Future work, in order. First, deploy navigation on the physical robot and re-tune it: the simulated robot is 0.30 by 0.25 metres while the real one is 0.60 by 0.50, and the simulated camera has no noise and a 69.4-degree depth field of view against about 87 for the D435i, so inflation, turning radius, clearance and speed limits must be re-tuned. Second, fix the two known failure cases: maze runs where no goal was issued, and suddenly moving obstacles. Third, run the chosen detector, YOLOv11n-seg, on the robot's own Jetson. Fourth, integrate both subsystems through the Decision module, so a detection pre-empts navigation, triggers the arm or vacuum and then resumes exploration. And fifth, actuate the arm and vacuum and complete the semi-automatic and automatic modes. On detection, more dust data and segmentation masks are the natural next steps. Thank you; we're happy to take questions.",
          source='Source: paper Sections VI-A, VII-C, VII-D (simulation vs physical set-up) and VIII (future work)')
steps = [('Deploy navigation', 'on the robot; re-tune for the real base and camera'), ('Fix known failures', 'maze runs with no goal; suddenly moving obstacles'),
         ('Run the detector', 'YOLOv11n-seg on the robot\'s Jetson'), ('Integrate', 'Decision module pre-empts navigation, triggers arm or vacuum, resumes'),
         ('Actuate and automate', 'arm, vacuum, semi-automatic and automatic modes')]
y0 = TOP + 0.45; x0 = LM + 0.12; step = 1.8
hline(s, x0, y0, x0 + 4 * step, color='9FB3CC', w=1.0)
for i, (h_, d_) in enumerate(steps):
    x = x0 + i * step
    dot = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x - 0.08), Inches(y0 - 0.08), Inches(0.16), Inches(0.16))
    dot.shadow.inherit = False
    dot.fill.solid(); dot.fill.fore_color.rgb = rgb(TEAL if i == 0 else 'FFFFFF'); dot.line.color.rgb = rgb(TEAL if i == 0 else ACC); dot.line.width = Pt(1.25)
    T(s, x - 0.12, TOP + 0.08, 1.0, 0.25, f'0{i + 1}', size=12, font=FS, color=TEAL if i == 0 else ACC)
    T(s, x - 0.12, y0 + 0.16, 1.68, 0.95, [{'t': h_, 'font': FS, 'size': 11, 'color': TEAL if i == 0 else K}, {'t': u(d_), 'size': 9.5, 'color': K2}])
T(s, LM, TOP + 1.6, 4.6, 0.26, 'Simulation vs the physical robot', size=11, font=FS, color=ACC)
st = [['', 'Simulation (tested)', 'Physical robot'], ['Base footprint', u('0.30 × 0.25 m'), u('0.60 × 0.50 m')], ['Depth field of view', '69.4°', 'about 87° (D435i)'],
      ['Camera noise', 'none', 'real sensor noise'], ['Walls', 'textured', 'may be plain'], ['Planner tuning', 'for the small base', 'to be re-tuned']]
btable(s, LM, TOP + 1.9, 4.6, st, [1.5, 1.5, 1.6], row_h=0.3, size=9.5, hcolor=ACC)
vline(s, 5.28, TOP + 1.65, TOP + 3.95, color=HAIR)
blk(s, 5.45, TOP + 1.6, 4.05, 1.4, [
    ('h', 'Also planned'),
    ('b', 'Closer analysis of false loop closures in worlds with many revisits'),
    ('b', 'More dust and obstacle data, and segmentation masks'),
    ('b', 'Wire the HMI\'s vacuum, arm, wiper and UV toggles to actuators')], size=9.5)
T(s, 5.45, TOP + 3.05, 4.05, 0.95, [
    {'t': 'Thank you. Questions are welcome.', 'font': FS, 'size': 15, 'color': ACC, 'after': 3},
    {'t': 'Paper submitted to IEEE Access   ·   dataset: github.com/manaswi-siripurapu/swachh-bauddhika-yantra', 'size': 8.5, 'color': K2}])

prs.save(OUT)
print('saved', OUT, 'slides:', len(prs.slides))
