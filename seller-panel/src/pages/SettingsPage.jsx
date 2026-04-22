import { useState, useEffect } from 'react'
import { api } from '../api.js'
import s from './SettingsPage.module.css'

export default function SettingsPage({ onSaved, adminLogin }) {
  const [shopName, setShopName]         = useState('')
  const [welcomeMsg, setWelcomeMsg]     = useState('')
  const [sellerContact, setSellerContact] = useState('')
  const [saving, setSaving]             = useState(false)

  const [faq, setFaq]         = useState([])
  const [faqForm, setFaqForm] = useState({ question:'', answer:'' })
  const [dragIdx, setDragIdx] = useState(null)
  const [editFaqId, setEditFaqId] = useState(null)

  const [pwForm, setPwForm]   = useState({ current_password:'', new_login:'', new_password:'' })
  const [pwSaving, setPwSaving] = useState(false)
  const [pwMsg, setPwMsg]     = useState('')

  const [logs, setLogs]         = useState([])
  const [logsOpen, setLogsOpen] = useState(false)
  const [logsLoading, setLogsLoading] = useState(false)

  useEffect(() => {
    api.getSettings().then(cfg => {
      setShopName(cfg.shop_name || 'Kaza Shop')
      setWelcomeMsg(cfg.welcome_message || '👋 Добро пожаловать!\n\nВыберите действие:')
      setSellerContact(cfg.seller_contact || '')
    }).catch(() => {})
    api.getFaq().then(setFaq).catch(() => {})
  }, [])

  async function saveSettings() {
    setSaving(true)
    try {
      const updated = await api.updateSettings({
        shop_name: shopName,
        welcome_message: welcomeMsg,
        seller_contact: sellerContact,
      })
      onSaved?.(updated)
      alert('Настройки сохранены')
    } catch(e) { alert(e.message) }
    finally { setSaving(false) }
  }

  // Password change
  async function saveCredentials() {
    if (!pwForm.new_login || !pwForm.new_password || !pwForm.current_password) {
      setPwMsg('Заполните все поля'); return
    }
    setPwSaving(true); setPwMsg('')
    try {
      const res = await api.updateCredentials({
        new_login: pwForm.new_login,
        new_password: pwForm.new_password,
        current_password: pwForm.current_password,
      })
      localStorage.setItem('admin_token', res.token)
      setPwMsg('✅ Данные обновлены')
      setPwForm({ current_password:'', new_login: res.login, new_password:'' })
    } catch(e) {
      setPwMsg('❌ ' + e.message)
    } finally { setPwSaving(false) }
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

  async function onDrop(targetIdx) {
    if (dragIdx === null || dragIdx === targetIdx) return
    const reordered = [...faq]
    const [moved] = reordered.splice(dragIdx, 1)
    reordered.splice(targetIdx, 0, moved)
    setFaq(reordered); setDragIdx(null)
    for (let i = 0; i < reordered.length; i++)
      await api.updateFaq(reordered[i].id, { sort_order: i }).catch(() => {})
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
      lines.push(`[${ts()}] 🗄 База данных: ${db.db==='ok'?'✅ подключена':'❌ ' + db.detail}`)
    } catch { lines.push(`[${ts()}] 🗄 База данных: ⚠️ нет ответа`) }
    try {
      const orders = await api.getOrders()
      const byStatus = orders.reduce((a,o)=>{ a[o.status]=(a[o.status]||0)+1; return a },{})
      lines.push(`[${ts()}] 🧾 Заказов: ${orders.length} — ${Object.entries(byStatus).map(([k,v])=>`${k}:${v}`).join(', ')||'нет'}`)
    } catch { lines.push(`[${ts()}] 🧾 Заказы: ⚠️ ошибка`) }
    try {
      const prods = await api.getProducts()
      const noPhoto = prods.filter(p=>!p.has_image).length
      lines.push(`[${ts()}] 📦 Товаров: ${prods.length}, без фото: ${noPhoto}`)
    } catch { lines.push(`[${ts()}] 📦 Товары: ⚠️ ошибка`) }
    lines.push(`[${ts()}] 🕐 Проверено: ${new Date().toLocaleString()}`)
    setLogs(lines); setLogsLoading(false)
  }

  return (
    <div className={s.page}>
      <h1 className={s.title}>Настройки</h1>

      {/* Магазин */}
      <section className={s.section}>
        <h2 className={s.sectionTitle}>Магазин</h2>
        <label className={s.label}>Название магазина
          <input className={s.input} value={shopName} onChange={e=>setShopName(e.target.value)} />
        </label>
        <label className={s.label}>Приветственное сообщение (отображается при /start в боте)
          <textarea className={s.input} rows={4} value={welcomeMsg}
            onChange={e=>setWelcomeMsg(e.target.value)}
            placeholder="👋 Добро пожаловать!..." />
        </label>
        <label className={s.label}>Контакт продавца (для кнопки «Написать нам»)
          <input className={s.input} value={sellerContact} onChange={e=>setSellerContact(e.target.value)}
            placeholder="@username или https://t.me/username" />
        </label>
        <button className={s.btnSave} onClick={saveSettings} disabled={saving}>
          {saving ? 'Сохранение...' : 'Сохранить настройки'}
        </button>
      </section>

      {/* FAQ */}
      <section className={s.section}>
        <h2 className={s.sectionTitle}>FAQ для бота</h2>
        <div className={s.faqForm}>
          <input className={s.input} placeholder="Вопрос" value={faqForm.question}
            onChange={e=>setFaqForm(f=>({...f,question:e.target.value}))} />
          <textarea className={s.input} rows={3} placeholder="Ответ" value={faqForm.answer}
            onChange={e=>setFaqForm(f=>({...f,answer:e.target.value}))} />
          <div className={s.faqFooter}>
            <button className={s.btnSave} onClick={saveFaq}>{editFaqId ? 'Сохранить' : '+ Добавить'}</button>
            {editFaqId && <button className={s.btnCancel} onClick={()=>{setEditFaqId(null);setFaqForm({question:'',answer:''})}}>Отмена</button>}
          </div>
        </div>
        <div className={s.faqList}>
          {faq.length===0 && <p className={s.empty}>FAQ пуст — добавьте первый вопрос</p>}
          {faq.map(item => (
            <div key={item.id}
              className={`${s.faqItem} ${!item.is_active?s.faqInactive:''}`}
              draggable onDragStart={()=>setDragIdx(faq.indexOf(item))}
              onDragOver={e=>e.preventDefault()} onDrop={()=>onDrop(faq.indexOf(item))}
              style={{cursor:'grab'}}>
              <div className={s.faqQ}>{item.question}</div>
              <div className={s.faqA}>{item.answer}</div>
              <div className={s.faqActions}>
                <button className={s.btnSm} onClick={()=>toggleFaqActive(item)}>
                  {item.is_active ? '🙈 Скрыть' : '👁 Показать'}
                </button>
                <button className={s.btnSm} onClick={()=>{setEditFaqId(item.id);setFaqForm({question:item.question,answer:item.answer})}}>✏️</button>
                <button className={s.btnSmDanger} onClick={()=>deleteFaq(item.id)}>🗑</button>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Смена логина/пароля */}
      <section className={s.section}>
        <h2 className={s.sectionTitle}>Безопасность</h2>
        <p className={s.hint}>Текущий логин: <b>{adminLogin}</b></p>
        <label className={s.label}>Текущий пароль
          <input type="password" className={s.input} value={pwForm.current_password}
            onChange={e=>setPwForm(f=>({...f,current_password:e.target.value}))} autoComplete="current-password" />
        </label>
        <label className={s.label}>Новый логин
          <input className={s.input} value={pwForm.new_login}
            onChange={e=>setPwForm(f=>({...f,new_login:e.target.value}))} placeholder="Минимум 3 символа" />
        </label>
        <label className={s.label}>Новый пароль
          <input type="password" className={s.input} value={pwForm.new_password}
            onChange={e=>setPwForm(f=>({...f,new_password:e.target.value}))}
            placeholder="Минимум 8 символов, буквы и цифры" autoComplete="new-password" />
        </label>
        {pwMsg && <p className={s.pwMsg}>{pwMsg}</p>}
        <button className={s.btnSave} onClick={saveCredentials} disabled={pwSaving}>
          {pwSaving ? 'Сохранение...' : 'Изменить данные входа'}
        </button>
      </section>

      {/* Системный журнал */}
      <section className={s.section}>
        <div className={s.logsHead}>
          <h2 className={s.sectionTitle} style={{margin:0}}>Системный журнал</h2>
          <div style={{display:'flex',gap:8}}>
            <button className={s.btnRefresh} onClick={loadLogs} disabled={logsLoading}>
              {logsLoading ? 'Проверка...' : '🔍 Проверить состояние'}
            </button>
            <button className={s.btnCacheReset} onClick={async()=>{
              try {
                const r = await api.reloadCache()
                alert(r.message || 'Кэш перезагружен')
              } catch { alert('Ошибка сброса кэша') }
            }}>
              🔄 Сбросить кэш каталога
            </button>
          </div>
        </div>
        {logsOpen && (
          <div className={s.logsBox}>
            {logs.length===0 ? <span className={s.empty}>Нет данных</span>
              : logs.map((l,i)=><div key={i} className={s.logLine}>{l}</div>)}
          </div>
        )}
      </section>
    </div>
  )
}
