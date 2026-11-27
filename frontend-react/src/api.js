let token = localStorage.getItem('ss_t')
export const setToken = t => { token = t; t ? localStorage.setItem('ss_t', t) : localStorage.clear() }
export const hasToken = () => !!token
export async function api(path, opt = {}) {
  opt.headers = { ...(opt.headers || {}), ...(token ? { Authorization: 'Bearer ' + token } : {}) }
  const r = await fetch('/api' + path, opt)
  const ct = r.headers.get('content-type') || ''
  if (ct.includes('json')) {
    const j = await r.json()
    if (j.status === 'error') throw Object.assign(new Error(j.message), { code: j.code })
    return j
  }
  if (!r.ok) throw new Error('Request failed')
  return r
}
export const json = (method, body) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
export const form = o => { const f = new FormData(); Object.entries(o).forEach(([k, v]) => f.append(k, v)); return f }
