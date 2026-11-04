"""Fill sections_DE_template.tex from paper_values.json (no numbers are typed into the output)."""
import json, os, sys
sys.path.insert(0, os.path.expanduser('~/Swachh/Navigation/Simulation/vacuum_ws/src/vacuum_eval'))
from vacuum_eval.paper_tables import fill
D = os.path.expanduser('~/Swachh/docs/paper_out/')
V = json.load(open(D + 'paper_values.json'))
text, missing = fill(open(D + 'sections_DE_template.tex', encoding='utf-8').read(), V)
if missing:
    print('MISSING TOKENS', sorted(set(missing))); sys.exit(2)
open(D + 'sections_D_E.tex', 'w', encoding='utf-8').write(text)
print('written', len(text.splitlines()), 'lines')
