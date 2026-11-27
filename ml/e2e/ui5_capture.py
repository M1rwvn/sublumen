"""1920x1080 screenshots of the analysis result view (gauge, tile overlay, indicator explanations) for a clean and a partly embedded full-size photo."""
import os
from playwright.sync_api import sync_playwright
BASE = os.environ.get('BASE', 'http://localhost:5055'); OUT = os.environ.get('OUT', '/downloads/ui5')
def run(pg, f, title, shot):
    pg.get_by_role('button', name='Cases & Evidence').click(); pg.wait_for_timeout(500)
    pg.get_by_placeholder('New case title').fill(title); pg.get_by_role('button', name='Create').click(); pg.get_by_text('Upload evidence').wait_for()
    pg.locator('input[type=file]').set_input_files(f); pg.get_by_role('button', name='Upload & hash').click(); pg.get_by_role('button', name='Analyze').wait_for()
    pg.get_by_role('button', name='Analyze').click(); pg.get_by_text('indicators only').wait_for(); pg.get_by_role('img', name='Evidence image with model evidence overlay: amber tiles carry more model evidence').wait_for(timeout=30000)
    AX = os.environ.get('AXE')
    if AX:
        pg.add_script_tag(content=open(AX).read())
        for sch in ('dark', 'light'):
            pg.evaluate(f"document.documentElement.dataset.theme='{sch}'"); print('axe', shot, sch, pg.evaluate("axe.run(document,{runOnly:['wcag2a','wcag2aa','wcag21aa','best-practice']}).then(r=>r.violations.map(v=>v.id+':'+v.nodes.length+' '+v.nodes[0].target.join(' ')))"))
        pg.evaluate("document.documentElement.dataset.theme='dark'")
    pg.wait_for_timeout(1500); pg.get_by_test_id('summary').scroll_into_view_if_needed(); pg.wait_for_timeout(500); pg.screenshot(path=f'{OUT}/{shot}.png')
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox', '--force-device-scale-factor=1'])
    ctx = b.new_context(viewport={'width': 1920, 'height': 1080}, color_scheme='dark'); ctx.add_init_script("localStorage.setItem('ss_theme','dark')")
    pg = ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(BASE + '/'); pg.get_by_label('Email').fill('admin@demo.org'); pg.get_by_label('Password').fill('demo-pass-123'); pg.get_by_role('button', name='Sign in').click(); pg.wait_for_timeout(1200)
    run(pg, OUT + '/photo_top_half_embedded.png', 'Case: embedded top half', 'result_embedded')
    pg.reload(); pg.wait_for_timeout(1000)
    run(pg, OUT + '/photo_clean.png', 'Case: clean photo', 'result_clean')
    print('page errors', errs); b.close()
