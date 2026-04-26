import { useState, useEffect, useCallback } from 'react'
import { api } from '../api.js'
import s from './ProductsPage.module.css'

const EMPTY = {
  name: '',
  price: '',
  discount_price: '',
  subcategory_id: '',
  description: '',
  characteristics: '',
  stock: 0,
  is_active: true,
  _cat_id: ''
}

export default function ProductsPage() {
  const [products, setProducts]           = useState([])
  const [categories, setCategories]       = useState([])
  const [allSubcats, setAllSubcats]       = useState({})
  const [subcats, setSubcats]             = useState([])
  const [loading, setLoading]             = useState(true)
  const [search, setSearch]               = useState('')
  const [filterCat, setFilterCat]         = useState('')
  const [filterSub, setFilterSub]         = useState('')
  const [filterSubOpts, setFilterSubOpts] = useState([])
  const [onlyNoPhoto, setOnlyNoPhoto]     = useState(false)
  const [modal, setModal]                 = useState(null)
  const [form, setForm]                   = useState(EMPTY)
  const [photoFile, setPhotoFile]         = useState(null)
  const [photoPreview, setPhotoPreview]   = useState(null)
  const [extraPhotos, setExtraPhotos]     = useState({})
  const [extraPreviews, setExtraPreviews] = useState({})
  const [saving, setSaving]               = useState(false)
  const [hideNoStock, setHideNoStock]     = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [prods, cats, cfg] = await Promise.all([
        api.getProducts(),
        api.getCategories(),
        api.getSettings(),
      ])
      setHideNoStock(cfg.hide_out_of_stock || false)
      setProducts(prods)
      setCategories(cats)
      const subResults = await Promise.all(
        cats.map(cat => api.getSubcategories(cat.id).then(subs => ({ cat, subs })))
      )
      const subMap = {}
      for (const { cat, subs } of subResults)
        for (const sub of subs)
          subMap[sub.id] = { name: sub.name, category_name: cat.name, category_id: cat.id }
      setAllSubcats(subMap)
    } catch (e) {
      alert('Ошибка загрузки: ' + e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!filterCat) { setFilterSubOpts([]); setFilterSub(''); return }
    api.getSubcategories(filterCat).then(setFilterSubOpts).catch(() => {})
    setFilterSub('')
  }, [filterCat])

  useEffect(() => {
    if (!form._cat_id) { setSubcats([]); return }
    api.getSubcategories(form._cat_id).then(setSubcats).catch(() => setSubcats([]))
  }, [form._cat_id])

  function openAdd() {
    setForm(EMPTY)
    setPhotoFile(null)
    setPhotoPreview(null)
    setExtraPhotos({})
    setExtraPreviews({})
    setModal({ type: 'add' })
  }

  function openEdit(p) {
    const sub = allSubcats?.[p.subcategory_id]
    setForm({
      name: p.name,
      price: String(p.price),
      discount_price: String(p.discount_price || ''),
      subcategory_id: String(p.subcategory_id),
      description: p.description || '',
      characteristics: p.characteristics || '',
      stock: p.stock || 0,
      is_active: p.is_active,
      _cat_id: sub?.category_id ? String(sub.category_id) : ''
    })
    setPhotoFile(null)
    setPhotoPreview(p.image_url ? api.BASE + p.image_url : null)
    setExtraPhotos({})
    // Инициализируем превью существующих доп. фото из данных товара
    setExtraPreviews({
      2: p.image_url_2 ? api.BASE + p.image_url_2 : null,
      3: p.image_url_3 ? api.BASE + p.image_url_3 : null,
    })
    setModal({ type: 'edit', product: p })
  }

  async function handleSave() {
    if (!form.name.trim()) return alert('Введите название')
    if (!form.price) return alert('Введите цену')
    if (!form.subcategory_id) return alert('Выберите категорию и подкатегорию')

    setSaving(true)
    try {
      const payload = {
        name: form.name.trim(),
        price: parseInt(form.price),
        discount_price: form.discount_price ? parseInt(form.discount_price) : null,
        subcategory_id: parseInt(form.subcategory_id),
        description: form.description || null,
        characteristics: form.characteristics || null,
        stock: parseInt(form.stock) || 0,
        is_active: form.is_active,
      }

      const saved = modal?.type === 'add'
        ? await api.createProduct(payload)
        : await api.updateProduct(modal.product.id, payload)

      // Основное фото (слот 1)
      if (photoFile) {
        await api.uploadPhotoSlot(saved.id, 1, photoFile)
      }

      // Дополнительные фото (слоты 2 и 3)
      for (const [slot, file] of Object.entries(extraPhotos)) {
        if (file) {
          await api.uploadPhotoSlot(saved.id, parseInt(slot), file)
        }
      }

      setExtraPhotos({})
      setExtraPreviews({})
      setPhotoFile(null)
      setPhotoPreview(null)
      setModal(null)
      await load()
    } catch (e) {
      console.error(e)
      alert('Ошибка сохранения: ' + (e.message || e))
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

  async function toggleActive(p) {
    await api.toggleActive(p.id, !p.is_active).catch(e => alert(e.message))
    await load()
  }

  async function toggleHideNoStock(val) {
    setHideNoStock(val)
    await api.updateSettings({ hide_out_of_stock: val }).catch(() => {})
    await api.reloadCache()
  }

  const visible = products.filter(p => {
    if (onlyNoPhoto && p.has_image) return false
    if (search && !p.name.toLowerCase().includes(search.toLowerCase())) return false
    if (filterCat) {
      const sub = allSubcats[p.subcategory_id]
      if (!sub || String(sub.category_id) !== String(filterCat)) return false
    }
    if (filterSub && String(p.subcategory_id) !== String(filterSub)) return false
    return true
  })

  if (loading) return <p className={s.msg}>Загрузка...</p>

  return (
    <div>
      <div className={s.toolbar}>
        <h1 className={s.title}>Товары <span className={s.count}>{products.length}</span></h1>
        <button className={s.btnAdd} onClick={openAdd}>+ Добавить</button>
      </div>

      <div className={s.filters}>
        <input className={s.search} placeholder="Поиск..." value={search}
          onChange={e => setSearch(e.target.value)} />
        <select className={s.filterSelect} value={filterCat}
          onChange={e => setFilterCat(e.target.value)}>
          <option value="">Все категории</option>
          {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        {filterSubOpts.length > 0 && (
          <select className={s.filterSelect} value={filterSub}
            onChange={e => setFilterSub(e.target.value)}>
            <option value="">Все подкатегории</option>
            {filterSubOpts.map(sc => <option key={sc.id} value={sc.id}>{sc.name}</option>)}
          </select>
        )}
        <label className={s.checkLabel}>
          <input type="checkbox" checked={onlyNoPhoto}
            onChange={e => setOnlyNoPhoto(e.target.checked)} />
          Без фото
        </label>
        <label className={s.checkLabel}>
          <input type="checkbox" checked={hideNoStock}
            onChange={e => toggleHideNoStock(e.target.checked)} />
          Скрыть для покупателя товары без остатка
        </label>
      </div>

      {visible.length === 0 ? <p className={s.msg}>Товары не найдены</p> : (
        <table className={s.table}>
          <thead>
            <tr>
              <th>Фото</th><th>Название</th><th>Категория</th><th>Подкатегория</th>
              <th>Цена</th><th>Цена со скидкой</th><th>Остаток</th><th>Активен</th><th></th>
            </tr>
          </thead>
          <tbody>
            {visible.map(p => (
              <tr key={p.id} className={!p.has_image ? s.noPhotoRow : ''}>
                <td>
                  {p.image_url
                    ? <img src={`${api.BASE}${p.image_url}?v=${p.updated_at || ''}`}
                           className={s.thumb} alt=""
                           onError={e => { e.target.style.display = 'none' }} />
                    : <span className={s.noPhotoBadge}>нет</span>}
                </td>
                <td className={s.nameCell}>{p.name}</td>
                <td className={s.subCell}>{allSubcats[p.subcategory_id]?.category_name || '—'}</td>
                <td className={s.subCell}>{allSubcats[p.subcategory_id]?.name || '—'}</td>
                <td>{(p.price || 0).toLocaleString()} ₽</td>
                <td>{p.discount_price
                  ? <span className={s.discount}>{p.discount_price.toLocaleString()} ₽</span>
                  : '—'}</td>
                <td className={s.stockCell}>{p.stock ?? 0}</td>
                <td>
                  <button className={p.is_active ? s.activeBadge : s.inactiveBadge}
                    onClick={() => toggleActive(p)} title="Нажмите чтобы переключить">
                    {p.is_active ? 'Да' : 'Нет'}
                  </button>
                </td>
                <td className={s.actions}>
                  <button className={s.btnEdit} onClick={() => openEdit(p)}>✏️</button>
                  {p.image_url && (
                    <button className={s.btnDel} onClick={() => handleDeletePhoto(p.id)}
                      title="Удалить фото">🖼</button>
                  )}
                  <button className={s.btnDel} onClick={() => handleDelete(p.id)}>🗑</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {modal && (
        <div className={s.overlay} onClick={e => e.target === e.currentTarget && setModal(null)}>
          <div className={s.modalBox}>
            <h2 className={s.modalTitle}>
              {modal?.type === 'add' ? 'Добавить товар' : 'Редактировать товар'}
            </h2>

            <label className={s.label}>Название *
              <input className={s.input} value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            </label>

            <div style={{ display: 'flex', gap: 12 }}>
              <label className={s.label} style={{ flex: 1 }}>Цена (₽) *
                <input className={s.input} type="number" value={form.price}
                  onChange={e => setForm(f => ({ ...f, price: e.target.value }))} />
              </label>
              <label className={s.label} style={{ flex: 1 }}>Цена со скидкой
                <input className={s.input} type="number" value={form.discount_price}
                  onChange={e => setForm(f => ({ ...f, discount_price: e.target.value }))} />
              </label>
            </div>

            <label className={s.label}>Категория *
              <select className={s.input} value={form._cat_id}
                onChange={e => setForm(f => ({ ...f, _cat_id: e.target.value, subcategory_id: '' }))}>
                <option value="">— выберите —</option>
                {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>

            <label className={s.label}>Подкатегория *
              <select className={s.input} value={form.subcategory_id}
                onChange={e => setForm(f => ({ ...f, subcategory_id: e.target.value }))}>
                <option value="">— выберите —</option>
                {subcats.map(sc => <option key={sc.id} value={sc.id}>{sc.name}</option>)}
              </select>
            </label>

            <label className={s.label}>Описание
              <textarea className={s.input} rows={3} value={form.description}
                onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
            </label>

            <label className={s.label}>Характеристики
              <textarea className={s.input} rows={2} value={form.characteristics}
                onChange={e => setForm(f => ({ ...f, characteristics: e.target.value }))} />
            </label>

            <label className={s.label}>Остаток (шт)
              <input className={s.input} type="number" min="0" value={form.stock}
                onChange={e => setForm(f => ({ ...f, stock: e.target.value }))} />
            </label>

            {/* Фото 1, 2, 3 */}
            {[1, 2, 3].map(slot => {
              const isMain = slot === 1
              // Показываем: новый preview (если выбран файл) ИЛИ существующее фото товара
              const preview = isMain
                ? photoPreview
                : extraPreviews[slot] || null

              return (
                <label key={slot} className={s.label}>
                  {isMain ? 'Фото 1 (основное)' : `Фото ${slot} (дополнительное)`}
                  {preview && (
                    <img src={preview} alt={`preview ${slot}`} style={{
                      width: 80, height: 80, objectFit: 'cover',
                      borderRadius: 8, marginBottom: 6, display: 'block'
                    }} />
                  )}
                  <input type="file" accept="image/jpeg,image/png,image/webp"
                    onChange={e => {
                      const f = e.target.files[0]
                      if (!f) return
                      const url = URL.createObjectURL(f)
                      if (isMain) {
                        setPhotoFile(f)
                        setPhotoPreview(url)
                      } else {
                        setExtraPhotos(prev => ({ ...prev, [slot]: f }))
                        setExtraPreviews(prev => ({ ...prev, [slot]: url }))
                      }
                    }} />
                </label>
              )
            })}

            <label className={s.checkLabel}>
              <input type="checkbox" checked={form.is_active}
                onChange={e => setForm(f => ({ ...f, is_active: e.target.checked }))} />
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
