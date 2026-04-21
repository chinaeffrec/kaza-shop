import { useState, useEffect } from 'react'
import { api } from '../api.js'
import s from './SettingsPage.module.css'

export default function SettingsPage({ onSaved }) {
  const [shopName, setShopName]         = useState('')
  const [reviewsEnabled, setReviews]    = useState(true)
  const [welcomeMsg, setWelcomeMsg] = useState('')
  const [sellerContact, setSellerContact] = useState('')
  const [saving, setSaving]             = useState(false)
  const [faq, setFaq]                   = useState([])
  const [faqForm, setFaqForm] = useState({ question:'', answer:'' })
  const [dragIdx, setDragIdx] = useState(null)
  const [editFaqId, setEditFaqId]       = useState(null)
  const [logs, setLogs]                 = useState([])
  const [logsOpen, setLogsOpen]         = useState(false)
  const [logsLoading, setLogsLoading]   = useState(false)

  useEffect(() => {
    api.getSettings().then(cfg => {
      setWelcomeMsg(cfg.welcome_message || '👋 Добро пожаловать!\n\nВыберите действие:')
      setShopName(cfg.shop_name || 'Kaza Shop')
      setReviews(cfg.reviews_enabled !== false)
      setSellerContact(cfg.seller_contact || '')
      setLogoUrl(cfg.logo_url ? `${api.BASE}${cfg.logo_url}` : null)
    }).catch(() => {})
    api.getFaq().then(setFaq).catch(() => {})
  }, [])

  async function saveSettings() {
    setSaving(true)
    try {
      let updated = await api.updateSettings({ shop_name: shopName, reviews_enabled: reviewsEnabled, welcome_message: welcomeMsg, seller_contact: sellerContact })
      onSaved?.({ ...updated, logo_url: updated.logo_url })
      alert('Настройки сохранены')
    } catch(e) { alert(e.message) }
    finally { setSaving(false) }
  }

  // FAQ
  async function saveFaq() {
  if (!faqForm.question.trim() || !faqForm.answer.trim()) return alert('Заполните вопрос и ответ')
  try {
    if (editFaqId) {
      const upd = await api.updateFaq(editFaqId, faqForm)
      setFaq(f => f.map(i => i.id === editFaqId ? upd : i))
    } else {
      const created = await api.createFaq({ ...faqForm, sort_order: faq.length })
      setFaq(f => [...f, created])
    }
    setFaqForm({ question:'', answer:'' }); setEditFaqId(null)
  } catch(e) { alert(e.message) }
  }

  function startEdit(item) {
  setEditFaqId(item.id)
  setFaqForm({ question:item.question, answer:item.answer })
  }

  async function onDrop(targetIdx) {
  if (dragIdx === null || dragIdx === targetIdx) return
  const reordered = [...faq]
  const [moved] = reordered.splice(dragIdx, 1)
  reordered.splice(targetIdx, 0, moved)
  setFaq(reordered)
  setDragIdx(null)
  // Сохраняем новый порядок
  for (let i = 0; i < reordered.length; i++) {
    await api.updateFaq(reordered[i].id, { sort_order: i }).catch(() => {})
  }
  }

  async function deleteFaq(id) {
    if (!confirm('Удалить вопрос?')) return
    await api.deleteFaq(id).catch(e => alert(e.message))
    setFaq(f => f.filter(i => i.id !== id))
  }

  async function toggleFaqActive(item) {
    const upd = await api.updateFaq(item.id, { is_active: !item.is_active }).catch(e => { alert(e.message); return null })
    if (upd) setFaq(f => f.map(i => i.id === item.id ? upd : i))
  }

  async function loadLogs() {
    setLogsLoading(true); setLogsOpen(true); setLogs([])
    const lines = []
    const ts = () => new Date().toLocaleTimeString()
    try {
      const health = await fetch(`${api.BASE}/health`).then(r => r.json())
      lines.push(`[${ts()}] ✅ Сервис работает — статус: ${health.status}`)
    } catch { lines.push(`[${ts()}] ❌ Сервис недоступен`) }
    try {
      const db = await fetch(`${api.BASE}/db-test`).then(r => r.json())
      lines.push(`[${ts()}] 🗄 База данных: ${db.db === 'ok' ? '✅ подключена' : '❌ ошибка: ' + db.detail}`)
    } catch { lines.push(`[${ts()}] 🗄 База данных: ⚠️ нет ответа`) }
    try {
      const orders = await api.getOrders()
      const byStatus = orders.reduce((a,o)=>{ a[o.status]=(a[o.status]||0)+1; return a },{})
      lines.push(`[${ts()}] 🧾 Заказов: ${orders.length} — ${Object.entries(byStatus).map(([k,v])=>`${k}:${v}`).join(', ')}`)
    } catch { lines.push(`[${ts()}] 🧾 Заказы: ⚠️ ошибка`) }
    try {
      const convs = await api.getConversations()
      const unread = convs.reduce((a,c)=>a+(c.unread||0),0)
      lines.push(`[${ts()}] 💬 Диалогов: ${convs.length}, непрочитанных: ${unread}`)
    } catch { lines.push(`[${ts()}] 💬 Сообщения: ⚠️ ошибка`) }
    try {
      const prods = await api.getProducts()
      const noPhoto = prods.filter(p=>!p.has_image).length
      lines.push(`[${ts()}] 📦 Товаров: ${prods.length}, без фото: ${noPhoto}`)
    } catch { lines.push(`[${ts()}] 📦 Товары: ⚠️ ошибка`) }
    setLogs(lines); setLogsLoading(false)
  }

  return (
    <div className={s.page}>
      <h1 className={s.title}>Настройки</h1>

      <section className={s.section}>
        <h2 className={s.sectionTitle}>Магазин</h2>
        <label className={s.label}>Название магазина
          <input className={s.input} value={shopName} onChange={e=>setShopName(e.target.value)} />
        </label>
        <label className={s.label}>Приветственное сообщение (в боте)
          <textarea
              className={s.input}
              rows={4}
              value={welcomeMsg}
              onChange={e => setWelcomeMsg(e.target.value)}
              placeholder="👋 Добро пожаловать!..."
          />
        </label>
        <label className={s.label}>
          Контакт продавца (для кнопки "Написать нам")
          <input
              className={s.input}
              value={sellerContact}
              onChange={e => setSellerContact(e.target.value)}
              placeholder="@username или https://t.me/username"
          />
        </label>
        <label className={s.checkLabel}>
          <input type="checkbox" checked={reviewsEnabled} onChange={e=>setReviews(e.target.checked)} />
          Отзывы включены (для всех товаров)
        </label>
        <button className={s.btnSave} onClick={saveSettings} disabled={saving}>
          {saving ? 'Сохранение...' : 'Сохранить'}
        </button>
      </section>

      <section className={s.section}>
        <h2 className={s.sectionTitle}>FAQ для бота</h2>
        <div className={s.faqForm}>
          <input className={s.input} placeholder="Вопрос" value={faqForm.question}
            onChange={e=>setFaqForm(f=>({...f,question:e.target.value}))} />
          <textarea className={s.input} rows={3} placeholder="Ответ" value={faqForm.answer}
            onChange={e=>setFaqForm(f=>({...f,answer:e.target.value}))} />
          <div className={s.faqFooter}>
            <button className={s.btnSave} onClick={saveFaq}>{editFaqId ? 'Сохранить' : '+ Добавить'}</button>
            {editFaqId && <button className={s.btnCancel} onClick={()=>{setEditFaqId(null);setFaqForm({question:'',answer:'',sort_order:0})}}>Отмена</button>}
          </div>
        </div>
        <div className={s.faqList}>
          {faq.length === 0 && <p className={s.empty}>FAQ пуст — добавьте первый вопрос</p>}
          {faq.map(item => (
            <div key={item.id}
                 className={`${s.faqItem} ${!item.is_active ? s.faqInactive : ''}`}
                 draggable
                 onDragStart={() => setDragIdx(faq.indexOf(item))}
                 onDragOver={e => e.preventDefault()}
                 onDrop={() => onDrop(faq.indexOf(item))}
                 style={{cursor:'grab'}}>
              <div className={s.faqQ}>{item.question}</div>
              <div className={s.faqA}>{item.answer}</div>
              <div className={s.faqActions}>
                <span className={s.faqOrder}>#{item.sort_order}</span>
                <button className={s.btnSm} onClick={()=>toggleFaqActive(item)}>{item.is_active?'🙈 Скрыть':'👁 Показать'}</button>
                <button className={s.btnSm} onClick={()=>startEdit(item)}>✏️</button>
                <button className={s.btnSmDanger} onClick={()=>deleteFaq(item.id)}>🗑</button>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className={s.section}>
        <div className={s.logsHead}>
          <h2 className={s.sectionTitle} style={{margin:0}}>Системный журнал</h2>
          <button className={s.btnRefresh} onClick={loadLogs} disabled={logsLoading}>
            {logsLoading ? 'Проверка...' : '🔍 Проверить состояние'}
          </button>
          <button className={s.btnRefresh} style={{marginLeft:8,background:'#e8f5e9',color:'#2e7d32'}}
                  onClick={async () => {
                    try {
                      const r = await fetch(`${api.BASE}/catalog/cache/reload`, {method:'POST'})
                      const d = await r.json()
                      alert(d.message)
                    } catch { alert('Ошибка сброса кэша') }
                  }}>
            🔄 Сбросить кэш каталога
          </button>
        </div>
        {logsOpen && (
          <div className={s.logsBox}>
            {logs.length === 0 ? <span className={s.empty}>Нет данных</span>
              : logs.map((l,i) => <div key={i} className={s.logLine}>{l}</div>)}
          </div>
        )}
      </section>
    </div>
  )
}
