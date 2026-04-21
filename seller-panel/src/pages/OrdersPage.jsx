import { useState, useEffect, useCallback } from 'react'
import { api } from '../api.js'
import s from './OrdersPage.module.css'

export default function OrdersPage() {
  const [orders, setOrders]     = useState([])
  const [statuses, setStatuses] = useState([])
  const [filter, setFilter]     = useState('')
  const [loading, setLoading]   = useState(true)
  const [expanded, setExpanded] = useState(null)
  const [detail, setDetail]     = useState(null)
  const [msgs, setMsgs]         = useState([])
  const [updating, setUpdating] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [ord, st] = await Promise.all([api.getOrders(filter), api.getOrderStatuses()])
      setOrders(ord); setStatuses(st)
    } catch(e) { alert(e.message) }
    finally { setLoading(false) }
  }, [filter])

  useEffect(() => { load() }, [load])

  async function expand(order) {
    if (expanded === order.id) { setExpanded(null); setDetail(null); setMsgs([]); return }
    setExpanded(order.id); setDetail(null); setMsgs([])
    const [d, conversation] = await Promise.all([
      api.getOrder(order.id),
      api.getConversation(order.user_id).catch(() => [])
    ])
    setDetail(d); setMsgs(conversation)
  }

  async function changeStatus(orderId, newStatus) {
    setUpdating(orderId)
    try { await api.updateOrderStatus(orderId, newStatus); await load() }
    catch(e) { alert(e.message) }
    finally { setUpdating(null) }
  }

  return (
    <div>
      <div className={s.toolbar}>
        <h1 className={s.title}>Заказы <span className={s.count}>{orders.length}</span></h1>
        <button className={s.refresh} onClick={load}>↻ Обновить</button>
      </div>
      <div className={s.tabs}>
        <button className={`${s.tab} ${filter===''?s.activeTab:''}`} onClick={()=>setFilter('')}>Все</button>
        {statuses.map(st=>(
          <button key={st.value} className={`${s.tab} ${filter===st.value?s.activeTab:''}`}
            onClick={()=>setFilter(st.value)}>{st.label}</button>
        ))}
      </div>

      {loading ? <p className={s.msg}>Загрузка...</p> : orders.length===0 ? <p className={s.msg}>Заказов нет</p> : (
        <div className={s.list}>
          {orders.map(o => (
            <div key={o.id} className={s.card}>
              <div className={s.cardHead} onClick={()=>expand(o)}>
                <span className={s.orderId}>#{o.id}</span>
                <span className={s.userId}>👤 {o.user_id}</span>
                <span className={s.total}>{o.total.toLocaleString()} ₽</span>
                <span className={s.statusBadge}>{o.status_label || o.status}</span>
                <span className={s.date}>{o.created_at?.slice(0,10)}</span>
                <span className={s.chevron}>{expanded===o.id?'▲':'▼'}</span>
              </div>

              {expanded===o.id && (
                <div className={s.cardBody}>
                  <div className={s.infoRow}>
                    <b>Telegram ID:</b> {o.user_id}
                    {o.comment && <span> · {o.comment}</span>}
                  </div>

                  <h4 className={s.subTitle}>Товары</h4>
                  {!detail ? <p className={s.msg}>Загрузка...</p> : (
                    <table className={s.itemsTable}>
                      <thead><tr><th>Товар</th><th>Цена</th><th>Кол-во</th><th>Сумма</th></tr></thead>
                      <tbody>
                        {detail.items?.map((it,i)=>(
                          <tr key={i}>
                            <td>{it.name}</td><td>{it.price} ₽</td>
                            <td>{it.quantity}</td><td>{it.sum} ₽</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}

                  {msgs.length > 0 && (
                    <>
                      <h4 className={s.subTitle}>Переписка</h4>
                      <div className={s.miniChat}>
                        {msgs.slice(-5).map(m=>(
                          <div key={m.id} className={`${s.miniMsg} ${m.direction==='out'?s.miniOut:s.miniIn}`}>
                            <span className={s.miniWho}>{m.direction==='out'?'Продавец':'Клиент'}</span>
                            <span className={s.miniText}>{m.text}</span>
                            <span className={s.miniTime}>{m.created_at?.slice(11,16)}</span>
                          </div>
                        ))}
                      </div>
                    </>
                  )}

                  <h4 className={s.subTitle}>Изменить статус</h4>
                  <div className={s.statusRow}>
                    {statuses.map(st=>(
                      <button key={st.value}
                        className={`${s.statusBtn} ${o.status===st.value?s.activeSt:''}`}
                        disabled={updating===o.id || o.status===st.value}
                        onClick={()=>changeStatus(o.id, st.value)}>{st.label}</button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
