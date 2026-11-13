"""v2 poster: builds presentation/Swachh_Poster.pptx from Sample-Poster.pptx (same master: gradient, header band, 3 panels).
Keeps the sample's BMS logo, title placeholder and author table; replaces all content.
Run: <venv>/bin/python build_poster.py
"""
import sys
sys.path.insert(0, '/home/hrishikesh/Swachh/presentation/build')
from lib_pptx import *
from pptx import Presentation
from pptx.oxml.ns import qn

SRC = R + '/Sample-Poster.pptx'
OUT = R + '/presentation/Swachh_Poster.pptx'
TNR = 'Times New Roman'; TXT = '2C3E70'; HD = '203864'

prs = Presentation(SRC)
s = prs.slides[0]
keep = {'Picture 4', 'object 27', 'object 74'}
for sh in list(s.shapes):
    if sh.name not in keep:
        sh._element.getparent().remove(sh._element)

# ---- title (placeholder keeps the sample's style: white, 24 pt) ----
title = [sh for sh in s.shapes if sh.name == 'object 27'][0]
title.left, title.top, title.width = Inches(2.3), Inches(0.05), Inches(19.4)
r = title.text_frame.paragraphs[0].runs[0]
r.text = 'Design and Development of Precision Motion Control with Obstacle Avoidance and Trash Detection for Swachh Bauddhika Yantra'
for extra in title.text_frame.paragraphs[0].runs[1:]:
    extra._r.getparent().remove(extra._r)
title.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
r.font.size = Pt(23); r.font.bold = True

# ---- author table (5 columns as in the sample) ----
tbl = [sh for sh in s.shapes if sh.name == 'object 74'][0]
tbl.left, tbl.top, tbl.width = Inches(2.3), Inches(0.5), Inches(19.4)
t = tbl.table
cols = [['Sanjana Srinivas (1BM23CS301)', 'Shashank U (1BM23CS314)', 'Siripurapu Manaswi (1BM23CS331)', 'Hrishikesh R Prasad (1BM23CS367)', 'Department of CSE'],
        ['Shreesha S (1BM24EC422)', 'Rajat C Athani (1BM24EC417)', 'Preetham N (1BM24EC414)', 'Raviteja M (1BM24EC418)', 'Department of ECE'],
        ['Guide: Dr. Umadevi V', 'Professor,', 'Department of Computer', 'Science and Engineering'],
        ['Co-guide: Dr. Veena N Hegde', 'Professor,', 'Department of Electronics and', 'Communication Engineering'],
        ['In collaboration with', 'Anand Iyer, Director Projects,', 'Innovative Consulting Inc', 'Vishwajeet Gokhale, CEO,', 'Tantradnya, Pune']]
widths = [4.1, 3.7, 3.7, 4.0, 3.9]
for ci, lines in enumerate(cols):
    t.columns[ci].width = Inches(widths[ci])
    cell = t.cell(0, ci); tf = cell.text_frame
    # reuse first paragraph's formatting, drop the rest
    ps = tf.paragraphs
    for p in ps[1:]:
        p._p.getparent().remove(p._p)
    p0 = tf.paragraphs[0]
    for rr in p0.runs[1:]:
        rr._r.getparent().remove(rr._r)
    for li, line in enumerate(lines):
        p = p0 if li == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        run = p.runs[0] if (li == 0 and p.runs) else p.add_run()
        run.text = line
        run.font.size = Pt(15); run.font.color.rgb = rgb(WHITE); run.font.name = BODY
        run.font.bold = (li == 0 and ci >= 2)
tbl.height = Inches(1.5)


from lib2 import btable, hline, vline, HAIR, RULE

# ---- helpers in the sample's style (v2: no coloured boxes) ----
PX = [0.47, 7.6, 14.73]; PW = 6.8; IN = 0.25; CW = PW - 2 * IN
BODY_PT = 13


def heading(x, y, txt, w=CW):
    tb = text(s, x, y, w, 0.42, [{'t': txt, 'align': 'c'}], size=21, color=HD, font=TNR, bold=True)
    tb.text_frame.paragraphs[0].runs[0].font.underline = True
    return y + 0.48


def sub(x, y, txt, w=CW):
    text(s, x, y, w, 0.3, txt, size=15, color=HD, font=TNR, bold=True)
    return y + 0.34


def para(x, y, h, items, w=CW, size=BODY_PT, after=3):
    out = []
    for it in items:
        if isinstance(it, str): it = {'t': it}
        d = dict(it); d.setdefault('size', size); d.setdefault('after', after); d.setdefault('color', TXT); d.setdefault('font', TNR)
        if d.get('bullet'): d.setdefault('bucolor', HD)
        out.append(d)
    text(s, x, y, w, h, out, size=size, color=TXT, font=TNR)
    return y + h


def bl(t_, **k):
    d = {'t': t_, 'bullet': True}; d.update(k); return d


def caption(x, y, txt, w=CW, h=0.26):
    text(s, x, y, w, h, [{'t': txt, 'align': 'c'}], size=11, color=TXT, font=TNR)
    return y + h


def ptable(x, y, w, rows, col_w, row_h=0.3, size=11.5, cell_bold=None, **k):
    cb = {(0, c): True for c in range(len(rows[0]))}
    cb.update(cell_bold or {})
    btable(s, x, y, w, rows, col_w, row_h=row_h, size=size, font=TNR, hfont=TNR, hcolor=HD, color=TXT, fill=None,
           grid='A7B3C9', rule=HD, cell_bold=cb, **k)
    return y + (sum(row_h) if isinstance(row_h, (list, tuple)) else row_h * len(rows))


def bold_hd(r_c_list):
    return {rc: True for rc in r_c_list}


BOXF = 'E6EAF2'


def tbox(bx, by, bw, bh, paras, lw=1.0, fill=BOXF, align='c', anchor='m', margin=0.06):
    b = box(s, bx, by, bw, bh, fill=fill, line=HD, radius=0.08, line_w=lw)
    items = []
    for p_ in paras:
        d = dict(p_); d.setdefault('color', TXT); d.setdefault('align', align); items.append(d)
    shape_text(b, items, font=TNR, anchor=anchor, margin=margin)
    return b


def flow(fx, fy, labels, h, size=11, gap=0.24, w=CW, lw=1.0):
    bw_ = (w - gap * (len(labels) - 1)) / len(labels)
    for i, lab in enumerate(labels):
        bx = fx + i * (bw_ + gap)
        paras = [{'t': t_, 'size': size if j == 0 else size - 1.5, 'bold': j == 0, 'color': HD if j == 0 else TXT} for j, t_ in enumerate(lab)]
        tbox(bx, fy, bw_, h, paras, lw=lw)
        if i < len(labels) - 1:
            arrow(s, bx + bw_ + 0.03, fy + h / 2, bx + bw_ + gap - 0.03, fy + h / 2, color=HD, w=1.5)
    return fy + h


# =============== Column 1: Introduction (problem) -> Proposed System (SBY) -> Operating Modes ===============
x = PX[0] + IN; y = 2.5
y = heading(x, y, 'Introduction')
y = para(x, y, 1.72, [
    {'t': 'Manual cleaning of large indoor spaces is labour-heavy, slow and inconsistent, and in industrial settings workers may unknowingly handle hazardous waste. Existing cleaning robots vacuum or mop, but do not combine autonomous navigation, AI-based trash detection and arm-based collection.', 'align': 'l', 'after': 5},
    {'t': 'Gaps identified in the literature survey:', 'bold': True, 'after': 2},
    bl('Deep-learning trash detection in cleaning robots relies on external processing.'),
    bl('Onboard trash detection is not integrated with autonomous navigation.')])
y = heading(x, y + 0.08, 'Proposed System')
y = para(x, y, 0.82, [{'runs': [('Swachh Bauddhika Yantra (SBY) ', {'bold': True}), ('is an autonomous indoor cleaning robot: it navigates, detects and classifies trash, picks it up with a 6-DOF arm and vacuums dust, with all computation on board. Detection runs on the robot and a Decision module joins it with navigation, closing both gaps. SDG 11.', {})], 'align': 'l'}])
picture(s, B + '/arch_transparent.png', x, y, CW, 2.15)
y = caption(x, y + 2.15, 'Fig. 1. Four-layer architecture of SBY')
y = para(x, y + 0.02, 1.15, [
    bl('', runs=[('Interface: ', {'bold': True}), ('HMI touchscreen', {})]),
    bl('', runs=[('Sensor: ', {'bold': True}), ('RGB camera, RealSense D435i depth camera, wheel encoders', {})]),
    bl('', runs=[('Processing (Jetson Orin Nano): ', {'bold': True}), ('detection, visual SLAM, Decision module', {})]),
    bl('', runs=[('Actuator: ', {'bold': True}), ('Arduino Uno drives the motors, arm and vacuum', {})])], size=12.5, after=2)
y = heading(x, y + 0.08, 'Operating Modes')
def mcell(name, status):
    return [[(name, {'bold': True})], [(status, {'size': 10.5, 'italic': True})]]
rows = [['Mode', 'What it does'],
        [mcell('Manual', 'working on the robot'), 'The operator controls direction, speed (9 levels) and emergency stop from the HMI touchscreen, which shows robot status. For precise control in sensitive or high-traffic areas.'],
        [mcell('Semi-automatic', 'planned'), 'The operator selects the area, type of cleaning and duration; the robot then cleans that area on its own while the operator monitors alerts. For routine cleaning.'],
        [mcell('Automatic', 'planned'), 'No operator input: the robot maps the space, finds what needs cleaning, and its detector decides the action (pick up, vacuum or re-plan). For large, complex areas.']]
y = ptable(x, y + 0.02, CW, rows, [1.55, 4.75], row_h=[0.32, 0.74, 0.74, 0.74], size=12, align=['l', 'l'])
y = para(x, y + 0.08, 0.5, [{'runs': [('One execution path: ', {'bold': True}), ('manual and autonomous commands share a single path to the actuators, and the emergency stop halts the robot in every mode.', {})], 'align': 'l'}], size=12)

# =============== Column 2: What we built (manual mode, navigation, trash detection) ===============
x = PX[1] + IN; y = 2.5
y = heading(x, y, 'Methodology')
y = sub(x, y, 'A. Hardware prototype, HMI and manual mode')
picture(s, PIMG + '/img-016.png', x, y + 0.02, 1.5, 1.5, crop='fill')
picture(s, P2M + '/image14.jpg', x + 1.58, y + 0.02, 2.0, 1.5, crop='fill')
para(x + 3.7, y, 1.8, [
    bl('3-rack chassis, 50 kg, 0.61 × 0.46 × 0.91 m', size=11.5),
    bl('2 BLDC hub motors, 24 V 26 Ah battery (~2 h)', size=11.5),
    bl('Jetson Orin Nano + Arduino Uno', size=11.5),
    bl('6-DOF 3D-printed arm, ≤ 0.5 kg', size=11.5)], w=2.6, after=2)
y = caption(x, y + 1.55, 'Fig. 2. Prototype and its HMI touchscreen', w=3.58)
y = para(x, y + 0.02, 0.3, [{'t': 'Manual mode, implemented on the hardware:', 'bold': True, 'color': HD}], size=12.5)
y = flow(x, y + 0.02, [['HMI', 'touchscreen'], ['Jetson', 'Orin Nano'], ['Arduino', 'Uno'], ['PWM +', 'relays'], ['Hub', 'motors']], 0.55, size=11.5)
y = para(x, y + 0.06, 0.95, [
    bl('Plain-text commands over serial (115200 baud), e.g. MOVE:FORWARD, SPEED:8'),
    bl('9 speed levels (PWM 80 to 255); every command acknowledged; status every 1 s'),
    bl('Emergency stop halts the motors and blocks motion until reset')], size=12, after=1)
y = sub(x, y + 0.04, 'B. Navigation subsystem (ROS 2 Jazzy, Nav2, Gazebo)')
y = flow(x, y + 0.02, [['RTAB-Map SLAM', 'RGB-D + odometry', '2D map, 5 cm cells'], ['Frontier explorer', 'our code, 2 Hz', 'chooses goal by S'],
                       ['Smac Hybrid-A*', 'forward-only path', '0.25 m radius'], ['MPPI controller', 'follows the path', '20 Hz, ≤ 0.30 m/s']], 0.86, size=10.5, gap=0.18)
y = para(x, y + 0.08, 0.3, [{'t': 'How the robot decides where to explore next', 'bold': True, 'color': HD}], size=12.5)
y = para(x, y, 0.62, [{'t': 'The robot has no floor plan, so it must keep choosing which unexplored area to visit. Twice a second our frontier explorer (2nd box above) finds every frontier, the boundary between mapped free space and unexplored space, and gives it a score:', 'align': 'l'}], size=12)
y = para(x, y, 0.4, [{'t': 'S = 1.0 ln(1 + n) − 1.5 d − 0.8 p', 'align': 'c', 'size': 16, 'bold': True, 'color': HD}])
lw3 = CW / 3
for i, (v, d_) in enumerate([('n', 'frontier size in cells: bigger reveals more map'), ('d', 'distance to it in metres: farther costs more'), ('p', 'penalty if within 0.5 m of an obstacle')]):
    text(s, x + i * lw3, y, lw3, 0.5, [{'runs': [(v + ' ', {'bold': True, 'italic': True, 'size': 13, 'color': HD}), (d_, {})], 'align': 'c'}], size=11, color=TXT, font=TNR)
y += 0.52
y = para(x, y, 0.62, [{'t': 'The highest-scoring frontier becomes the next goal for the Smac Hybrid-A* planner, kept 0.30 m from obstacles. A goal that fails, exceeds 30 s or stalls is dropped and skipped for 60 s.', 'align': 'l'}], size=12)
y = sub(x, y + 0.04, 'C. Trash detection on our custom dataset')
y = para(x, y, 0.62, [{'runs': [('Our own dataset, built from scratch: 877 images, 6,349 hand-drawn annotations, 8 classes', {'bold': True, 'color': HD}),
                                ('; split 611 / 175 / 91. Shot from the robot\'s low camera, tilted 30° down so trash is within the arm\'s reach.', {})], 'align': 'l'}], size=12.5)
y += 0.04
samples = ['img-021.png', 'img-022.png', 'img-023.png', 'img-024.png', 'img-025.png', 'img-026.png']
labels = ['Bottle', 'Paper', 'Wrapper', 'Foil', 'Cement dust', 'Wooden dust']
iw = (CW - 5 * 0.06) / 6
for i, f in enumerate(samples):
    picture(s, PIMG + '/' + f, x + i * (iw + 0.06), y + 0.02, iw, 0.62, crop='fill')
    text(s, x + i * (iw + 0.06), y + 0.65, iw, 0.22, [{'t': labels[i], 'align': 'c'}], size=9.5, color=TXT, font=TNR)
y += 0.9
y = para(x, y, 0.95, [
    bl('Classes follow the cleaning action they need: bottle, wrapper, paper, foil → activate arm; obstacle → re-plan path.'),
    bl('Models: YOLOv8n (3.01 M), YOLOv11n-seg (2.84 M), RF-DETR Medium (33.3 M); random-search tuning.')], size=12, after=2)

# =============== Column 3: Results + Conclusion ===============
x = PX[2] + IN; y = 2.5
y = heading(x, y, 'Results')
y = sub(x, y, 'Navigation in Gazebo (held-out worlds, ground-truth checked)')
fw = (CW - 0.15) / 2
for fx, f in [(x, '/img-039.png'), (x + fw + 0.15, '/img-041.png')]:
    plate = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(fx), Inches(y + 0.02), Inches(fw), Inches(2.3))
    plate.fill.solid(); plate.fill.fore_color.rgb = rgb(WHITE); plate.line.color.rgb = rgb('8E9BB5'); plate.line.width = Pt(0.75)
    plate.shadow.inherit = False; plate.name = 'Figure plate'
    picture(s, PIMG + f, fx + 0.07, y + 0.09, fw - 0.14, 2.16)
caption(x, y + 2.34, 'Fig. 3. Explored maps (paper Fig. 6)', w=fw, h=0.24)
caption(x + fw + 0.15, y + 2.34, 'Fig. 4. Paths of the nine runs (paper Fig. 7)', w=fw, h=0.24)
y += 2.66
tw = 3.95
rows = [['World', 'Coverage', 'Complete', 'ATE'], ['Multi-room loop', '86.3 %', '65.4 %', '0.74 m'], ['Office', '83.8 %', '65.9 %', '0.35 m'],
        ['Maze (dead ends)', '14.3 %', '11.9 %', '0.76 m'], ['Pooled (9 runs)', '61.4 %', '47.7 %', '0.57 m']]
ptable(x, y, tw, rows, [1.4, 0.92, 0.92, 0.71], row_h=0.32, size=11.5, cell_bold={(4, 0): True, (4, 1): True, (4, 2): True, (4, 3): True})
vline(s, x + tw + 0.15, y + 0.05, y + 1.55, color='A7B3C9')
keys = [('29.2 %', 'of 178 goals truly reached (Nav2 reported 50 %)'), ('19 / 20', 'goals with a perfect pose, vs 6 / 19 with AMCL'),
        ('4 / 6', 'avoidance trials (U-trap 3/3, moving box 1/3)'), ('260 ms', 'to stop; 166 ms to half speed')]
for i, (v, l) in enumerate(keys):
    text(s, x + tw + 0.28, y + i * 0.4, CW - tw - 0.28, 0.4, [{'runs': [(v + '  ', {'bold': True, 'size': 14, 'color': HD}), (l, {'size': 10.5})]}], size=10.5, color=TXT, font=TNR, anchor='m')
y += 1.62
text(s, x, y, CW, 0.25, 'Coverage = share of reachable floor explored; ATE = trajectory error. In two of three maze runs no goal was issued.', size=10.5, color=TXT, font=TNR)
y += 0.5
y = sub(x, y, 'Trash detection on our custom SBY dataset')
rows = [['Model', 'mAP@0.5', 'mAP@.5:.95', 'Recall', 'FPS', 'Power', 'FPS/W'],
        ['YOLOv8n', '0.927', '0.820', '0.900', '76.4', '12.7 W', '6.05'],
        ['YOLOv11n-seg', '0.930', '0.821', '0.920', '79.3', '12.9 W', '6.15'],
        ['RF-DETR-M', '0.934', '0.839', '0.894', '41.4', '14.9 W', '2.79']]
y = ptable(x, y + 0.03, CW, rows, [1.25, 0.95, 1.1, 0.7, 0.6, 0.85, 0.85], row_h=0.3, size=11.5,
           cell_bold={(3, 1): True, (3, 2): True, (2, 3): True, (2, 4): True, (2, 6): True})
text(s, x, y + 0.02, CW, 0.45, 'Accuracy on our custom dataset (validation set, 175 images); speed and power on a Jetson Orin Nano at FP16.', size=10.5, color=TXT, font=TNR)
y = para(x, y + 0.45, 0.72, [
    bl('All three exceed 0.92 mAP@0.5 on our dataset; RF-DETR draws the tightest boxes but is ~22× larger.'),
    bl('Dust is hardest (cement dust 64.6 % AP for RF-DETR). YOLOv11n-seg is the best fit for the robot.')], size=12, after=2)
y = heading(x, y + 0.04, 'Conclusion')
y = para(x, y, 0.92, [{'t': 'The prototype performs manual mode on hardware. In simulation, navigation explores up to 86 % of the reachable floor in room-like worlds; localisation, not the planner, limits goal accuracy. All three detectors exceed 0.92 mAP@0.5 on our custom dataset, running at up to 79 FPS on a Jetson Orin Nano.', 'align': 'l'}], size=12)
y = heading(x, y + 0.02, 'Future Work')
half = (CW - 0.3) / 2
for i, items in enumerate([['Deploy navigation on the physical robot and re-tune it', 'Fix maze stalls and sudden moving obstacles'],
                           ['Run the detector on the robot; integrate both subsystems', 'Actuate arm and vacuum; semi-automatic and automatic modes']]):
    text(s, x + i * (half + 0.3), y, half, 1.0, [{'t': it, 'bullet': True, 'bucolor': HD, 'size': 11.5, 'color': TXT, 'font': TNR, 'after': 2} for it in items])


prs.save(B + '/Swachh_Poster_large.pptx')   # sample-size version (21.99 x 14.14 in), kept for reference

# ---------------- convert to an exact A3 landscape canvas (420 x 297 mm) ----------------
from pptx.util import Emu
from pptx.shapes.picture import Picture
from pptx.shapes.graphfrm import GraphicFrame
from pptx.shapes.connector import Connector
A3W, A3H = 420 * 36000, 297 * 36000
FX = A3W / prs.slide_width; FY = A3H / prs.slide_height; FONT = 0.80; MIN_SZ = 800


def scale_shape(sh):
    if isinstance(sh, Connector):
        bx, by, ex, ey = sh.begin_x, sh.begin_y, sh.end_x, sh.end_y
        sh.begin_x, sh.begin_y, sh.end_x, sh.end_y = int(bx * FX), int(by * FY), int(ex * FX), int(ey * FY)
        return
    if sh.left is None:   # placeholder inheriting its position
        return
    l, t, w, h = sh.left, sh.top, sh.width, sh.height
    if isinstance(sh, Picture):   # keep aspect: scale uniformly by FX, centre in the re-proportioned slot
        nw, nh = int(w * FX), int(h * FX)
        sh.left, sh.width, sh.height = int(l * FX), nw, nh
        sh.top = int(t * FY + (h * FY - nh) / 2)
        return
    sh.left, sh.top, sh.width, sh.height = int(l * FX), int(t * FY), int(w * FX), int(h * FY)
    if isinstance(sh, GraphicFrame) and sh.has_table:
        for c in sh.table.columns: c.width = int(c.width * FX)
        for r in sh.table.rows: r.height = int(r.height * FY)


def scale_fonts(el):
    for tag in ('a:rPr', 'a:endParaRPr', 'a:defRPr'):
        for e in el.iter(qn(tag)):
            if e.get('sz'): e.set('sz', str(max(MIN_SZ, int(int(e.get('sz')) * FONT))))
    for e in el.iter(qn('a:spcPts')):
        e.set('val', str(int(int(e.get('val')) * FONT)))


master = prs.slide_master
for sh in master.shapes: scale_shape(sh)
for lay in master.slide_layouts:
    for sh in lay.shapes: scale_shape(sh)
for sh in s.shapes: scale_shape(sh)
scale_fonts(s.shapes._spTree)
prs.slide_width, prs.slide_height = A3W, A3H
prs.save(OUT)
print('saved', OUT, 'A3: %.1f x %.1f mm' % (prs.slide_width / 36000, prs.slide_height / 36000))
