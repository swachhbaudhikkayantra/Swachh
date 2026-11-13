"""CONCISE poster (same layout as build_poster.py, less text): builds presentation/Swachh_Poster.pptx from Sample-Poster.pptx (same master: gradient, header band, 3 panels).
Keeps the sample's BMS logo, title placeholder and author table; replaces all content.
Run: <venv>/bin/python build_poster.py
"""
import sys
sys.path.insert(0, '/home/hrishikesh/Swachh/presentation/build')
from lib_pptx import *
from pptx import Presentation
from pptx.oxml.ns import qn

SRC = R + '/Sample-Poster.pptx'
OUT = R + '/presentation/Swachh_Poster_Concise.pptx'
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


# =============== CONCISE VERSION: same sections, headings, figures and tables; text cut to talking points ===============
BODY_PT = 14
x = PX[0] + IN; y = 2.5
y = heading(x, y, 'Introduction')
y = para(x, y, 1.15, [
    bl('Large indoor spaces are still cleaned by hand: slow and inconsistent'),
    bl('Workers may unknowingly handle hazardous waste'),
    bl('Today\'s cleaning robots only vacuum or mop')], size=14, after=2)
y = para(x, y, 0.95, [{'t': 'Gaps in the literature', 'bold': True, 'color': HD, 'after': 2},
                      bl('Deep-learning trash detection runs off-board'),
                      bl('Onboard detection is not linked to navigation')], size=14, after=2)
y = heading(x, y + 0.1, 'Proposed System')
y = para(x, y, 0.62, [{'runs': [('SBY: ', {'bold': True}), ('an autonomous indoor cleaning robot that navigates, detects trash, picks it up with a 6-DOF arm and vacuums, all computed on board.', {})], 'align': 'l'}], size=14)
picture(s, B + '/arch_transparent.png', x, y + 0.02, CW, 2.45)
y = caption(x, y + 2.48, 'Fig. 1. Four-layer architecture of SBY')
y = para(x, y + 0.02, 0.65, [{'runs': [('Interface: ', {'bold': True}), ('HMI    ', {}), ('Sensor: ', {'bold': True}), ('RGB + D435i depth camera', {})], 'align': 'c', 'after': 2},
                             {'runs': [('Processing: ', {'bold': True}), ('Jetson Orin Nano    ', {}), ('Actuator: ', {'bold': True}), ('Arduino Uno', {})], 'align': 'c'}], size=13)
y = heading(x, y + 0.12, 'Operating Modes')
def mcell(name, status):
    return [[(name, {'bold': True})], [(status, {'size': 11, 'italic': True})]]
rows = [['Mode', 'What it does'],
        [mcell('Manual', 'working on the robot'), 'Operator drives the robot from the HMI: direction, speed, emergency stop'],
        [mcell('Semi-automatic', 'planned'), 'Operator picks the area, task and duration; the robot cleans it'],
        [mcell('Automatic', 'planned'), 'Robot maps, finds trash and acts on its own; operator only monitors']]
y = ptable(x, y + 0.02, CW, rows, [1.75, 4.55], row_h=[0.34, 0.62, 0.62, 0.62], size=13, align=['l', 'l'])

# =============== Column 2: Methodology ===============
x = PX[1] + IN; y = 2.5
y = heading(x, y, 'Methodology')
y = sub(x, y, 'A. Hardware prototype, HMI and manual mode')
picture(s, PIMG + '/img-016.png', x, y + 0.02, 1.65, 1.75, crop='fill')
picture(s, P2M + '/image14.jpg', x + 1.73, y + 0.02, 2.25, 1.75, crop='fill')
para(x + 4.1, y + 0.05, 1.8, [
    bl('50 kg, 3-rack chassis', size=13), bl('BLDC hub motors, 24 V', size=13),
    bl('Jetson Orin Nano + Arduino Uno', size=13), bl('6-DOF 3D-printed arm', size=13)], w=2.2, after=3)
y = caption(x, y + 1.8, 'Fig. 2. Prototype and its HMI touchscreen', w=3.98)
y = para(x, y + 0.02, 0.32, [{'t': 'Manual mode, working on the hardware:', 'bold': True, 'color': HD}], size=13.5)
y = flow(x, y + 0.02, [['HMI', 'touchscreen'], ['Jetson', 'Orin Nano'], ['Arduino', 'Uno'], ['PWM +', 'relays'], ['Hub', 'motors']], 0.6, size=12.5)
y = para(x, y + 0.06, 0.38, [{'t': 'Serial text commands  ·  9 speed levels  ·  emergency stop', 'align': 'c'}], size=13)
y = sub(x, y + 0.08, 'B. Navigation subsystem (ROS 2 Jazzy, Nav2, Gazebo)')
y = flow(x, y + 0.02, [['RTAB-Map SLAM', 'builds the 2D map'], ['Frontier explorer', 'our code: picks the goal'],
                       ['Smac Hybrid-A*', 'plans the path'], ['MPPI controller', 'follows the path']], 0.78, size=11.5, gap=0.18)
y = para(x, y + 0.1, 0.32, [{'t': 'How the robot decides where to explore next', 'bold': True, 'color': HD}], size=13.5)
y = para(x, y, 0.4, [{'t': 'Every frontier (edge of the mapped area) is scored; the best becomes the next goal:', 'align': 'l'}], size=13)
y = para(x, y, 0.45, [{'t': 'S = 1.0 ln(1 + n) − 1.5 d − 0.8 p', 'align': 'c', 'size': 18, 'bold': True, 'color': HD}])
lw3 = CW / 3
for i, (v, d_) in enumerate([('n', 'frontier size: more new map'), ('d', 'distance: farther costs more'), ('p', 'near-obstacle penalty')]):
    text(s, x + i * lw3, y, lw3, 0.35, [{'runs': [(v + ' ', {'bold': True, 'italic': True, 'size': 14, 'color': HD}), (d_, {})], 'align': 'c'}], size=12, color=TXT, font=TNR)
y += 0.45
y = sub(x, y + 0.08, 'C. Trash detection on our custom dataset')
y = para(x, y, 0.36, [{'t': 'Custom dataset: 877 images  ·  6,349 annotations  ·  8 classes', 'bold': True, 'color': HD, 'align': 'c'}], size=14)
samples = ['img-021.png', 'img-022.png', 'img-023.png', 'img-024.png', 'img-025.png', 'img-026.png']
labels = ['Bottle', 'Paper', 'Wrapper', 'Foil', 'Cement dust', 'Wooden dust']
iw = (CW - 5 * 0.06) / 6
for i, f in enumerate(samples):
    picture(s, PIMG + '/' + f, x + i * (iw + 0.06), y + 0.02, iw, 0.78, crop='fill')
    text(s, x + i * (iw + 0.06), y + 0.81, iw, 0.24, [{'t': labels[i], 'align': 'c'}], size=10.5, color=TXT, font=TNR)
y += 1.1
y = para(x, y, 0.75, [
    bl('Robot\'s-eye images: low camera, tilted 30° down'),
    bl('Models compared: YOLOv8n, YOLOv11n-seg, RF-DETR')], size=13.5, after=2)

# =============== Column 3: Results + Conclusion + Future Work ===============
x = PX[2] + IN; y = 2.5
y = heading(x, y, 'Results')
y = sub(x, y, 'Navigation in Gazebo (ground-truth checked)')
fw = (CW - 0.15) / 2
for fx, f in [(x, '/img-039.png'), (x + fw + 0.15, '/img-041.png')]:
    plate = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(fx), Inches(y + 0.02), Inches(fw), Inches(2.3))
    plate.fill.solid(); plate.fill.fore_color.rgb = rgb(WHITE); plate.line.color.rgb = rgb('8E9BB5'); plate.line.width = Pt(0.75)
    plate.shadow.inherit = False; plate.name = 'Figure plate'
    picture(s, PIMG + f, fx + 0.07, y + 0.09, fw - 0.14, 2.16)
caption(x, y + 2.34, 'Fig. 3. Explored maps (paper Fig. 6)', w=fw, h=0.24)
caption(x + fw + 0.15, y + 2.34, 'Fig. 4. Paths of the nine runs (paper Fig. 7)', w=fw, h=0.24)
y += 2.66
tw = 3.6
rows = [['World', 'Coverage', 'ATE'], ['Multi-room loop', '86.3 %', '0.74 m'], ['Office', '83.8 %', '0.35 m'],
        ['Maze (dead ends)', '14.3 %', '0.76 m'], ['Pooled (9 runs)', '61.4 %', '0.57 m']]
ptable(x, y, tw, rows, [1.6, 1.0, 1.0], row_h=0.32, size=12.5, cell_bold={(4, 0): True, (4, 1): True, (4, 2): True})
vline(s, x + tw + 0.15, y + 0.05, y + 1.55, color='A7B3C9')
keys = [('29.2 %', 'goals truly reached'), ('19 / 20', 'with a perfect pose'), ('4 / 6', 'avoidance trials'), ('260 ms', 'to stop')]
for i, (v, l) in enumerate(keys):
    text(s, x + tw + 0.3, y + i * 0.4, CW - tw - 0.3, 0.4, [{'runs': [(v + '  ', {'bold': True, 'size': 15, 'color': HD}), (l, {'size': 12})]}], size=12, color=TXT, font=TNR, anchor='m')
y += 1.65
y = para(x, y, 0.35, [{'t': 'Coverage = reachable floor explored; ATE = trajectory error', 'align': 'l'}], size=11.5)
y = sub(x, y + 0.1, 'Trash detection on our custom dataset')
rows = [['Model', 'mAP@0.5', 'Recall', 'FPS', 'Power'],
        ['YOLOv8n', '0.927', '0.900', '76.4', '12.7 W'],
        ['YOLOv11n-seg', '0.930', '0.920', '79.3', '12.9 W'],
        ['RF-DETR-M', '0.934', '0.894', '41.4', '14.9 W']]
y = ptable(x, y + 0.03, CW, rows, [1.7, 1.2, 1.1, 1.1, 1.2], row_h=0.32, size=12.5, cell_bold={(3, 1): True, (2, 2): True, (2, 3): True})
y = para(x, y + 0.04, 0.32, [{'t': 'Accuracy: custom dataset. Speed: Jetson Orin Nano, FP16', 'align': 'l'}], size=11.5)
y = para(x, y + 0.04, 0.72, [bl('All three exceed 0.92 mAP@0.5'), bl('YOLOv11n-seg: best fit for the robot')], size=13.5, after=2)
y = heading(x, y + 0.08, 'Conclusion')
y = para(x, y, 1.05, [bl('Manual mode works on the robot'), bl('Navigation explores up to 86 % of the floor in simulation'),
                      bl('Detection: > 0.92 mAP@0.5, up to 79 FPS on a Jetson')], size=13.5, after=2)
y = heading(x, y + 0.04, 'Future Work')
half = (CW - 0.3) / 2
for i, items in enumerate([['Navigation on the real robot', 'Integrate both subsystems'], ['Arm and vacuum actuation', 'Semi-automatic and automatic modes']]):
    text(s, x + i * (half + 0.3), y, half, 0.8, [{'t': it, 'bullet': True, 'bucolor': HD, 'size': 13, 'color': TXT, 'font': TNR, 'after': 2} for it in items])


prs.save(B + '/Swachh_Poster_Concise_large.pptx')   # sample-size version (21.99 x 14.14 in), kept for reference

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
