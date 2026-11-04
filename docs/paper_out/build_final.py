"""Assemble docs/PAPER_SECTIONS_FINAL.md. No numbers are computed here: text for 3.7 and 5.1-5.3 is copied
from docs/PAPER_SECTIONS_FILL.md; 3.8, 5.4, 7.3 and 7.4 come from sections_template.md with every
number filled from paper_values.json (written by vacuum_eval.paper_tables)."""
import json, os, sys
sys.path.insert(0, os.path.expanduser('~/Swachh/Navigation/Simulation/vacuum_ws/src/vacuum_eval'))
from vacuum_eval.paper_tables import fill

D = os.path.expanduser('~/Swachh/docs/')
fillsrc = open(D + 'PAPER_SECTIONS_FILL.md', encoding='utf-8').read()
V = json.load(open(D + 'paper_out/paper_values.json'))
tmpl = open(D + 'paper_out/sections_template.md', encoding='utf-8').read()
tables = open(D + 'paper_out/paper_tables.md', encoding='utf-8').read()


def cut(src, a, b):
    i = src.index(a); j = src.index(b, i)
    return src[i:j].rstrip() + '\n'


s37 = cut(fillsrc, '## 3.7 Navigation Strategy', '## 4.2')
s5 = cut(fillsrc, '### 5.1 Visual SLAM', '### 5.4 Decision Module')
text, missing = fill(tmpl, V)
if missing:
    print('MISSING TOKENS', sorted(set(missing))); sys.exit(2)
s38 = cut(text, '## 3.8', '## 5.4')
s54 = cut(text, '## 5.4', '## 7.3')
s73 = text[text.index('## 7.3'):].rstrip() + '\n'
out = ('# Final text for sections 3.7, 3.8, 5.1 to 5.4, 7.3 and 7.4\n\n'
       '**Written for:** the paper authors. Numbers in 7.3 and 7.4 are filled by a script from the raw result files '
       '(`vacuum_eval.paper_tables`, verified by two independent recomputations); nothing was calculated by hand. '
       'Every statement was then fact-checked sentence by sentence against the code, configs and logs by three '
       'independent read-only reviewers, and the corrections are applied. '
       'The generated tables are at the end. `[TBD: ...]` marks facts the repository cannot answer.\n\n'
       + s37 + '\n' + s38 + '\n' + s5 + '\n' + s54 + '\n' + s73
       + '\n---\n\n## Appendix: generated tables\n\n' + tables.split('\n', 2)[2])
open(D + 'PAPER_SECTIONS_FINAL.md', 'w', encoding='utf-8').write(out)
print('written', len(out.splitlines()), 'lines')
