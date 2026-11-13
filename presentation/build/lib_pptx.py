"""Shared python-pptx helpers for the SBY deck and poster."""
import copy
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION, XL_TICK_LABEL_POSITION
from pptx.oxml.ns import qn
from lxml import etree

R = '/home/hrishikesh/Swachh'
B = R + '/presentation/build'
FIG = R + '/docs/paper_out/figures'
PIMG = B + '/paperimg'
P2M = B + '/p2x/ppt/media'
ICON = B + '/icons'
LOGO = P2M + '/image5.jpg'
ALT = {'img-014.png': 'SBY four-layer architecture diagram (paper Fig. 1)', 'img-016.png': 'Photo of the SBY prototype robot',
       'image14.jpg': 'Photo of the touchscreen HMI mounted on the robot', 'image11.jpg': 'Photo of the prototype under manual control',
       'img-021.png': 'Dataset sample: bottles', 'img-022.png': 'Dataset sample: paper', 'img-023.png': 'Dataset sample: plastic wrapper',
       'img-024.png': 'Dataset sample: aluminium foil', 'img-025.png': 'Dataset sample: cement dust', 'img-026.png': 'Dataset sample: wooden dust',
       'img-029.png': 'YOLOv8 network architecture', 'img-032.png': 'RF-DETR network architecture',
       'img-039.png': 'True floor plans next to the maps explored in three runs per world',
       'fig_costmap_layers.png': 'SLAM occupancy grid, global costmap and local costmap', 'fig_test_worlds.png': 'Floor plans of the held-out Gazebo test worlds', 'img-041.png': 'Paths of the nine exploration episodes over the floor plans (paper Fig. 7)', 'arch_transparent.png': 'SBY four-layer architecture diagram (paper Fig. 1)', 'crop_utrap.png': 'Avoidance scenario: static U-shaped trap', 'crop_dynamic.png': 'Avoidance scenario: box that suddenly moves out from behind a wall'}

# palette
NAVY = '14284B'; BLUE = '1F5FAD'; INK = '1F2937'; GREY = '5B6472'; MUTED = '8A93A3'
CARD = 'F2F5FA'; LINE = 'D5DCE6'; WHITE = 'FFFFFF'
GREEN = '2E7D32'; GREEN_L = 'E7F3E8'
SIMB = '1F5FAD'; SIMB_L = 'E4EDF9'
ORANGE = 'C2410C'; ORANGE_L = 'FCEDE4'
RED = 'B91C1C'
HEAD = 'Cambria'; BODY = 'Calibri'; MONO = 'Consolas'


def rgb(h):
    return RGBColor.from_string(h)


def _apply_run(run, size, color, bold=False, italic=False, font=BODY):
    f = run.font
    f.size = Pt(size); f.bold = bold; f.italic = italic; f.name = font
    f.color.rgb = rgb(color)


def set_bullet(p, char='•', indent_in=0.16, color=None):
    pPr = p._p.get_or_add_pPr()
    pPr.set('marL', str(int(Inches(indent_in)))); pPr.set('indent', str(-int(Inches(indent_in))))
    for tag in ('a:buNone', 'a:buChar', 'a:buAutoNum', 'a:buFont', 'a:buClr'):
        for e in pPr.findall(qn(tag)):
            pPr.remove(e)
    if color:
        buClr = etree.SubElement(pPr, qn('a:buClr')); s = etree.SubElement(buClr, qn('a:srgbClr')); s.set('val', color)
    buFont = etree.SubElement(pPr, qn('a:buFont')); buFont.set('typeface', 'Arial')
    bu = etree.SubElement(pPr, qn('a:buChar')); bu.set('char', char)


def text(slide, x, y, w, h, paras, size=12, color=INK, font=BODY, bold=False, align='l', anchor='t',
         margin=0.0, after=0, line=None, name=None, autofit=False):
    """paras: str | list of items; item = str | {'runs':[(txt,{opts})...] or 't':str, 'bullet':bool, 'size','color','bold','after','align','font','italic'}"""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name: tb.name = name
    tf = tb.text_frame; tf.word_wrap = True
    m = Inches(margin); tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = m
    tf.vertical_anchor = {'t': MSO_ANCHOR.TOP, 'm': MSO_ANCHOR.MIDDLE, 'b': MSO_ANCHOR.BOTTOM}[anchor]
    if isinstance(paras, str): paras = [paras]
    first = True
    for item in paras:
        if isinstance(item, str): item = {'t': item}
        p = tf.paragraphs[0] if first else tf.add_paragraph(); first = False
        al = item.get('align', align)
        p.alignment = {'l': PP_ALIGN.LEFT, 'c': PP_ALIGN.CENTER, 'r': PP_ALIGN.RIGHT}[al]
        p.space_after = Pt(item.get('after', after))
        if item.get('before'): p.space_before = Pt(item['before'])
        if line or item.get('line'): p.line_spacing = item.get('line', line)
        runs = item.get('runs') or [(item.get('t', ''), {})]
        for txt, o in runs:
            r = p.add_run(); r.text = txt
            _apply_run(r, o.get('size', item.get('size', size)), o.get('color', item.get('color', color)),
                       o.get('bold', item.get('bold', bold)), o.get('italic', item.get('italic', False)),
                       o.get('font', item.get('font', font)))
        if item.get('bullet'):
            set_bullet(p, item.get('char', '•'), item.get('indent', 0.16), item.get('bucolor'))
    if autofit:
        bodyPr = tf._txBody.find(qn('a:bodyPr'))
        etree.SubElement(bodyPr, qn('a:normAutofit'))
    return tb


def box(slide, x, y, w, h, fill=CARD, line=None, radius=0.06, shape='round', name=None, line_w=0.75):
    st = {'round': MSO_SHAPE.ROUNDED_RECTANGLE, 'rect': MSO_SHAPE.RECTANGLE, 'oval': MSO_SHAPE.OVAL,
          'chevron': MSO_SHAPE.CHEVRON, 'pentagon': MSO_SHAPE.PENTAGON, 'arrow': MSO_SHAPE.RIGHT_ARROW}[shape]
    s = slide.shapes.add_shape(st, Inches(x), Inches(y), Inches(w), Inches(h))
    if name: s.name = name
    if shape == 'round':
        s.adjustments[0] = radius
    if fill:
        s.fill.solid(); s.fill.fore_color.rgb = rgb(fill)
    else:
        s.fill.background()
    if line:
        s.line.color.rgb = rgb(line); s.line.width = Pt(line_w)
    else:
        s.line.fill.background()
    s.shadow.inherit = False
    s.text_frame.text = ''
    return s


def shape_text(s, paras, size=11, color=INK, bold=False, align='c', anchor='m', font=BODY, margin=0.04):
    tf = s.text_frame; tf.word_wrap = True
    m = Inches(margin); tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = m
    tf.vertical_anchor = {'t': MSO_ANCHOR.TOP, 'm': MSO_ANCHOR.MIDDLE, 'b': MSO_ANCHOR.BOTTOM}[anchor]
    if isinstance(paras, str): paras = [paras]
    for i, item in enumerate(paras):
        if isinstance(item, str): item = {'t': item}
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = {'l': PP_ALIGN.LEFT, 'c': PP_ALIGN.CENTER, 'r': PP_ALIGN.RIGHT}[item.get('align', align)]
        if item.get('after'): p.space_after = Pt(item['after'])
        runs = item.get('runs') or [(item.get('t', ''), {})]
        for txt, o in runs:
            r = p.add_run(); r.text = txt
            _apply_run(r, o.get('size', item.get('size', size)), o.get('color', item.get('color', color)),
                       o.get('bold', item.get('bold', bold)), o.get('italic', False), o.get('font', item.get('font', font)))


def icon_circle(slide, x, y, d, icon, fill=BLUE):
    c = box(slide, x, y, d, d, fill=fill, shape='oval')
    pad = d * 0.2
    slide.shapes.add_picture(f'{ICON}/{icon}_w.png', Inches(x + pad), Inches(y + pad), Inches(d - 2 * pad), Inches(d - 2 * pad))
    return c


def num_circle(slide, x, y, d, n, fill=BLUE, size=12):
    c = box(slide, x, y, d, d, fill=fill, shape='oval')
    shape_text(c, str(n), size=size, color=WHITE, bold=True, margin=0)
    return c


def arrow(slide, x1, y1, x2, y2, color=MUTED, w=1.5):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = rgb(color); c.line.width = Pt(w)
    ln = c.line._get_or_add_ln()
    tail = etree.SubElement(ln, qn('a:tailEnd')); tail.set('type', 'triangle'); tail.set('w', 'med'); tail.set('len', 'med')
    spPr = c._element.spPr
    etree.SubElement(spPr, qn('a:effectLst'))
    st = c._element.find(qn('p:style'))
    if st is not None: c._element.remove(st)
    return c


def picture(slide, path, x, y, w=None, h=None, crop=None, name=None):
    """Place picture; if both w and h given and crop=='fit' → crop to fill box (center)."""
    from PIL import Image
    im = Image.open(path); iw, ih = im.size
    if w and h and crop == 'fill':
        box_r = w / h; img_r = iw / ih
        pic = slide.shapes.add_picture(path, Inches(x), Inches(y), Inches(w), Inches(h))
        if img_r > box_r:  # too wide → crop sides
            c = (1 - box_r / img_r) / 2; pic.crop_left = c; pic.crop_right = c
        else:
            c = (1 - img_r / box_r) / 2; pic.crop_top = c; pic.crop_bottom = c
    elif w and h:  # fit inside box, centered
        r = min(w / iw, h / ih); pw, ph = iw * r, ih * r
        pic = slide.shapes.add_picture(path, Inches(x + (w - pw) / 2), Inches(y + (h - ph) / 2), Inches(pw), Inches(ph))
    elif w:
        pic = slide.shapes.add_picture(path, Inches(x), Inches(y), width=Inches(w))
    else:
        pic = slide.shapes.add_picture(path, Inches(x), Inches(y), height=Inches(h))
    if name: pic.name = name
    import os
    alt = ALT.get(os.path.basename(path))
    if alt:
        pic._element.nvPicPr.cNvPr.set('descr', alt); pic.name = alt[:60]
    return pic


def table(slide, x, y, w, rows, col_w=None, row_h=0.26, size=10, header_fill=NAVY, header_color=WHITE,
          zebra='F5F7FB', bold_cells=(), color_cells=None, font=BODY, align_cols=None, first_col_bold=False):
    nr, nc = len(rows), len(rows[0])
    gt = slide.shapes.add_table(nr, nc, Inches(x), Inches(y), Inches(w), Inches(row_h * nr))
    t = gt.table
    tblPr = t._tbl.tblPr
    # remove default style banding look
    tblPr.set('bandRow', '0'); tblPr.set('firstRow', '0')
    if col_w:
        for i, cw in enumerate(col_w): t.columns[i].width = Inches(cw)
    for r in range(nr):
        t.rows[r].height = Inches(row_h)
        for c in range(nc):
            cell = t.cell(r, c); cell.margin_left = cell.margin_right = Inches(0.06)
            cell.margin_top = cell.margin_bottom = Inches(0.02)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            val = rows[r][c]
            tf = cell.text_frame; tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if (c == 0 or (align_cols and align_cols[c] == 'l')) else PP_ALIGN.CENTER
            run = p.add_run(); run.text = str(val)
            isb = (r == 0) or ((r, c) in bold_cells) or (first_col_bold and c == 0)
            col = header_color if r == 0 else (color_cells or {}).get((r, c), INK)
            _apply_run(run, size, col, isb, font=font)
            cell.fill.solid()
            cell.fill.fore_color.rgb = rgb(header_fill if r == 0 else (zebra if (zebra and r % 2 == 0) else WHITE))
    return gt


def bar_chart(slide, x, y, w, h, cats, series, colors, title=None, maxv=None, minv=0, fmt='0.0', legend=True,
              label_size=9, axis_size=9, gap=60, overlap=-10, show_val_axis=False, num_fmt_axis=None, bar=False):
    cd = CategoryChartData(); cd.categories = cats
    for name, vals in series: cd.add_series(name, vals)
    ct = XL_CHART_TYPE.BAR_CLUSTERED if bar else XL_CHART_TYPE.COLUMN_CLUSTERED
    gf = slide.shapes.add_chart(ct, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    ch = gf.chart
    ch.font.name = BODY; ch.font.size = Pt(axis_size); ch.font.color.rgb = rgb(GREY)
    if title:
        ch.has_title = True
        ch.chart_title.text_frame.text = title
        r = ch.chart_title.text_frame.paragraphs[0].runs[0]
        _apply_run(r, 11, INK, True)
    else:
        ch.has_title = False
    ch.has_legend = legend and len(series) > 1
    if ch.has_legend:
        ch.legend.position = XL_LEGEND_POSITION.TOP; ch.legend.include_in_layout = False
        ch.legend.font.size = Pt(axis_size); ch.legend.font.name = BODY
    plot = ch.plots[0]; plot.gap_width = gap; plot.overlap = overlap
    plot.has_data_labels = True
    dl = plot.data_labels; dl.number_format = fmt; dl.number_format_is_linked = False
    dl.font.size = Pt(label_size); dl.font.name = BODY; dl.font.color.rgb = rgb(INK)
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    for s, col in zip(plot.series, colors):
        s.format.fill.solid(); s.format.fill.fore_color.rgb = rgb(col)
        s.format.line.fill.background()
        s.invert_if_negative = False
    va = ch.value_axis
    if maxv is not None: va.maximum_scale = maxv
    va.minimum_scale = minv
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = rgb('E5E9F0'); va.major_gridlines.format.line.width = Pt(0.5)
    va.format.line.fill.background()
    va.tick_labels.font.size = Pt(axis_size); va.tick_labels.font.color.rgb = rgb(MUTED)
    if num_fmt_axis:
        va.tick_labels.number_format = num_fmt_axis; va.tick_labels.number_format_is_linked = False
    if not show_val_axis:
        va.tick_label_position = XL_TICK_LABEL_POSITION.NONE
        va.has_major_gridlines = False
    ca = ch.category_axis
    ca.tick_labels.font.size = Pt(axis_size); ca.tick_labels.font.color.rgb = rgb(INK)
    ca.format.line.color.rgb = rgb(LINE)
    ca.has_major_gridlines = False
    return gf


def status_chip(slide, x, y, label, kind, w=None, size=9):
    fill, col = {'done': (GREEN_L, GREEN), 'sim': (SIMB_L, SIMB), 'left': (ORANGE_L, ORANGE)}[kind]
    w = w or (0.12 + 0.068 * len(label))
    s = box(slide, x, y, w, 0.24, fill=fill, radius=0.5)
    shape_text(s, label, size=size, color=col, bold=True, margin=0.02)
    return s
