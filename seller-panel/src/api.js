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

function uploadFile(path, file) {
  const fd = new FormData()
  fd.append('file', file)
  return req('POST', path, fd, true)
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
  reloadCache:      () => req('POST', '/catalog/cache/reload'),

  // Products
  getProducts:      (page = 1, perPage = 20) => req('GET', `/products/${buildQuery({ page, per_page: perPage })}`),
  getProduct:       (id) => req('GET', `/products/${id}`),
  createProduct:    (d) => req('POST', '/products/', d),
  updateProduct:    (id, d) => req('PATCH', `/products/${id}`, d),
  deleteProduct:    (id) => req('DELETE', `/products/${id}`),
  uploadPhoto:      (id, file) => uploadFile(`/products/${id}/photo`, file),
  deletePhoto:      (id) => req('DELETE', `/products/${id}/photo`),
  uploadPhotoSlot:  (id, slot, file) => uploadFile(`/products/${id}/photo/${slot}`, file),
  deletePhotoSlot:  (id, slot) => req('DELETE', `/products/${id}/photo/${slot}`),
  toggleActive:     (id, is_active) => req('PATCH', `/products/${id}`, { is_active }),

  // Import
  importXlsx: (file) => uploadFile('/import/products', file),

  // Orders
  getOrders:        (status, page = 1, perPage = 20) => req('GET', `/orders/${buildQuery({ status, page, per_page: perPage })}`),
  getOrder:         (id) => req('GET', `/orders/${id}`),
  getOrderStatuses: () => req('GET', '/orders/statuses'),
  updateOrderStatus:(id, status, comment) => req('PATCH', `/orders/${id}/status`, { status, comment }),
  generateReceipt:  (id) => req('POST', `/orders/${id}/receipt`),

  // Stats
  getDashboard: (from, to) => req('GET', `/stats/dashboard${buildQuery({ date_from: from, date_to: to })}`),
  getStats:     (from, to) => req('GET', `/stats/products${buildQuery({ date_from: from, date_to: to })}`),
  trackReturn:  (pid) => req('POST', `/stats/products/${pid}/return`),

  exportDashboard: (from, to) => {
    const token = localStorage.getItem('admin_token')
    const qs = buildQuery({ date_from: from || null, date_to: to || null })
    const url = `${BASE}/stats/dashboard/export${qs}`
    return fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then(r => {
        if (!r.ok) throw new Error('Export failed')
        return r.blob()
      })
      .then(blob => {
        const a = document.createElement('a')
        a.href = URL.createObjectURL(blob)
        a.download = `stats_orders.xlsx`
        a.click()
        URL.revokeObjectURL(a.href)
      })
  },

  exportStats: (from, to) => {
    const token = localStorage.getItem('admin_token')
    const qs = buildQuery({ date_from: from || null, date_to: to || null })
    const url = `${BASE}/stats/products/export${qs}`
    return fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then(r => {
        if (!r.ok) throw new Error('Export failed')
        return r.blob()
      })
      .then(blob => {
        const a = document.createElement('a')
        a.href = URL.createObjectURL(blob)
        a.download = `stats_products.xlsx`
        a.click()
        URL.revokeObjectURL(a.href)
      })
  },

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