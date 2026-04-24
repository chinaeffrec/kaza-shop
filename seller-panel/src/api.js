const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function buildQuery(params) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      query.set(key, value)
    }
  })
  const qs = query.toString()
  return qs ? `?${qs}` : ''
}

async function req(method, path, body, isFormData = false) {
  const opts = { method, headers: {} }
  const token = localStorage.getItem('admin_token')
  if (token) opts.headers['Authorization'] = `Bearer ${token}`

  if (body) {
    if (isFormData) { opts.body = body }
    else { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body) }
  }
  const res = await fetch(`${BASE}${path}`, opts)
  if (res.status === 401) {
    localStorage.removeItem('admin_token')
    window.location.reload()
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }
  return res.json()
}

async function downloadFile(path, fallbackName) {
  const token = localStorage.getItem('admin_token')
  const res = await fetch(`${BASE}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (res.status === 401) {
    localStorage.removeItem('admin_token')
    window.location.reload()
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Download failed')
  }

  const blob = await res.blob()
  const contentDisposition = res.headers.get('content-disposition') || ''
  const matchedName = contentDisposition.match(/filename="?([^"]+)"?/)
  const filename = matchedName?.[1] || fallbackName

  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

export const api = {
  BASE,
  // Auth
  login:  (login, password) => req('POST', '/auth/login', { login, password }),
  me:     () => req('GET', '/auth/me'),
  updateCredentials: (d) => req('PATCH', '/auth/credentials', d),
  // Catalog
  getCategories:    () => req('GET', '/catalog/categories'),
  getSubcategories: (id) => req('GET', `/catalog/categories/${id}/subcategories`),
  reloadCache:      () => fetch(`${BASE}/catalog/cache/reload`, { method: 'POST', headers: { Authorization: `Bearer ${localStorage.getItem('admin_token')}` } }).then(r => r.json()),
  // Products
  getProducts:   () => req('GET', '/products/'),
  getProduct:    (id) => req('GET', `/products/${id}`),
  createProduct: (d) => req('POST', '/products/', d),
  updateProduct: (id, d) => req('PATCH', `/products/${id}`, d),
  deleteProduct: (id) => req('DELETE', `/products/${id}`),
  uploadPhoto: (id, file) => {
    const fd = new FormData(); fd.append('file', file)
    return req('POST', `/products/${id}/photo`, fd, true)
  },
  deletePhoto: (id) => req('DELETE', `/products/${id}/photo`),
  toggleActive: (id, is_active) => req('PATCH', `/products/${id}`, { is_active }),
  // Import
  importXlsx: (file) => {
    const fd = new FormData(); fd.append('file', file)
    return req('POST', '/import/products', fd, true)
  },
  // Orders
  getOrders:        (status) => req('GET', `/orders/${buildQuery({ status })}`),
  getOrder:         (id) => req('GET', `/orders/${id}`),
  getOrderStatuses: () => req('GET', '/orders/statuses'),
  updateOrderStatus:(id, status, comment) => req('PATCH', `/orders/${id}/status`, { status, comment }),
  // Stats
  getDashboard: (from, to) => req('GET', `/stats/dashboard${buildQuery({ date_from: from, date_to: to })}`),
  getStats:     (from, to) => req('GET', `/stats/products${buildQuery({ date_from: from, date_to: to })}`),
  trackReturn:  (pid) => req('POST', `/stats/products/${pid}/return`),
  // Settings
  getSettings:    () => req('GET', '/settings/'),
  updateSettings: (d) => req('PATCH', '/settings/', d),
  downloadLogs:   () => downloadFile('/settings/logs/download', 'kaza-shop-logs.zip'),
  // FAQ
  getFaq:    () => req('GET', '/faq/'),
  createFaq: (d) => req('POST', '/faq/', d),
  updateFaq: (id, d) => req('PATCH', `/faq/${id}`, d),
  deleteFaq: (id) => req('DELETE', `/faq/${id}`),
}
