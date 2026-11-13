"""v2 design system: restrained, editorial look (assertion-evidence slides).
White page, charcoal text, one accent (deep blue), grey for context, red only to flag a failure in data.
Segoe UI / Segoe UI Semibold. Booktabs tables (rules only). Decluttered native charts with direct labels.
"""
from lib_pptx import *  # noqa: F401,F403
from lib_pptx import _apply_run
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.chart.data import CategoryChartData
from pptx.oxml.ns import qn
from lxml import etree

F = 'Segoe UI'; FS = 'Segoe UI Semibold'; SYM = 'Segoe UI Symbol'; MATH = 'Cambria Math'; MONO2 = 'Consolas'
K = '1A1A1A'      # body text
K2 = '4D4D4D'     # secondary text
G = '7F7F7F'      # captions / notes
G3 = 'C8C8C8'     # chart context bars
RULE = '262626'
HAIR = 'D9D9D9'
ACC = '1F4E79'    # single accent
ACC2 = '8FA9C8'   # lighter accent for a second series
RED = 'A33A2B'    # failure only
NO_STYLE = '{2D5ABB26-0587-4C30-8999-92F81FD0307C}'


def T(slide, x, y, w, h, paras, size=13, color=K, font=F, **kw):
    return text(slide, x, y, w, h, paras, size=size, color=color, font=font, **kw)


def _noshadow(shape):
    # connectors pick up the theme's effect style (a soft shadow); give them an explicit empty effect list
    spPr = shape._element.spPr
    for e in spPr.findall(qn('a:effectLst')): spPr.remove(e)
    etree.SubElement(spPr, qn('a:effectLst'))
    st = shape._element.find(qn('p:style'))
    if st is not None: shape._element.remove(st)


def hline(slide, x1, y, x2, color=HAIR, w=0.75):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y), Inches(x2), Inches(y))
    c.line.color.rgb = rgb(color); c.line.width = Pt(w)
    _noshadow(c)
    return c


def vline(slide, x, y1, y2, color=HAIR, w=0.75):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x), Inches(y1), Inches(x), Inches(y2))
    c.line.color.rgb = rgb(color); c.line.width = Pt(w)
    _noshadow(c)
    return c


def outline_box(slide, x, y, w, h, color=ACC, lw=1.0, fill=None):
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill: s.fill.solid(); s.fill.fore_color.rgb = rgb(fill)
    else: s.fill.background()
    s.line.color.rgb = rgb(color); s.line.width = Pt(lw)
    s.shadow.inherit = False
    return s


def _cell_border(cell, side, w_pt=None, color=RULE):
    tcPr = cell._tc.get_or_add_tcPr()
    tag = {'L': 'a:lnL', 'R': 'a:lnR', 'T': 'a:lnT', 'B': 'a:lnB'}[side]
    for e in tcPr.findall(qn(tag)): tcPr.remove(e)
    ln = etree.Element(qn(tag))
    if w_pt:
        ln.set('w', str(int(w_pt * 12700))); ln.set('cmpd', 'sng')
        sf = etree.SubElement(ln, qn('a:solidFill')); c = etree.SubElement(sf, qn('a:srgbClr')); c.set('val', color)
        d = etree.SubElement(ln, qn('a:prstDash')); d.set('val', 'solid')
    else:
        ln.set('w', '0'); etree.SubElement(ln, qn('a:noFill'))
    # schema order: lnL, lnR, lnT, lnB, ... fill
    order = ['a:lnL', 'a:lnR', 'a:lnT', 'a:lnB']
    idx = 0
    for i, t_ in enumerate(order):
        if t_ == tag: break
        if tcPr.find(qn(t_)) is not None: idx += 1
    tcPr.insert(idx, ln)


def btable(slide, x, y, w, rows, col_w, row_h=0.32, size=11, align=None, header=True, font=F, hfont=FS,
           cell_colors=None, cell_fonts=None, cell_bold=None, hcolor=K, color=K, fill=None, grid=None, valign='m', name=None, rule=RULE, vgrid=None):
    """Booktabs table: heavy top rule, thin rule under header, heavy bottom rule, no fills.
    grid=hex → also thin inner horizontal rules in that colour. fill=hex → cell background (poster)."""
    nr, nc = len(rows), len(rows[0])
    tot = sum(row_h) if isinstance(row_h, (list, tuple)) else row_h * nr
    gf = slide.shapes.add_table(nr, nc, Inches(x), Inches(y), Inches(w), Inches(tot))
    if name: gf.name = name
    t = gf.table; tbl = t._tbl
    tblPr = tbl.tblPr
    for a in ('firstRow', 'bandRow', 'firstCol', 'lastRow', 'lastCol', 'bandCol'): tblPr.set(a, '0')
    sid = tblPr.find(qn('a:tableStyleId'))
    if sid is None: sid = etree.SubElement(tblPr, qn('a:tableStyleId'))
    sid.text = NO_STYLE
    for i, cw in enumerate(col_w): t.columns[i].width = Inches(cw)
    for r in range(nr):
        rh = row_h[r] if isinstance(row_h, (list, tuple)) else row_h
        t.rows[r].height = Inches(rh)
        for c in range(nc):
            cell = t.cell(r, c)
            cell.margin_left = Inches(0.0 if c == 0 else 0.06); cell.margin_right = Inches(0.06)
            cell.margin_top = Inches(0.02); cell.margin_bottom = Inches(0.02)
            cell.vertical_anchor = {'m': MSO_ANCHOR.MIDDLE, 't': MSO_ANCHOR.TOP}[valign]
            if fill: cell.margin_left = Inches(0.08)
            val = rows[r][c]
            tf = cell.text_frame; tf.word_wrap = True
            p = tf.paragraphs[0]
            al = (align[c] if align else ('l' if c == 0 else 'c'))
            p.alignment = {'l': PP_ALIGN.LEFT, 'c': PP_ALIGN.CENTER, 'r': PP_ALIGN.RIGHT}[al]
            is_h = header and r == 0
            fnt = (cell_fonts or {}).get((r, c), hfont if is_h else font)
            col = (cell_colors or {}).get((r, c), hcolor if is_h else color)
            b = (cell_bold or {}).get((r, c), False)
            paras = val if isinstance(val, list) else [str(val)]   # rich cell: list of paragraphs, each str or [(text, opts)]
            for pi, para in enumerate(paras):
                pp = p if pi == 0 else tf.add_paragraph()
                pp.alignment = p.alignment
                for t_, o in ([(para, {})] if isinstance(para, str) else para):
                    run = pp.add_run(); run.text = t_
                    _apply_run(run, o.get('size', size), o.get('color', col), o.get('bold', b), o.get('italic', False), font=o.get('font', fnt))
            if fill:
                cell.fill.solid(); cell.fill.fore_color.rgb = rgb(fill)
            else:
                cell.fill.background()
            _cell_border(cell, 'L', 0.6 if (vgrid and c > 0) else None, vgrid or RULE)
            _cell_border(cell, 'R', 0.6 if (vgrid and c < nc - 1) else None, vgrid or RULE)
            top = 1.25 if r == 0 else (0.6 if (header and r == 1) else (0.4 if grid else None))
            bot = 1.25 if r == nr - 1 else None
            _cell_border(cell, 'T', top, rule if (r == 0 or (header and r == 1)) else (grid or HAIR))
            _cell_border(cell, 'B', bot, rule)
    return gf


def chart(slide, x, y, w, h, cats, series, colors, point_colors=None, fmt='0.0', bar=False, legend=None,
          label_size=10, axis_size=10, gap=50, overlap=-10, maxv=None, minv=0, title=None, suffix=''):
    cd = CategoryChartData(); cd.categories = cats
    for nm, vals in series: cd.add_series(nm, vals)
    ct = XL_CHART_TYPE.BAR_CLUSTERED if bar else XL_CHART_TYPE.COLUMN_CLUSTERED
    gf = slide.shapes.add_chart(ct, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    ch = gf.chart
    ch.font.name = F; ch.font.size = Pt(axis_size); ch.font.color.rgb = rgb(K2)
    if title:
        ch.has_title = True; ch.chart_title.text_frame.text = title
        _apply_run(ch.chart_title.text_frame.paragraphs[0].runs[0], 11, K, False, font=FS)
    else:
        ch.has_title = False
    ch.has_legend = bool(legend)
    if legend:
        ch.legend.position = XL_LEGEND_POSITION.TOP; ch.legend.include_in_layout = False
        ch.legend.font.size = Pt(axis_size); ch.legend.font.name = F; ch.legend.font.color.rgb = rgb(K2)
    plot = ch.plots[0]; plot.gap_width = gap; plot.overlap = overlap
    plot.has_data_labels = True
    dl = plot.data_labels; dl.number_format = fmt + (f'"{suffix}"' if suffix else ''); dl.number_format_is_linked = False
    dl.font.size = Pt(label_size); dl.font.name = F; dl.font.color.rgb = rgb(K)
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    for i, (s_, col) in enumerate(zip(plot.series, colors)):
        s_.format.fill.solid(); s_.format.fill.fore_color.rgb = rgb(col); s_.format.line.fill.background()
        s_.invert_if_negative = False
        if point_colors and i in point_colors:
            for pi, pc in point_colors[i].items():
                pt = s_.points[pi]; pt.format.fill.solid(); pt.format.fill.fore_color.rgb = rgb(pc); pt.format.line.fill.background()
    va = ch.value_axis
    if maxv is not None: va.maximum_scale = maxv
    va.minimum_scale = minv
    va.has_major_gridlines = False; va.visible = False
    ca = ch.category_axis
    ca.tick_labels.font.size = Pt(axis_size); ca.tick_labels.font.color.rgb = rgb(K2); ca.tick_labels.font.name = F
    ca.format.line.color.rgb = rgb('A6A6A6'); ca.format.line.width = Pt(0.75)
    ca.has_major_gridlines = False
    from pptx.enum.chart import XL_TICK_MARK
    ca.major_tick_mark = XL_TICK_MARK.NONE
    return gf


def bignum(slide, x, y, w, value, label, color=ACC, vsize=26, lsize=11, lh=0.6):
    T(slide, x, y, w, 0.5, value, size=vsize, color=color, font=FS, anchor='b')
    T(slide, x, y + 0.52, w, lh, label, size=lsize, color=K2)
