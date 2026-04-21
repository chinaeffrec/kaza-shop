import { useState, useEffect, useCallback } from 'react'
import { api } from '../api.js'
import s from './StatsPage.module.css'

export default function StatsPage({ saved, onSave }) {
  const [stats, setStats]       = useState(saved?.stats || [])
  const [products, setProducts] = useState(saved?.products || {})
  const [dateFrom, setDateFrom] = useState(saved?.dateFrom || '')
  const [dateTo, setDateTo]     = useState(saved?.dateTo || '')
  const [loading, setLoading]   = useState(false)
  const [sort, setSort]         = useState(saved?.sort || 'ordered')

  const load = useCallback(async () => {
  setLoading(true)
  try {
    const [st, prods] = await Promise.all([
      api.getStats(dateFrom || null, dateTo || null),
      api.getProducts(),
    ])
    const map = {}
    prods.forEach(p => { map[p.id] = p })
    setProducts(map)
    setStats(st)
    onSave?.({ stats: st, products: map, dateFrom, dateTo, sort }) // ← добавить эту строку
  } catch(e) { alert(e.message) }
  finally { setLoading(false) }
  }, [dateFrom, dateTo])

  useEffect(() => { load() }, [])

  const sorted = [...stats].sort((a,b) => (b[sort]||0) - (a[sort]||0))
  const totals = stats.reduce((acc,s) => ({
    cart: acc.cart + s.added_to_cart,
    ordered: acc.ordered + s.ordered,
    returned: acc.returned + s.returned,
    sold_sum: acc.sold_sum + (s.period_sold_sum||0),
  }), {cart:0,ordered:0,returned:0,sold_sum:0})

  const th = (col, label) => (
      <th className={s.sortable} onClick={() => {
        setSort(col)
        onSave?.({ stats, products, dateFrom, dateTo, sort: col })
      }}>
      {label}{sort===col?' ▼':''}
    </th>
  )

  return (
    <div>
      <div className={s.toolbar}>
        <h1 className={s.title}>Статистика</h1>
        <button className={s.btnRefresh} onClick={load}>↻ Обновить</button>
      </div>
      <div className={s.filters}>
        <label className={s.dateLabel}>С <input type="date" className={s.dateInput} value={dateFrom} onChange={e=>setDateFrom(e.target.value)} /></label>
        <label className={s.dateLabel}>По <input type="date" className={s.dateInput} value={dateTo} onChange={e=>setDateTo(e.target.value)} /></label>
        <button className={s.btnApply} onClick={load}>Применить</button>
        <button className={s.btnReset} onClick={()=>{setDateFrom('');setDateTo('')}}>Сбросить</button>
      </div>
      <div className={s.summary}>
        <div className={s.card}><div className={s.cardVal}>{totals.cart}</div><div className={s.cardLabel}>в корзину</div></div>
        <div className={s.card}><div className={s.cardVal}>{totals.ordered}</div><div className={s.cardLabel}>заказано</div></div>
        <div className={s.card}><div className={s.cardVal}>{totals.returned}</div><div className={s.cardLabel}>возвратов</div></div>
        <div className={s.card}><div className={s.cardVal}>{totals.sold_sum.toLocaleString()} ₽</div><div className={s.cardLabel}>выручка за период</div></div>
      </div>
      {loading ? <p className={s.msg}>Загрузка...</p> : (
        <table className={s.table}>
          <thead><tr>
            <th>Товар</th>
            {th('added_to_cart','В корзину')}
            {th('ordered','Заказано')}
            {th('returned','Возвраты')}
            {th('period_sold_qty','Продано (период)')}
            {th('period_sold_sum','Выручка (период)')}
            <th></th>
          </tr></thead>
          <tbody>
            {sorted.map(st=>{
              const p = products[st.product_id]
              return (
                <tr key={st.product_id}>
                  <td>{p?p.name:`ID ${st.product_id}`}</td>
                  <td className={s.num}>{st.added_to_cart}</td>
                  <td className={s.num}>{st.ordered}</td>
                  <td className={`${s.num} ${st.returned>0?s.warn:''}`}>{st.returned}</td>
                  <td className={s.num}>{st.period_sold_qty||0}</td>
                  <td className={s.num}>{(st.period_sold_sum||0).toLocaleString()} ₽</td>
                  <td><button className={s.btnReturn} onClick={()=>api.trackReturn(st.product_id).then(load)} title="Возврат">↩️</button></td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}
