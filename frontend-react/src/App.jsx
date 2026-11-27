import React, { useEffect, useState } from 'react'
import { api, json, form, setToken, hasToken } from './api.js'

const Msg = ({ m }) => m ? <div className={'msg ' + (m.ok ? 'ok' : 'err')} role={m.ok ? 'status' : 'alert'}>{m.text}</div> : null
const Level = ({ l }) => <span className={'badge ' + l}>{String(l).toUpperCase()}</span>
const useMsg = () => { const [m, set] = useState(null); return [m, (text, ok) => set(text ? { text, ok } : null)] }

export function Login({ onDone }) {
  const [e, setE] = useState(''), [p, setP] = useState(''), [m, msg] = useMsg()
  const go = async () => {
    try {
      const j = await api('/auth/login', json('POST', { email: e, password: p }))
      setToken(j.token); localStorage.setItem('ss_u', `${j.email} (${j.role})`); onDone()
    } catch (x) { msg(x.message) }
  }
  return <main className="card" style={{ maxWidth: 380, marginTop: 60 }}><h1 style={{ fontSize: 20, margin: "0 0 12px" }}>Sign in</h1>
    <label>Email</label><input aria-label="Email" value={e} onChange={x => setE(x.target.value)} />
    <label>Password</label><input aria-label="Password" type="password" value={p} onChange={x => setP(x.target.value)} />
    <button className="pri" onClick={go}>Sign in</button><Msg m={m} /></main>
}

function Studio() {
  const [cover, setCover] = useState(), [text, setText] = useState(''), [pw, setPw] = useState(''), [keyed, setKeyed] = useState(false)
  const [eo, setEo] = useState(null), [em, emsg] = useMsg()
  const [img, setImg] = useState(), [xpw, setXpw] = useState(''), [xo, setXo] = useState(null), [xm, xmsg] = useMsg()
  const embed = async () => {
    if (!cover) return emsg('Choose a cover image')
    try { setEo(await api('/stego/embed?format=json' + (keyed ? '&keyed=1' : ''), { method: 'POST', body: form({ file: cover, message: text, password: pw }) })); emsg('') }
    catch (x) { setEo(null); emsg(x.message) }
  }
  const extract = async () => {
    if (!img) return xmsg('Choose an image')
    try { setXo(await api('/stego/extract', { method: 'POST', body: form({ file: img, password: xpw }) })); xmsg('') }
    catch (x) { setXo(null); xmsg(x.message) }
  }
  return <><div className="row">
    <div className="card"><h2>Hide a message</h2>
      <label>Cover image (PNG or BMP)</label><input type="file" aria-label="Cover image" accept=".png,.bmp" onChange={x => setCover(x.target.files[0])} />
      <label>Secret message</label><textarea aria-label="Secret message" rows="4" value={text} onChange={x => setText(x.target.value)} />
      <label>Password (never stored, never logged)</label><input aria-label="Embedding password" type="password" value={pw} onChange={x => setPw(x.target.value)} />
      <label><input type="checkbox" style={{ width: 'auto' }} checked={keyed} onChange={x => setKeyed(x.target.checked)} /> Keyed order (spreads changes over the whole image)</label>
      <button className="pri" onClick={embed}>Encrypt &amp; embed</button><Msg m={em} />
      {eo && <><div className="msg ok">PSNR {eo.psnr_db.toFixed(2)} dB, SSIM {eo.ssim.toFixed(4)}, payload {(eo.payload_rate * 100).toFixed(1)}% of capacity ({eo.capacity_bytes} bytes max)</div>
        <p><a download="stego.png" href={'data:image/png;base64,' + eo.stego_png_base64}>Download stego.png</a></p></>}
    </div>
    <div className="card"><h2>Extract a message</h2>
      <label>Stego image</label><input type="file" aria-label="Stego image" accept=".png,.bmp" onChange={x => setImg(x.target.files[0])} />
      <label>Password</label><input aria-label="Extraction password" type="password" value={xpw} onChange={x => setXpw(x.target.value)} />
      <button className="pri" onClick={extract}>Extract</button><Msg m={xm} />
      {xo && <div className="msg ok">Message ({xo.bytes} bytes):<br /><b>{xo.message}</b></div>}
    </div></div>
    <div className="limits">Share the stego image as-is. JPEG conversion, resizing or screenshots destroy the hidden data.</div></>
}

const EXPLAIN = {
  chi_square: ['Chi-square test', 'Checks whether pairs of neighbouring pixel values are suspiciously equal in count, a classic trace of sequential LSB replacement. Weak against +-1 matching and random placement.'],
  rs_estimate: ['RS analysis', 'Estimates what fraction of the LSB capacity was overwritten by comparing how smooth pixel groups become when bits are flipped. Noisy on small images.'],
  lsb_stream_randomness: ['LSB randomness', 'Compares the least significant bits of neighbouring samples. Natural photos keep some structure there; an embedded encrypted message looks random.'],
  lsb_entropy: ['LSB entropy', 'Information content of the least significant bit plane. Context only: many clean images are already close to 1.'],
  lsb_ratio: ['LSB ones ratio', 'Share of 1 bits in the LSB plane. A value near 0.5 is normal for photos and for embedded data alike.'],
  adjacent_correlation: ['Neighbour correlation', 'How alike adjacent pixels are. Embedding adds noise and lowers it, but so do textured photos.'],
}
function Gauge({ score, lvl }) {
  const R = 44, C = 2 * Math.PI * R, v = Math.min(1, Math.max(0, score ?? 0)), col = { high: 'var(--bad)', medium: 'var(--warn)', low: 'var(--ok)' }[lvl] || 'var(--line)'
  return <div className="gauge" data-level={lvl} role="img" aria-label={score == null ? 'No model score' : `Model score ${score.toFixed(2)} of 1, level ${lvl}`}>
    <svg viewBox="0 0 104 104" aria-hidden="true"><circle cx="52" cy="52" r={R} fill="none" stroke="var(--line)" strokeWidth="8" />
      {score != null && <circle cx="52" cy="52" r={R} fill="none" stroke={col} strokeWidth="8" strokeLinecap="round" strokeDasharray={`${C * v * 0.999} ${C}`} transform="rotate(-90 52 52)" />}
      <line x1="52" y1="3" x2="52" y2="13" stroke="var(--fg)" strokeWidth="2" transform="rotate(180 52 52)" /></svg>
    <b>{score != null ? score.toFixed(2) : '-'}</b><span>model score</span></div>
}
function Overlay({ evId }) {
  const [o, setO] = useState(null)
  useEffect(() => { let u; let live = true
    api(`/evidence/${evId}/visual/overlay`).then(async r => { const bl = await r.blob(); if (live) { u = URL.createObjectURL(bl); setO({ url: u, cap: r.headers.get('X-Visual-Caption') }) } }).catch(() => {})
    return () => { live = false; u && URL.revokeObjectURL(u) } }, [evId])
  if (!o) return null
  return <figure className="ovl"><img className="pv" src={o.url} alt="Evidence image with model evidence overlay: amber tiles carry more model evidence" /><figcaption className="cap">{o.cap}</figcaption></figure>
}

function Analysis({ r }) {
  const lvl = r.ml ? r.ml.level : 'unknown'
  const words = { high: 'Strong indicators of hidden data. Treat as a lead to verify, not proof.', medium: 'Some indicators are raised. Inconclusive on its own.', low: 'No strong indicators. This does not prove the image is clean: other methods and low payloads can go undetected.', unknown: 'No model score for this run.' }
  return <div className="card"><div className="summary" data-testid="summary"><Gauge score={r.ml ? r.ml.score : null} lvl={lvl} />
      <div><Level l={lvl} /> <span className="cap">{r.model}</span><p>{words[lvl]}</p>{r.ml && r.ml.tiles && <p className="cap">Scored on {r.ml.tiles} image tile{r.ml.tiles > 1 ? 's' : ''}. 0.5 is the validation threshold.</p>}</div></div>
    {r.ml && r.evidence_id && <Overlay evId={r.evidence_id} />}
    <h2>Analysis #{r.run_id} <small className="cap">no verdict: indicators only (model {r.model})</small></h2>
    <table><thead><tr><th>Indicator</th><th>Value</th><th>Level</th><th>Note</th></tr></thead><tbody>
      {r.indicators.map(i => <tr key={i.name}><td>{i.name}{EXPLAIN[i.name] && <details className="why"><summary>What is this?</summary><span className="cap"><b>{EXPLAIN[i.name][0]}.</b> {EXPLAIN[i.name][1]}</span></details>}</td><td>{i.value ?? '-'}</td><td><Level l={i.level} /></td><td className="cap">{i.note}</td></tr>)}
      {r.ml && <tr><td>ML {r.ml.model} ({r.ml.algo})</td><td>{r.ml.score.toFixed(3)}</td><td><Level l={r.ml.level} /></td><td className="cap">{r.ml.note}</td></tr>}
    </tbody></table>
    {r.provenance && <div className="cap">Provenance (C2PA): {r.provenance.note}</div>}
    {r.warnings.map(w => <div className="msg err" key={w}>{w}</div>)}
    <div className="limits"><b>Limitations</b><ul>{r.limitations.map(l => <li key={l}>{l}</li>)}</ul></div></div>
}

function Cases({ setEv }) {
  const [cases, setCases] = useState([]), [cur, setCur] = useState(null), [detail, setDetail] = useState(null)
  const [title, setTitle] = useState(''), [m, msg] = useMsg(), [res, setRes] = useState(null), [file, setFile] = useState(), [audit, setAudit] = useState(null)
  const load = async () => setCases((await api('/cases')).cases)
  useEffect(() => { load() }, [])
  useEffect(() => { if (cur) api('/cases/' + cur).then(setDetail) }, [cur])
  const create = async () => { try { const j = await api('/cases', json('POST', { title })); await load(); setCur(j.id) } catch (x) { msg(x.message) } }
  const upload = async () => {
    if (!file) return msg('Choose a file')
    try { const j = await api('/evidence', { method: 'POST', body: form({ case_id: cur, file }) }); setEv(j.id); setDetail(await api('/cases/' + cur)); msg(j.warning || 'Uploaded and hashed', true) }
    catch (x) { msg(x.message) }
  }
  const analyze = async id => { setEv(id); try { setRes(await api('/analyses', json('POST', { evidence_id: id }))) } catch (x) { msg(x.message) } }
  const report = async () => {
    try { const j = await api('/reports', json('POST', { case_id: cur })); const r = await api(j.download.replace(/^\/api/, '')); const u = URL.createObjectURL(await r.blob())
      msg('Report ready. PDF SHA-256 ' + j.pdf_sha256, true); setRes({ pdf: u }) } catch (x) { msg(x.message) }
  }
  const demo = async () => {
    try {
      msg('Building the demo case: embed, upload, analyze...', true)
      const cover = new File([await (await fetch('/static/demo-cover.png')).blob()], 'pier-photo-cover.png', { type: 'image/png' })
      const e = await api('/stego/embed?format=json', { method: 'POST', body: form({ file: cover, message: 'Meet at the old pier at midnight. Bring the drive. '.repeat(30), password: 'demo-key-2026' }) })
      const bin = atob(e.stego_png_base64); const u8 = Uint8Array.from(bin, c => c.charCodeAt(0))
      const stego = new File([u8], 'pier-photo-stego.png', { type: 'image/png' })
      const c = await api('/cases', json('POST', { title: 'Demo: suspicious pier photo' })); await load(); setCur(c.id)
      await api('/evidence', { method: 'POST', body: form({ case_id: c.id, file: cover }) })
      const ev = await api('/evidence', { method: 'POST', body: form({ case_id: c.id, file: stego }) })
      setDetail(await api('/cases/' + c.id)); await analyze(ev.id); msg('Demo case ready: the cover and a stego copy are uploaded; the stego copy was analyzed (key: demo-key-2026).', true)
    } catch (x) { msg(x.message) }
  }
  return <div className="row">
    <div className="card" style={{ flex: '0 0 300px' }}><h2>Cases</h2>
      {!cases.length && <div className="empty">No cases yet. Create one, or <button className="sec" onClick={demo}>load the demo case</button></div>}
      <input aria-label="New case title" placeholder="New case title" value={title} onChange={x => setTitle(x.target.value)} /><button className="pri" onClick={create}>Create</button>
      <table><tbody>{cases.map(c => <tr key={c.id}><td><a href="#" onClick={e => { e.preventDefault(); setCur(c.id); setRes(null) }}>{c.case_code}</a></td><td>{c.title}</td></tr>)}</tbody></table></div>
    <div style={{ flex: 2 }}>{!detail && <div className="card empty">Select or create a case to upload evidence, run analyses and generate the PDF report.<Msg m={m} /></div>}{detail && <div className="card"><h2>{detail.case_code}: {detail.title}</h2>
      <label>Upload evidence (PNG/BMP/JPEG)</label><input type="file" aria-label="Evidence file" onChange={x => setFile(x.target.files[0])} />
      <button className="pri" onClick={upload}>Upload &amp; hash</button> <button className="sec" onClick={report}>Generate PDF report</button> <button className="sec" onClick={async () => setAudit((await api(`/cases/${cur}/audit`)).events)}>Audit trail</button>
      <Msg m={m} />
      {!detail.evidence.length && <div className="empty">No evidence yet. Upload a PNG, BMP or JPEG: it is hashed (SHA-256) at intake and stored read-only.</div>}<table><thead><tr><th>ID</th><th>File</th><th>SHA-256</th><th><span className="sr">Actions</span></th></tr></thead><tbody>{detail.evidence.map(e => <tr key={e.id}><td>{e.id}</td><td>{e.name}<br /><span className="cap">{e.format} {e.width}x{e.height}</span></td><td className="mono">{e.sha256.slice(0, 24)}...</td><td><button className="sec" onClick={() => analyze(e.id)}>Analyze</button></td></tr>)}</tbody></table>
      {audit && <table><tbody>{audit.map(a => <tr key={a.id}><td>{a.timestamp}</td><td>{a.action}</td></tr>)}</tbody></table>}</div>}
      {res && res.pdf && <a download="report.pdf" href={res.pdf}>Download report.pdf</a>}
      {res && res.run_id && <Analysis r={res} />}</div></div>
}

function Visual({ ev }) {
  const [id, setId] = useState(ev || ''), [plane, setPlane] = useState(0), [ch, setCh] = useState(0), [out, setOut] = useState(null), [m, msg] = useMsg()
  const go = async kind => {
    try { const q = kind === 'bitplane' ? `?plane=${plane}&channel=${ch}` : ''; const r = await api(`/evidence/${id}/visual/${kind}${q}`)
      setOut({ url: URL.createObjectURL(await r.blob()), cap: r.headers.get('X-Visual-Caption') }); msg('') } catch (x) { msg(x.message) }
  }
  return <div className="card"><h2>Visual Investigation Lab</h2><label>Evidence ID</label><input aria-label="Evidence ID" value={id} onChange={x => setId(x.target.value)} />
    <div className="row"><div><label>Bit plane (0=LSB..7)</label><input aria-label="Bit plane" type="number" min="0" max="7" value={plane} onChange={x => setPlane(x.target.value)} /></div>
      <div><label>Channel (0=R,1=G,2=B)</label><input aria-label="Channel" type="number" min="0" max="2" value={ch} onChange={x => setCh(x.target.value)} /></div></div>
    <button className="pri" onClick={() => go('bitplane')}>Bit plane</button> <button className="pri" onClick={() => go('heatmap')}>Anomaly heatmap</button> <button className="pri" onClick={() => go('overlay')}>Model overlay</button><Msg m={m} />
    {out && <><img className="pv" src={out.url} alt="visual" /><div className="cap">{out.cap}</div></>}</div>
}

function Compare() {
  const [a, setA] = useState(), [b, setB] = useState(), [r, setR] = useState(null), [m, msg] = useMsg()
  const go = async () => { try { setR(await api('/compare?diffmap=1', { method: 'POST', body: form({ a, b }) })); msg('') } catch (x) { msg(x.message) } }
  return <div className="card"><h2>Compare two images</h2><div className="row"><div><label>Image A</label><input aria-label="Image A" type="file" onChange={x => setA(x.target.files[0])} /></div><div><label>Image B</label><input aria-label="Image B" type="file" onChange={x => setB(x.target.files[0])} /></div></div>
    <button className="pri" onClick={go}>Compare</button><Msg m={m} />
    {r && <><table><tbody><tr><td>Identical bytes</td><td>{String(r.identical_bytes)}</td></tr><tr><td>SHA-256 A</td><td className="mono">{r.sha256_a}</td></tr><tr><td>SHA-256 B</td><td className="mono">{r.sha256_b}</td></tr><tr><td>Differing pixels</td><td>{r.diff_pixels ?? 'n/a'}</td></tr></tbody></table>
      {r.ssim != null && <div className="kpis" data-testid="ssim-dash"><div className="kpi"><span>SSIM (mean)</span><b>{r.ssim.toFixed(5)}</b></div><div className="kpi"><span>SSIM (worst window)</span><b>{r.ssim_min.toFixed(4)}</b></div><div className="kpi"><span>PSNR</span><b>{r.psnr_db ? r.psnr_db.toFixed(2) + ' dB' : 'identical'}</b></div><div className="kpi"><span>MSE</span><b>{r.mse.toFixed(4)}</b></div><div className="kpi"><span>Max pixel change</span><b>{r.max_abs_diff}</b></div><div className="kpi"><span>Changed R / G / B</span><b>{r.changed_by_channel.join(' / ')}</b></div></div>}
      {r.diff_map_png_base64 && <><img className="pv" alt="diff" src={'data:image/png;base64,' + r.diff_map_png_base64} /><div className="cap">{r.diff_map_caption}</div></>}
      {r.ssim_map_png_base64 && <><img className="pv" alt="ssim map" src={'data:image/png;base64,' + r.ssim_map_png_base64} /><div className="cap">{r.ssim_map_caption}</div></>}</>}</div>
}

function Models() {
  const [ms, setMs] = useState(null)
  useEffect(() => { api('/models').then(j => setMs(j.models)) }, [])
  if (!ms) return <div className="card">Loading...</div>
  return <div className="card"><h2>Registered models (held-out test metrics recorded at training)</h2>
    <table><thead><tr><th>Name</th><th>Algo</th><th>Acc</th><th>Recall</th><th>FPR</th><th>Precision</th><th>F1</th></tr></thead><tbody>
      {ms.map(m => { const t = m.metrics.test[m.algo] || {}; const f = k => t[k] == null ? '-' : t[k].toFixed(3)
        return <tr key={m.name}><td>{m.name}</td><td>{m.algo}</td><td>{f('accuracy')}</td><td>{f('recall')}</td><td>{f('fpr')}</td><td>{f('precision')}</td><td>{f('f1')}</td></tr> })}
    </tbody></table><div className="limits"><b>v8 (default):</b> gradient boosting on 137 LSB/SPAM features plus 700 SRM-lite residual co-occurrence features, scored on up to 8 tiles of 128px. Locked test (photos never used for training or threshold choice; Flowers and Kodak are families unseen in training), v7 to v8 AUC: 0.88 to 0.995 flowers, 0.77 to 0.996 Kodak, 0.75 to 0.989 pets. Clean false alarms 5.0% / 2.3% / 6.0%; LSB matching at 10% payload recall 0.87-0.93. JPEG-recompressed stego is still mostly missed (about 7%); third-party tools are not tested. See docs/locked_eval_v8.json.<br /><br />v7 (previous default): same features as v6 (12 LSB statistics + 125 SPAM residuals, RBF-SVM), trained on Imagenette 160px crops, 128px crops of full-size decoded JPEG photos and synthetic covers; threshold set on validation data (5% false-alarm target). Its row above is scored on a pooled, harder test (full-size crops included, JPEG-recompressed stego included), so its accuracy and recall are not comparable with older rows. Held-out clean-PNG false alarms: 1.6% on Imagenette-160 crops, 7.5% (95% CI 5.5-9.7) on full-size photo crops (v6: 28.7%). On 3 extra photos about 17% (one of them 42%). LSB matching recall at 50% payload: 55-62%. Stego recompressed as JPEG is mostly missed (recall 6-16%). Not validated on BOSSBase or camera RAW. See Benchmark Lab and docs/benchmark_v7.json.</div></div>
}

function Bench() {
  const [bs, setBs] = useState(null)
  useEffect(() => { api('/benchmarks').then(j => setBs(j.benchmarks)) }, [])
  if (!bs) return <div className="card">Loading...</div>
  if (!bs.length) return <div className="card">No benchmark recorded yet.</div>
  const pct = v => (v.value * 100).toFixed(1) + '% [' + (v.ci95[0] * 100).toFixed(1) + '-' + (v.ci95[1] * 100).toFixed(1) + ']'
  const lab = k => k.replace('recall|', 'recall ').replace(/\|/g, ' ').replace('fpr_png_all', 'false alarms, clean PNG (all)').replace('fpr_png_real_photos', 'false alarms, clean real photos').replace('fpr_jpeg95_covers', 'false alarms, clean JPEG q95')
  return <>{bs.map(b => { const r = b.result; if (r.meta.models) { const ds = Object.keys(r.detectors); const keys = Object.keys(r.detectors[ds[0]]).sort()
    return <div className="card" key={b.id}><h2>Benchmark #{b.id}: v7 vs v6, v5 and rule baselines (seed {r.meta.seed}, {r.meta.n_test_covers} held-out clean PNG covers across 2 sets, source-photo-disjoint)</h2>
      <p className="muted">Each cell: rate % [95% CI, cluster bootstrap over covers, {r.meta.bootstrap} resamples]. Lower is better for false alarms; higher for recall.</p>
      <table><thead><tr><th>Measure</th>{ds.map(d => <th key={d}>{d}</th>)}</tr></thead><tbody>
        {keys.map(k => <tr key={k}><td>{lab(k)}</td>{ds.map(d => <td key={d}>{pct(r.detectors[d][k])}</td>)}</tr>)}
      </tbody></table><div className="limits">{r.meta.notes.join(' ')}</div></div> }
    return <div className="card" key={b.id}><h2>Benchmark #{b.id} (model {r.meta.model}, seed {r.meta.seed}, {r.meta.n_covers} held-out covers)</h2>
    <table><thead><tr><th>Detector</th><th>Embedder</th><th>Recall</th><th>FPR</th><th>F1</th></tr></thead><tbody>
      {Object.entries(r.detectors).flatMap(([d, e]) => Object.entries(e).map(([k, v]) => <tr key={d + k}><td>{d}</td><td>{k}</td><td>{(v.recall * 100).toFixed(1)}%</td><td>{(v.fpr * 100).toFixed(1)}%</td><td>{v.f1.toFixed(3)}</td></tr>))}
    </tbody></table><div className="limits">{r.meta.notes.join(' ')}</div></div> })}</>
}

const applyTheme = t => { document.documentElement.dataset.theme = t }
const toggleTheme = () => { const t = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light'; localStorage.setItem('ss_theme', t); applyTheme(t) }
applyTheme(localStorage.getItem('ss_theme') || (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'))
const TABS = { studio: 'Stego Studio', cases: 'Cases & Evidence', visual: 'Visual Lab', compare: 'Compare', models: 'Models', bench: 'Benchmark Lab' }
export default function App() {
  const [auth, setAuth] = useState(hasToken()), [tab, setTab] = useState('studio'), [ev, setEv] = useState('')
  if (!auth) return <Login onDone={() => setAuth(true)} />
  return <><a className="skip" href="#main">Skip to content</a><header><img src="/static/sublumen-mark-for-dark-bg.svg" alt="Sublumen logo" /><h1><span className="sub">sub</span>lumen</h1><small>Find what the pixels hide.</small><span className="sp" />
    <span className="who">{localStorage.getItem('ss_u')}</span><button className="sec" aria-label="Toggle theme" onClick={toggleTheme}>Light/Dark</button><button className="sec" onClick={() => { setToken(null); setAuth(false) }}>Log out</button></header>
    <nav aria-label="Sections">{Object.entries(TABS).map(([k, v]) => <button key={k} aria-current={tab === k ? 'page' : undefined} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{v}</button>)}</nav>
    <main id="main">{tab === 'studio' && <Studio />}{tab === 'cases' && <Cases setEv={setEv} />}{tab === 'visual' && <Visual key={ev} ev={ev} />}
      {tab === 'compare' && <Compare />}{tab === 'models' && <Models />}{tab === 'bench' && <Bench />}</main></>
}
