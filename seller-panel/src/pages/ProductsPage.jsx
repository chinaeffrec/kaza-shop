import { useState, useEffect, useCallback } from 'react'
import { api } from '../api.js'
import s from './ProductsPage.module.css'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const EMPTY = { name: '', price: '', subcategory_id: '', description: '', characteristics: '', is_active: true }

export default function ProductsPage() {
  const [products, setProducts]       = useState([])
  const [categories, setCategories]   = useState([])
  const [subcats, setSubcats]         = useState([])
  const [loading, setLoading]         = useState(true)
  const [error, setError]             = useState(null)
  const [modal, setModal]             = useState(null)   // null | 'add' | product object
  const [form, setForm]               = useState(EMPTY)
  const [saving, setSaving]           = useState(false)
  const [photoFile, setPhotoFile]     = useState(null)
  const [catFilter, setCatFilter]     = useState('')
  const [search, setSearch]           = useState('')

  const load = useCallback(async () => {
    try {
      setLoading(true)
      const [prods, cats] = await Promise.all([api.getProducts(), api.getCategories()])
      setProducts(prods)
      setCategories(cats)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  // Загружаем подкатегории при выборе категории в форме
  useEffect(() => {
    if (!form._cat_id) { setSubcats([]); return }
    api.getSubcategories(form._cat_id).then(setSubcats).catch(() => setSubcats([]))
  }, [form._cat_id])

  function openAdd() {
    setForm(EMPTY)
    setPhotoFile(null)
    setModal('add')
  }

  function openEdit(p) {
    setForm({
      name: p.name, price: String(p.price),
      subcategory_id: String(p.subcategory_id),
      description: p.description || '',
      characteristics: p.characteristics || '',
      is_active: p.is_active,
      _cat_id: '',
    })
    setPhotoFile(null)
    setModal(p)
  }

  async function handleSave() {
    setSaving(true)
    try {
      const payload = {
        name: form.name,
        price: parseInt(form.price),
        subcategory_id: parseInt(form.subcategory_id),
        description: form.description || null,
        characteristics: form.characteristics || null,
        is_active: form.is_active,
      }

      let saved
      if (modal === 'add') {
        saved = await api.createProduct(payload)
      } else {
        saved = await api.updateProduct(modal.id, payload)
      }

      if (photoFile) {
        await api.uploadPhoto(saved.id, photoFile)
      }

      setModal(null)
      await load()
    } catch (e) {
      alert('Ошибка: ' + e.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(id) {
    if (!confirm('Удалить товар?')) return
    await api.deleteProduct(id).catch(e => alert(e.message))
    await load()
  }

  async function handleDeletePhoto(id) {
    await api.deletePhoto(id).catch(e => alert(e.message))
    await load()
  }

  const visible = products.filter(p => {
    const matchCat = !catFilter || String(p.subcategory_id) === catFilter
    const matchSearch = !search || p.name.toLowerCase().includes(search.toLowerCase())
    return matchCat && matchSearch
  })

  if (loading) return <p className={s.msg}>Загрузка...</p>
  if (error)   return <p className={s.msg} style={{ color: 'red' }}>Ошибка: {error}</p>

  return (
    <div>
      <div className={s.toolbar}>
        <h1 className={s.title}>Товары <span className={s.count}>{products.length}</span></h1>
        <button className={s.btnAdd} onClick={openAdd}>+ Добавить</button>
      </div>

      <div className={s.filters}>
        <input
          className={s.search}
          placeholder="Поиск по названию..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      {visible.length === 0
        ? <p className={s.msg}>Товары не найдены</p>
        : (
          <table className={s.table}>
            <thead>
              <tr>
                <th>Фото</th>
                <th>Название</th>
                <th>Цена</th>
                <th>Активен</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {visible.map(p => (
                <tr key={p.id}>
                  <td>
                    {p.image_url
                      ? <img src={`${BASE}${p.image_url}`} className={s.thumb} alt="" />
                      : <span className={s.noPhoto}>нет</span>}
                  </td>
                  <td>{p.name}</td>
                  <td>{p.price} ₽</td>
                  <td>
                    <span className={p.is_active ? s.active : s.inactive}>
                      {p.is_active ? 'Да' : 'Нет'}
                    </span>
                  </td>
                  <td className={s.actions}>
                    <button className={s.btnEdit} onClick={() => openEdit(p)}>✏️</button>
                    {p.image_url && (
                      <button className={s.btnDel} onClick={() => handleDeletePhoto(p.id)} title="Удалить фото">🖼</button>
                    )}
                    <button className={s.btnDel} onClick={() => handleDelete(p.id)}>🗑</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )
      }

      {modal && (
        <div className={s.overlay} onClick={e => e.target === e.currentTarget && setModal(null)}>
          <div className={s.modalBox}>
            <h2 className={s.modalTitle}>{modal === 'add' ? 'Добавить товар' : 'Редактировать товар'}</h2>

            <label className={s.label}>Название
              <input className={s.input} value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            </label>

            <label className={s.label}>Цена (₽)
              <input className={s.input} type="number" value={form.price} onChange={e => setForm(f => ({ ...f, price: e.target.value }))} />
            </label>

            <label className={s.label}>Категория
              <select className={s.input} value={form._cat_id || ''} onChange={e => setForm(f => ({ ...f, _cat_id: e.target.value, subcategory_id: '' }))}>
                <option value="">— выберите —</option>
                {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>

            <label className={s.label}>Подкатегория
              <select className={s.input} value={form.subcategory_id} onChange={e => setForm(f => ({ ...f, subcategory_id: e.target.value }))}>
                <option value="">— выберите —</option>
                {subcats.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </label>

            <label className={s.label}>Описание
              <textarea className={s.input} rows={3} value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
            </label>

            <label className={s.label}>Характеристики
              <textarea className={s.input} rows={2} value={form.characteristics} onChange={e => setForm(f => ({ ...f, characteristics: e.target.value }))} />
            </label>

            <label className={s.label}>Фото (JPEG/PNG/WebP)
              <input type="file" accept="image/*" onChange={e => setPhotoFile(e.target.files[0])} />
              {photoFile && <span className={s.fileHint}>{photoFile.name}</span>}
            </label>

            <label className={s.checkLabel}>
              <input type="checkbox" checked={form.is_active} onChange={e => setForm(f => ({ ...f, is_active: e.target.checked }))} />
              Активен (показывать в боте)
            </label>

            <div className={s.modalFooter}>
              <button className={s.btnCancel} onClick={() => setModal(null)}>Отмена</button>
              <button className={s.btnSave} onClick={handleSave} disabled={saving}>
                {saving ? 'Сохранение...' : 'Сохранить'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
