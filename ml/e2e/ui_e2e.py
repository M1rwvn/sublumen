"""Playwright click-through of every tab. Run with the server up: BASE=http://localhost:5055 python ml/e2e/ui_e2e.py (from backend/ so tests/conftest imports)."""
import sys, os, base64, json
sys.path.insert(0, 'tests')
from conftest import make_png
from playwright.sync_api import sync_playwright
BASE = os.environ.get('BASE', 'http://localhost:5055'); OUT = os.environ.get('SHOTS', '/downloads/shots'); os.makedirs(OUT, exist_ok=True)
EMAIL, PW = os.environ.get('E', 'admin@demo.org'), os.environ.get('P', 'demo-pass-123')
open('/tmp/cover.png', 'wb').write(make_png(128, 128, seed=3))
res = {}
def check(name, ok, extra=''):
    res[name] = bool(ok); print(('PASS ' if ok else 'FAIL ') + name, extra)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    ctx = b.new_context(viewport={'width': 1200, 'height': 800}, color_scheme='dark', accept_downloads=True)
    pg = ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    pg.goto(BASE + '/'); pg.get_by_label('Email').fill(EMAIL); pg.get_by_label('Password').fill(PW)
    pg.get_by_role('button', name='Sign in').click(); pg.get_by_text('Stego Studio').first.wait_for()
    check('login', True)
    # Studio embed (keyed) + extract
    pg.locator('input[type=file]').first.set_input_files('/tmp/cover.png')
    pg.locator('textarea').fill('hello from the browser'); pg.locator('input[type=password]').first.fill('browser-pw')
    pg.get_by_role('checkbox').check()
    pg.get_by_role('button', name='Encrypt & embed').click(); pg.get_by_text('PSNR').first.wait_for()
    href = pg.get_by_text('Download stego.png').get_attribute('href')
    open('/tmp/stego_ui.png', 'wb').write(base64.b64decode(href.split(',', 1)[1]))
    check('studio_embed', True, pg.locator('.msg.ok').first.inner_text())
    pg.screenshot(path=f'{OUT}/ui_1_studio_dark.png')
    pg.locator('input[type=file]').nth(1).set_input_files('/tmp/stego_ui.png'); pg.locator('input[type=password]').nth(1).fill('browser-pw')
    pg.get_by_role('button', name='Extract', exact=True).click(); pg.get_by_text('hello from the browser').wait_for(timeout=5000)
    check('extract_correct_password', True)
    pg.locator('input[type=password]').nth(1).fill('wrong-pw'); pg.get_by_role('button', name='Extract', exact=True).click()
    pg.locator('.msg.err').wait_for(timeout=5000); check('extract_wrong_password_rejected', pg.locator('.msg.err').count() >= 1, pg.locator('.msg.err').first.inner_text())
    pg.screenshot(path=f'{OUT}/ui_2_extract.png', full_page=True)
    # Cases
    pg.get_by_role('button', name='Cases & Evidence').click()
    pg.get_by_text('No cases yet').wait_for(); check('empty_state_cases', True)
    pg.get_by_role('button', name='load the demo case').click(); pg.get_by_test_id('summary').wait_for(timeout=15000)
    check('demo_case_flow', 'model score' in pg.get_by_test_id('summary').inner_text().lower(), pg.get_by_test_id('summary').inner_text().replace('\n', ' '))
    pg.screenshot(path=f'{OUT}/ui_7_demo_case.png', full_page=True)
    pg.get_by_placeholder('New case title').fill('قضية اختبار Browser'); pg.get_by_role('button', name='Create').click()
    pg.get_by_text('Upload evidence').wait_for()
    pg.locator('input[type=file]').set_input_files('/tmp/cover.png'); pg.get_by_role('button', name='Upload & hash').click()
    pg.get_by_role('button', name='Analyze').wait_for(); pg.get_by_role('button', name='Analyze').click()
    pg.get_by_text('indicators only').wait_for(); check('analysis', pg.get_by_text('chi_square').count() > 0)
    check('default_model_v8', pg.get_by_text('model_v8_hgb').count() > 0)
    pg.get_by_role('button', name='Generate PDF report').click(); pg.wait_for_timeout(1500)
    with pg.expect_download() as d: pg.get_by_text('Download report.pdf').click()
    d.value.save_as('/tmp/ui_report.pdf'); check('pdf_download', open('/tmp/ui_report.pdf', 'rb').read(4) == b'%PDF', os.path.getsize('/tmp/ui_report.pdf'))
    # Visual
    pg.get_by_role('button', name='Visual Lab').click(); pg.get_by_role('button', name='Anomaly heatmap').click(); pg.locator('img.pv').wait_for()
    pg.get_by_role('button', name='Bit plane').click(); pg.wait_for_timeout(500); check('visual_lab', pg.locator('img.pv').count() == 1)
    # Compare (SSIM dashboard)
    pg.get_by_role('button', name='Compare').click()
    pg.locator('input[type=file]').nth(0).set_input_files('/tmp/cover.png'); pg.locator('input[type=file]').nth(1).set_input_files('/tmp/stego_ui.png')
    pg.get_by_role('button', name='Compare', exact=True).nth(1).click() if pg.get_by_role('button', name='Compare', exact=True).count() > 1 else None
    pg.get_by_test_id('ssim-dash').wait_for(timeout=8000)
    check('compare_ssim_dashboard', pg.get_by_alt_text('ssim map').count() == 1 and pg.get_by_alt_text('diff').count() == 1, pg.get_by_test_id('ssim-dash').inner_text().replace('\n', ' '))
    pg.screenshot(path=f'{OUT}/ui_3_compare_ssim.png', full_page=True)
    # Models / Bench
    pg.get_by_role('button', name='Models').click(); pg.get_by_text('model_v7_svm_rbf').first.wait_for(); check('models_tab', True)
    pg.get_by_role('button', name='Benchmark Lab').click(); pg.get_by_text('Benchmark #').first.wait_for(); check('bench_tab', True)
    # Light mode
    pg.get_by_role('button', name='Compare').click(); pg.get_by_label('Toggle theme').click()
    check('light_mode_attr', pg.evaluate("document.documentElement.dataset.theme") == 'light')
    pg.screenshot(path=f'{OUT}/ui_4_light.png', full_page=True)
    bg = pg.evaluate("getComputedStyle(document.body).backgroundColor"); check('light_bg', bg == 'rgb(237, 241, 247)', bg)
    # Mobile
    m = b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, device_scale_factor=2); mp = m.new_page()
    mp.goto(BASE + '/'); mp.get_by_label('Email').fill(EMAIL); mp.get_by_label('Password').fill(PW); mp.get_by_role('button', name='Sign in').click()
    mp.get_by_text('Stego Studio').first.wait_for()
    sw = mp.evaluate("document.documentElement.scrollWidth"); cw = mp.evaluate("document.documentElement.clientWidth")
    check('mobile_no_horizontal_page_scroll', sw <= cw + 1, f'scrollWidth={sw} clientWidth={cw}')
    mp.screenshot(path=f'{OUT}/ui_5_mobile.png')
    mp.get_by_role('button', name='Models').click(); mp.get_by_text('model_v7_svm_rbf').first.wait_for()
    sw = mp.evaluate("document.documentElement.scrollWidth"); check('mobile_models_no_page_scroll', sw <= cw + 1, f'scrollWidth={sw}')
    mp.screenshot(path=f'{OUT}/ui_6_mobile_models.png')
    errs = [e for e in errs if '422' not in e]  # the 422 is the deliberate wrong-password extract
    check('no_page_or_console_errors', not errs, errs[:3])
    b.close()
print(json.dumps(res)); sys.exit(0 if all(res.values()) else 1)
