"""Promo screen recording + 1920x1080 screenshots of the running app (one flow, same demo image)."""
import os, sys, json, base64, shutil
from playwright.sync_api import sync_playwright
BASE = os.environ.get('BASE', 'http://localhost:5055'); OUT = os.environ.get('OUT', '/downloads/promo'); VID = '/tmp/vid'
COVER = OUT + '/sublumen-demo-cover.png'
MSG_HEAD = 'Meet at the old pier at midnight. Bring the drive. '
MSG = (MSG_HEAD * 60)[:1500]
notes = {}
def pause(pg, ms=1200): pg.wait_for_timeout(ms)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox', '--force-device-scale-factor=1'])
    ctx = b.new_context(viewport={'width': 1920, 'height': 1080}, record_video_dir=VID, record_video_size={'width': 1920, 'height': 1080},
                        color_scheme='dark', accept_downloads=True)
    ctx.add_init_script("localStorage.setItem('ss_theme','dark')")
    pg = ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(BASE + '/'); pause(pg, 1500)
    pg.get_by_label('Email').click(); pg.get_by_label('Email').type('admin@demo.org', delay=70); pause(pg, 600)
    pg.get_by_label('Password').click(); pg.get_by_label('Password').type('demo-pass-123', delay=70); pause(pg, 800)
    pg.screenshot(path=f'{OUT}/shot_0_login.png')
    pg.get_by_role('button', name='Sign in').click(); pg.get_by_text('Stego Studio').first.wait_for(); pause(pg)
    # Studio
    pg.locator('input[type=file]').first.set_input_files(COVER); pause(pg)
    ta = pg.locator('textarea'); ta.click(); ta.type(MSG_HEAD, delay=60)
    pg.keyboard.insert_text(MSG[len(MSG_HEAD):]); pause(pg)   # remainder pasted so the payload is large enough to be statistically visible
    pg.locator('input[type=password]').first.click(); pg.locator('input[type=password]').first.type('demo-key-2026', delay=80); pause(pg)
    pg.screenshot(path=f'{OUT}/shot_1_studio_filled.png')
    pg.get_by_role('button', name='Encrypt & embed').click(); pg.get_by_text('PSNR').first.wait_for(); pause(pg, 1500)
    notes['studio_embed'] = pg.locator('.msg.ok').first.inner_text()
    pg.screenshot(path=f'{OUT}/shot_1_studio_embedded.png')
    with pg.expect_download() as d: pg.get_by_text('Download stego.png').click()
    d.value.save_as(OUT + '/sublumen-demo-stego.png'); pause(pg)
    # Extract
    pg.locator('input[type=file]').nth(1).set_input_files(OUT + '/sublumen-demo-stego.png'); pause(pg)
    xp = pg.locator('input[type=password]').nth(1); xp.click(); xp.type('wrong-key', delay=80); pause(pg, 600)
    pg.get_by_role('button', name='Extract', exact=True).click(); pg.locator('.msg.err').wait_for(); pause(pg, 1800)
    notes['extract_wrong'] = pg.locator('.msg.err').first.inner_text()
    pg.screenshot(path=f'{OUT}/shot_2_extract_wrong.png')
    xp.fill(''); xp.type('demo-key-2026', delay=80); pause(pg, 600)
    pg.get_by_role('button', name='Extract', exact=True).click(); pg.get_by_text('Message (1500 bytes)').wait_for(); pause(pg, 1800)
    notes['extract_ok'] = pg.locator('.msg.ok').last.inner_text()[:90]
    pg.screenshot(path=f'{OUT}/shot_2_extract_ok.png')
    # Cases + analyze stego
    pg.get_by_role('button', name='Cases & Evidence').click(); pause(pg)
    pg.get_by_placeholder('New case title').click(); pg.get_by_placeholder('New case title').type('Case: pier photo', delay=70); pause(pg, 600)
    pg.get_by_role('button', name='Create').click(); pg.get_by_text('Upload evidence').wait_for(); pause(pg)
    pg.locator('input[type=file]').set_input_files(OUT + '/sublumen-demo-stego.png'); pause(pg)
    pg.get_by_role('button', name='Upload & hash').click(); pg.get_by_role('button', name='Analyze').wait_for(); pause(pg, 1500)
    pg.get_by_role('button', name='Analyze').click(); pg.get_by_text('indicators only').wait_for(); pause(pg, 2000)
    notes['analysis_header'] = pg.get_by_text('indicators only').inner_text()
    ml = pg.locator('tr', has_text='ML model_v8_hgb'); notes['analysis_ml_row'] = ml.inner_text().replace('\t', ' | ')
    notes['analysis_rows'] = [r.replace('\t', ' | ') for r in pg.locator('table').nth(2).locator('tr').all_inner_texts()]
    notes['analysis_summary'] = pg.get_by_test_id('summary').inner_text().replace('\n', ' ')
    pg.mouse.wheel(0, 500); pause(pg, 800)
    pg.screenshot(path=f'{OUT}/shot_3_analysis.png')
    pg.mouse.wheel(0, -800); pause(pg, 600)
    pg.get_by_role('button', name='Generate PDF report').click(); pause(pg, 2000)
    with pg.expect_download() as d: pg.get_by_text('Download report.pdf').click()
    d.value.save_as(OUT + '/sublumen-demo-report.pdf'); pause(pg, 1200)
    pg.screenshot(path=f'{OUT}/shot_4_cases_report.png')
    # Visual lab
    pg.get_by_role('button', name='Visual Lab').click(); pause(pg)
    pg.get_by_role('button', name='Bit plane').click(); pg.locator('img.pv').wait_for(); pause(pg, 1800)
    pg.screenshot(path=f'{OUT}/shot_5_visual_bitplane.png')
    pg.get_by_role('button', name='Anomaly heatmap').click(); pause(pg, 2000)
    pg.screenshot(path=f'{OUT}/shot_5_visual_heatmap.png')
    # Compare
    pg.get_by_role('button', name='Compare').click(); pause(pg)
    pg.locator('input[type=file]').nth(0).set_input_files(COVER); pause(pg, 800)
    pg.locator('input[type=file]').nth(1).set_input_files(OUT + '/sublumen-demo-stego.png'); pause(pg, 800)
    pg.get_by_role('button', name='Compare', exact=True).nth(1).click(); pg.get_by_test_id('ssim-dash').wait_for(); pause(pg, 2500)
    notes['compare_dashboard'] = pg.get_by_test_id('ssim-dash').inner_text().replace('\n', ' ')
    pg.mouse.wheel(0, 450); pause(pg, 1500)
    pg.screenshot(path=f'{OUT}/shot_6_compare_ssim.png')
    pg.mouse.wheel(0, -900)
    # Models + Benchmark
    pg.get_by_role('button', name='Models').click(); pg.get_by_text('model_v7_svm_rbf').first.wait_for(); pause(pg, 1800)
    notes['models_v7_row'] = pg.locator('tr', has_text='model_v7_svm_rbf').first.inner_text().replace('\t', ' | ')
    notes['models_rows'] = [r.replace('\t', ' | ') for r in pg.locator('tr').all_inner_texts()][:14]
    pg.screenshot(path=f'{OUT}/shot_7_models.png')
    pg.get_by_role('button', name='Benchmark Lab').click(); pg.get_by_text('Benchmark #').first.wait_for(); pause(pg, 2500)
    notes['benchmark_heading'] = pg.get_by_text('Benchmark #').first.inner_text()
    notes['benchmark_rows_first_card'] = [r.replace('\t', ' | ') for r in pg.locator('table').first.locator('tr').all_inner_texts()]
    pg.screenshot(path=f'{OUT}/shot_8_benchmark.png')
    pg.mouse.wheel(0, 600); pause(pg, 1500)
    notes['page_errors'] = errs
    vpath = pg.video.path(); ctx.close(); b.close()
shutil.copy(vpath, OUT + '/sublumen-demo.webm')
json.dump(notes, open(OUT + '/notes.json', 'w'), indent=1, ensure_ascii=False); print(json.dumps(notes, indent=1, ensure_ascii=False))
