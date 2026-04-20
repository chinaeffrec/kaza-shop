const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'
// Note: FastAPI routes are /catalog/..., /products/..., /orders/... (no /api prefix)

async function req(method, path, body, isFormData = false) {
  const opts = { method, headers: {} }
  if (body) {
    if (isFormData) {
      opts.body = body
    } else {
      opts.headers['Content-Type'] = 'application/json'
      opts.body = JSON.stringify(body)
    }
  }
  const res = await fetch(`${BASE}${path}`, opts)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }
  return res.json()
}

export const api = {
  // Catalog
  getCategories: () => req('GET', '/catalog/categories'),
  getSubcategories: (catId) => req('GET', `/catalog/categories/${catId}/subcategories`),

  // Products
  getProducts: () => req('GET', '/products/'),
  getProduct: (id) => req('GET', `/products/${id}`),
  createProduct: (data) => req('POST', '/products/', data),
  updateProduct: (id, data) => req('PATCH', `/products/${id}`, data),
  deleteProduct: (id) => req('DELETE', `/products/${id}`),
  uploadPhoto: (id, file) => {
    const fd = new FormData()
    fd.append('file', file)
    return req('POST', `/products/${id}/photo`, fd, true)
  },
  deletePhoto: (id) => req('DELETE', `/products/${id}/photo`),

  // Import
  importXlsx: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return req('POST', '/import/products', fd, true)
  },

  // Orders
  getOrders: (status) => req('GET', `/orders/${status ? `?status=${status}` : ''}`),
  getOrder: (id) => req('GET', `/orders/${id}`),
  updateOrderStatus: (id, status, comment) =>
    req('PATCH', `/orders/${id}/status`, { status, comment }),
}
