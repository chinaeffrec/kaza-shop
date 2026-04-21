import { useState, useEffect, useCallback } from 'react'
import { api } from '../api.js'
import s from './ProductsPage.module.css'

const EMPTY = { name:'', price:'', discount_price:'', subcategory_id:'', description:'', characteristics:'', stock:0, is_active:true, _cat_id:'' }

export default function ProductsPage() {
  const [products, setProducts]   = useState([])
  const [categories, setCategories] = useState([])
  const [subcats, setSubcats]     = useState([])
  const [allSubcats, setAllSubcats] = useState({})  // id -> {name, category_name}
  const [loading, setLoading]     = useState(true)
  const [search, setSearch]       = useState('')
  const [onlyNoPhoto, setOnlyNoPhoto] = useState(false)
  const [modal, setModal]         = useState(null)
  const [form, setForm]           = useState(EMPTY)
  const [photoFile, setPhotoFile] = useState(null)
  const [saving, setSaving]       = useState(false)

  const load = useCallback(async () => {
  setLoading(true)

  try {
    const [prods, cats] = await Promise.all([
      api.getProducts(),
      api.getCategories()
    ])

    setProducts(prods)
    setCategories(cats)

    // Загружаем все подкатегории параллельно
    const subResults = await Promise.all(
      cats.map(cat => api.getSubcategories(cat.id).then(subs => ({ cat, subs })))
    )

    const subMap = {}

    for (const { cat, subs } of subResults) {
      for (const sub of subs) {
        subMap[sub.id] = {
          name: sub.name,
          category_name: cat.name
        }
      }
    }

    setAllSubcats(subMap)

  } catch (e) {
    alert('Ошибка загрузки: ' + (e?.message || 'неизвестная ошибка'))
  } finally {
    setLoading(false)
  }
}, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!form._cat_id) { setSubcats([]); return }
    api.getSubcategories(form._cat_id).then(setSubcats).catch(() => setSubcats([]))
  }, [form._cat_id])

  function openAdd() { setForm(EMPTY); setPhotoFile(null); setModal('add') }

  function openEdit(p) {
    setForm({ name:p.name, price:String(p.price), discount_price:String(p.discount_price||''),
      subcategory_id:String(p.subcategory_id), description:p.description||'',
      characteristics:p.characteristics||'', stock:p.stock||0, is_active:p.is_active, _cat_id:'' })
    setPhotoFile(null); setModal(p)
  }

  async function handleSave() {
    setSaving(true)
    try {
      const payload = { name:form.name, price:parseInt(form.price),
        discount_price: form.discount_price ? parseInt(form.discount_price) : null,
        subcategory_id:parseInt(form.subcategory_id),
        description:form.description||null, characteristics:form.characteristics||null,
        stock: parseInt(form.stock)||0, is_active:form.is_active }
      const saved = modal === 'add' ? await api.createProduct(payload) : await api.updateProduct(modal.id, payload)
      if (photoFile) await api.uploadPhoto(saved.id, photoFile)
      setModal(null); await load()
    } catch(e) { alert('Ошибка: ' + e.message) }
    finally { setSaving(false) }
  }

  async function handleDelete(id) {
    if (!confirm('Удалить товар?')) return
    await api.deleteProduct(id).catch(e => alert(e.message)); await load()
  }
  async function handleDeletePhoto(id) {
    await api.deletePhoto(id).catch(e => alert(e.message)); await load()
  }

  const visible = products.filter(p => {
    if (onlyNoPhoto && p.has_image) return false
    if (search && !p.name.toLowerCase().includes(search.toLowerCase())) return false
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
        <input className={s.search} placeholder="Поиск..." value={search} onChange={e=>setSearch(e.target.value)} />
        <label className={s.checkLabel}>
          <input type="checkbox" checked={onlyNoPhoto} onChange={e=>setOnlyNoPhoto(e.target.checked)} />
          Только без фото
        </label>
      </div>

      {visible.length === 0 ? <p className={s.msg}>Товары не найдены</p> : (
        <table className={s.table}>
          <thead><tr><th>Фото</th><th>Название</th><th>Категория</th><th>Подкатегория</th><th>Цена</th><th>Цена со скидкой</th><th>Активен</th><th></th></tr></thead>
          <tbody>
            {visible.map(p => (
              <tr key={p.id} className={!p.has_image ? s.noPhotoRow : ''}>
                <td>
                  {p.image_url
                      ? <img src={`${api.BASE}${p.image_url}?t=${Date.now()}`} className={s.thumb} alt=""
                             onError={e => { e.target.style.display='none' }} />
                    : <span className={s.noPhotoBadge}>нет фото</span>}
                </td>
                <td>{p.name}</td>
                <td>{allSubcats[p.subcategory_id]?.category_name || '—'}</td>
                <td>{allSubcats[p.subcategory_id]?.name || '—'}</td>
                <td>{p.price} ₽</td>
                <td>{p.discount_price ? <span className={s.discount}>{p.discount_price.toLocaleString()} ₽</span> : '—'}</td>
                <td><span className={p.is_active ? s.active : s.inactive}>{p.is_active ? 'Да' : 'Нет'}</span></td>
                <td className={s.actions}>
                  <button className={s.btnEdit} onClick={() => openEdit(p)}>✏️</button>
                  {p.image_url && <button className={s.btnDel} onClick={() => handleDeletePhoto(p.id)} title="Удалить фото">🖼</button>}
                  <button className={s.btnDel} onClick={() => handleDelete(p.id)}>🗑</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {modal && (
        <div className={s.overlay} onClick={e => e.target===e.currentTarget && setModal(null)}>
          <div className={s.modalBox}>
            <h2 className={s.modalTitle}>{modal==='add' ? 'Добавить товар' : 'Редактировать'}</h2>
            <label className={s.label}>Название<input className={s.input} value={form.name} onChange={e=>setForm(f=>({...f,name:e.target.value}))} /></label>
            <div style={{display:'flex',gap:12}}>
              <label className={s.label} style={{flex:1}}>Цена (₽)<input className={s.input} type="number" value={form.price} onChange={e=>setForm(f=>({...f,price:e.target.value}))} /></label>
              <label className={s.label} style={{flex:1}}>Цена со скидкой<input className={s.input} type="number" value={form.discount_price} onChange={e=>setForm(f=>({...f,discount_price:e.target.value}))} /></label>
            </div>
            <label className={s.label}>Категория
              <select className={s.input} value={form._cat_id} onChange={e=>setForm(f=>({...f,_cat_id:e.target.value,subcategory_id:''}))}>
                <option value="">— выберите —</option>
                {categories.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
            <label className={s.label}>Подкатегория
              <select className={s.input} value={form.subcategory_id} onChange={e=>setForm(f=>({...f,subcategory_id:e.target.value}))}>
                <option value="">— выберите —</option>
                {subcats.map(sc=><option key={sc.id} value={sc.id}>{sc.name}</option>)}
              </select>
            </label>
            <label className={s.label}>Описание<textarea className={s.input} rows={3} value={form.description} onChange={e=>setForm(f=>({...f,description:e.target.value}))} /></label>
            <label className={s.label}>Характеристики<textarea className={s.input} rows={2} value={form.characteristics} onChange={e=>setForm(f=>({...f,characteristics:e.target.value}))} /></label>
            <label className={s.label}>Остаток (шт)<input className={s.input} type="number" value={form.stock} onChange={e=>setForm(f=>({...f,stock:e.target.value}))} /></label>
            <label className={s.label}>Фото (JPEG/PNG/WebP)
              <input type="file" accept="image/*" onChange={e=>setPhotoFile(e.target.files[0])} />
              {photoFile && <span className={s.fileHint}>{photoFile.name}</span>}
            </label>
            <label className={s.checkLabel}><input type="checkbox" checked={form.is_active} onChange={e=>setForm(f=>({...f,is_active:e.target.checked}))} /> Активен</label>
            <div className={s.modalFooter}>
              <button className={s.btnCancel} onClick={()=>setModal(null)}>Отмена</button>
              <button className={s.btnSave} onClick={handleSave} disabled={saving}>{saving?'Сохранение...':'Сохранить'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
