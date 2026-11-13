"""Standalone slide 'What Has Been Built?' in the deck's style: intro line + 3 parallel vertical boxes.
Output: presentation/What_Has_Been_Built_Slide.pptx (one slide, to paste into any deck). No en/em dashes.
"""
import re
import sys
sys.path.insert(0, '/home/hrishikesh/Swachh/presentation/build')
from lib2 import *
from pptx import Presentation

SRC = R + '/Major Project Phase 2 PPT.pptx'
OUT = R + '/presentation/What_Has_Been_Built_Slide.pptx'
TEAL = '17806D'; TINT = 'EAF1F8'; NB = ' '
LM = 0.5; RM = 9.5; CWD = RM - LM

prs = Presentation(SRC)
sld = prs.slides._sldIdLst
for s_ in list(sld):
    prs.part.drop_rel(s_.rId); sld.remove(s_)
BLANK = [l for l in prs.slide_layouts if l.name == 'BLANK'][0]


def u(t):
    return re.sub(r'(?<=\d) (?=(%|ms|m|W|FPS|s|MB|M|h|kg|Hz|GB|Ah|V|cm)(?![A-Za-z0-9]))', NB, t)


s = prs.slides.add_slide(BLANK)
for ph in list(s.placeholders):
    ph._element.getparent().remove(ph._element)
s.shapes.add_picture(LOGO, Inches(8.98), Inches(0.2), Inches(0.56), Inches(0.552)).name = 'BMS logo'
T(s, LM, 0.3, 8.3, 0.6, 'What Has Been Built?', size=26, color=K, font=FS, anchor='m', name='Title')
T(s, LM, 1.0, CWD, 0.55, u('Currently, the SBY hardware prototype runs in manual mode, and both intelligent subsystems, navigation and trash detection, are built and evaluated: navigation in the Gazebo simulator, trash detection on a Jetson Orin Nano.'),
  size=11.5, color=K2, name='Intro')

boxes = [
    ('Prototype and Manual Mode', 'Built and running on the robot', [
        'Three-rack chassis, two BLDC hub motors, 24 V 26 Ah battery',
        'Jetson Orin Nano for compute, Arduino Uno for the motors',
        'Touchscreen HMI: drive controls, 9 speed levels, emergency stop',
        'Serial commands, each acknowledged by the Arduino']),
    ('Navigation Subsystem', 'Built and tested in Gazebo', [
        'RTAB-Map: 2D map (5 cm cells) from depth camera and wheel odometry',
        'Custom frontier explorer chooses the next goal',
        'Smac Hybrid-A* path planning and MPPI control',
        'Up to 86.3 % of reachable floor explored (61.4 % average)']),
    ('Trash Detection Subsystem', 'Built and run on a Jetson', [
        'Custom dataset: 877 images, 8 classes, 6,349\u00a0annotations',
        'YOLOv8n, YOLOv11n\u2011seg and RF\u2011DETR trained and compared',
        'All three above 0.92 mAP@0.5',
        'Real time on Jetson Orin Nano, up to 79 FPS']),
]
gap = 0.25; bw = (CWD - 2 * gap) / 3; by = 1.7; bh = 3.2; hh = 0.5
for i, (head, status, items) in enumerate(boxes):
    bx = LM + i * (bw + gap)
    b = outline_box(s, bx, by, bw, bh, color=ACC, lw=1.0); b.name = f'Box {i + 1}'
    hd = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(bx), Inches(by), Inches(bw), Inches(hh))
    hd.fill.solid(); hd.fill.fore_color.rgb = rgb(ACC); hd.line.fill.background(); hd.shadow.inherit = False
    hd.name = f'Box {i + 1} heading'
    T(s, bx + 0.1, by, bw - 0.2, hh, [{'t': head, 'align': 'c'}], size=13.5, color='FFFFFF', font=FS, anchor='m')
    paras = [{'t': status, 'font': FS, 'color': TEAL, 'size': 12, 'after': 6, 'align': 'c'}]
    paras += [{'t': u(t_), 'bullet': True, 'bucolor': ACC, 'size': 12, 'after': 6, 'indent': 0.16} for t_ in items]
    T(s, bx + 0.12, by + hh + 0.1, bw - 0.24, bh - hh - 0.15, paras, size=12, color=K)

T(s, LM, 5.33, 4.0, 0.18, 'Swachh Bauddhika Yantra  |  Department of CSE, BMSCE', size=8, color=G, name='Footer')
s.notes_slide.notes_text_frame.text = (
    "Here is where the project stands today. First, the platform: the hardware prototype is built and runs in manual mode. "
    "It has a three-rack chassis with two BLDC hub motors on a 24 volt battery, a Jetson Orin Nano for compute and an Arduino Uno "
    "for the motors, driven from a touchscreen HMI with nine speed levels and an emergency stop. Second, the navigation subsystem: "
    "RTAB-Map builds the map, our own frontier explorer picks where to go next, and Smac Hybrid-A star with MPPI plans and follows "
    "the path. In Gazebo it explored up to 86.3 percent of the reachable floor. Third, trash detection: we built our own dataset "
    "of 877 images and trained three models, all above 0.92 mAP at 0.5, running in real time on the Jetson at up to 79 FPS.")
prs.save(OUT)
print('saved', OUT)
