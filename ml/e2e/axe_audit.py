"""Automated accessibility audit (axe-core 4.x) of every tab in dark and light mode. Needs axe.min.js (npm i axe-core) at AXE path.
Run with the server up: BASE=http://localhost:5055 AXE=/tmp/axe.min.js python ml/e2e/axe_audit.py. axe finds a subset of WCAG issues; it is not a full audit."""
import os, json
from playwright.sync_api import sync_playwright
BASE = os.environ.get('BASE', 'http://localhost:5055'); AXE = open(os.environ.get('AXE', '/tmp/axe.min.js')).read()
TABS = ['Stego Studio', 'Cases & Evidence', 'Visual Lab', 'Compare', 'Models', 'Benchmark Lab']
out = {}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    for scheme in ('dark', 'light'):
        pg = b.new_context(viewport={'width': 1280, 'height': 900}, color_scheme=scheme).new_page()
        pg.goto(BASE + '/'); pg.add_script_tag(content=AXE)
        res = pg.evaluate("axe.run(document, {runOnly:['wcag2a','wcag2aa','wcag21aa','best-practice']}).then(r=>r.violations.map(v=>({id:v.id,impact:v.impact,n:v.nodes.length,help:v.help})))")
        out[f'{scheme}|login'] = res
        pg.get_by_label('Email').fill('admin@demo.org'); pg.get_by_label('Password').fill('demo-pass-123'); pg.get_by_role('button', name='Sign in').click()
        pg.get_by_text('Stego Studio').first.wait_for()
        for t in TABS:
            pg.get_by_role('button', name=t).first.click(); pg.wait_for_timeout(700)
            pg.add_script_tag(content=AXE)
            out[f'{scheme}|{t}'] = pg.evaluate("axe.run(document, {runOnly:['wcag2a','wcag2aa','wcag21aa','best-practice']}).then(r=>r.violations.map(v=>({id:v.id,impact:v.impact,n:v.nodes.length,help:v.help,ex:v.nodes[0].target.join(' ')+' | '+(v.nodes[0].any[0]||{}).message})))")
json.dump(out, open('/tmp/axe_result.json', 'w'), indent=1)
for k, v in out.items(): print(k, len(v), [(x['id'], x['n']) for x in v])
