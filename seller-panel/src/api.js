const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function req(method, path, body, isFormData = false) {
  const opts = { method, headers: {} }
  if (body) {
    if (isFormData) { opts.body = body }
    else { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body) }
  }
  const res = await fetch(`${BASE}${path}`, opts)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }
  return res.json()
}

export const api = {
  BASE,
  getCategories:     () => req('GET', '/catalog/categories'),
  getSubcategories:  (id) => req('GET', `/catalog/categories/${id}/subcategories`),
  getProducts:       () => req('GET', '/products/'),
  getProduct:        (id) => req('GET', `/products/${id}`),
  createProduct:     (d) => req('POST', '/products/', d),
  updateProduct:     (id, d) => req('PATCH', `/products/${id}`, d),
  deleteProduct:     (id) => req('DELETE', `/products/${id}`),
  uploadPhoto: (id, file) => { const fd = new FormData(); fd.append('file', file); return req('POST', `/products/${id}/photo`, fd, true) },
  deletePhoto:       (id) => req('DELETE', `/products/${id}/photo`),
  importXlsx: (file) => { const fd = new FormData(); fd.append('file', file); return req('POST', '/import/products', fd, true) },
  getOrders:         (status) => req('GET', `/orders/${status ? `?status=${status}` : ''}`),
  getOrder:          (id) => req('GET', `/orders/${id}`),
  getOrderStatuses:  () => req('GET', '/orders/statuses'),
  updateOrderStatus: (id, status, comment) => req('PATCH', `/orders/${id}/status`, { status, comment }),
  getConversations:  () => req('GET', '/messages/conversations'),
  getConversation:   (uid) => req('GET', `/messages/${uid}`),
  sendMessage: (uid, text) => req('POST', '/messages/send-to-user', { user_id: uid, text, direction: 'out' }),
  deleteConversation:(uid) => req('DELETE', `/messages/${uid}`),
  getReviews:        () => req('GET', '/reviews/'),
  getProductReviews: (pid) => req('GET', `/reviews/product/${pid}`),
  toggleReview:      (id, is_visible) => req('PATCH', `/reviews/${id}/visibility`, { is_visible }),
  getStats:          (from, to) => req('GET', `/stats/products${from ? `?date_from=${from}&date_to=${to}` : ''}`),
  trackReturn:       (pid) => req('POST', `/stats/products/${pid}/return`),
  getSettings:       () => req('GET', '/settings/'),
  updateSettings:    (d) => req('PATCH', '/settings/', d),
  uploadLogo:  (file) => { const fd = new FormData(); fd.append('file', file); return req('POST', '/settings/logo', fd, true) },
  deleteLogo:        () => req('DELETE', '/settings/logo'),
  getFaq:            () => req('GET', '/faq/'),
  createFaq:         (d) => req('POST', '/faq/', d),
  updateFaq:         (id, d) => req('PATCH', `/faq/${id}`, d),
  deleteFaq:         (id) => req('DELETE', `/faq/${id}`),
}
