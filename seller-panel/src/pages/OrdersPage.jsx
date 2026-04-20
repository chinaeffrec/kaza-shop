import { useState, useEffect, useCallback } from 'react'
import { api } from '../api.js'
import s from './OrdersPage.module.css'

const STATUSES = [
  { value: '',           label: 'Все' },
  { value: 'new',        label: '🆕 Новые' },
  { value: 'confirmed',  label: '✅ Подтверждены' },
  { value: 'shipped',    label: '🚚 Отправлены' },
  { value: 'delivered',  label: '✔️ Доставлены' },
  { value: 'cancelled',  label: '❌ Отменены' },
]

const STATUS_LABELS = {
  new: '🆕 Новый', confirmed: '✅ Подтверждён', shipped: '🚚 Отправлен',
  delivered: '✔️ Доставлен', cancelled: '❌ Отменён',
}

export default function OrdersPage() {
  const [orders, setOrders]     = useState([])
  const [filter, setFilter]     = useState('')
  const [loading, setLoading]   = useState(true)
  const [expanded, setExpanded] = useState(null)
  const [detail, setDetail]     = useState(null)
  const [updating, setUpdating] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.getOrders(filter)
      setOrders(data)
    } catch (e) {
      alert(e.message)
    } finally {
      setLoading(false)
    }
  }, [filter])

  useEffect(() => { load() }, [load])

  async function expand(order) {
    if (expanded === order.id) { setExpanded(null); setDetail(null); return }
    setExpanded(order.id)
    const d = await api.getOrder(order.id).catch(() => null)
    setDetail(d)
  }

  async function changeStatus(orderId, newStatus) {
    setUpdating(orderId)
    try {
      await api.updateOrderStatus(orderId, newStatus)
      await load()
    } catch (e) {
      alert(e.message)
    } finally {
      setUpdating(null)
    }
  }

  return (
    <div>
      <div className={s.toolbar}>
        <h1 className={s.title}>Заказы <span className={s.count}>{orders.length}</span></h1>
        <button className={s.refresh} onClick={load}>↻ Обновить</button>
      </div>

      <div className={s.tabs}>
        {STATUSES.map(st => (
          <button
            key={st.value}
            className={`${s.tab} ${filter === st.value ? s.activeTab : ''}`}
            onClick={() => setFilter(st.value)}
          >{st.label}</button>
        ))}
      </div>

      {loading ? (
        <p className={s.msg}>Загрузка...</p>
      ) : orders.length === 0 ? (
        <p className={s.msg}>Заказов нет</p>
      ) : (
        <div className={s.list}>
          {orders.map(o => (
            <div key={o.id} className={s.card}>
              <div className={s.cardHead} onClick={() => expand(o)}>
                <span className={s.orderId}>#{o.id}</span>
                <span className={s.user}>user {o.user_id}</span>
                <span className={s.total}>{o.total} ₽</span>
                <span className={s[o.status] || s.badge}>{STATUS_LABELS[o.status] || o.status}</span>
                <span className={s.date}>{o.created_at?.slice(0, 10)}</span>
                <span className={s.chevron}>{expanded === o.id ? '▲' : '▼'}</span>
              </div>

              {expanded === o.id && (
                <div className={s.cardBody}>
                  {detail?.id === o.id ? (
                    <>
                      <table className={s.itemsTable}>
                        <thead><tr><th>Товар</th><th>Цена</th><th>Кол-во</th><th>Сумма</th></tr></thead>
                        <tbody>
                          {detail.items.map((it, i) => (
                            <tr key={i}>
                              <td>{it.name}</td>
                              <td>{it.price} ₽</td>
                              <td>{it.quantity}</td>
                              <td>{it.sum} ₽</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>

                      <div className={s.statusRow}>
                        <span>Изменить статус:</span>
                        {STATUSES.filter(st => st.value).map(st => (
                          <button
                            key={st.value}
                            className={`${s.statusBtn} ${o.status === st.value ? s.activeSt : ''}`}
                            disabled={updating === o.id || o.status === st.value}
                            onClick={() => changeStatus(o.id, st.value)}
                          >{st.label}</button>
                        ))}
                      </div>
                    </>
                  ) : <p className={s.msg}>Загрузка...</p>}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
