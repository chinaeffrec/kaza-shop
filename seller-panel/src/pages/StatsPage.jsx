import { useState, useEffect, useCallback } from 'react'
import { api } from '../api.js'
import s from './StatsPage.module.css'

export default function StatsPage({ saved, onSave }) {
  const [dashboard, setDashboard] = useState(saved?.dashboard || null)
  const [stats, setStats]         = useState(saved?.stats || [])
  const [products, setProducts]   = useState(saved?.products || {})
  const [dateFrom, setDateFrom]   = useState(saved?.dateFrom || '')
  const [dateTo, setDateTo]       = useState(saved?.dateTo || '')
  const [loading, setLoading]     = useState(false)
  const [sort, setSort]           = useState(saved?.sort || 'ordered')
  const [tab, setTab]             = useState('dashboard')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [dash, st, prods] = await Promise.all([
        api.getDashboard(dateFrom || null, dateTo || null),
        api.getStats(dateFrom || null, dateTo || null),
        api.getProducts(),
      ])
      const map = {}
      prods.forEach(p => { map[p.id] = p })
      setDashboard(dash)
      setStats(st)
      setProducts(map)
      onSave?.({ dashboard: dash, stats: st, products: map, dateFrom, dateTo, sort })
    } catch(e) { alert(e.message) }
    finally { setLoading(false) }
  }, [dateFrom, dateTo])

  useEffect(() => { load() }, [])

  const sorted = [...stats].sort((a,b) => (b[sort]||0) - (a[sort]||0))

  const th = (col, label) => (
    <th className={s.sortable} onClick={() => {
      setSort(col)
      onSave?.({ dashboard, stats, products, dateFrom, dateTo, sort: col })
    }}>
      {label}{sort===col?' ▼':''}
    </th>
  )

  const fmt = (n) => (n||0).toLocaleString('ru-RU')

  return (
    <div>
      <div className={s.toolbar}>
        <h1 className={s.title}>Статистика</h1>
        <button className={s.btnRefresh} onClick={load} disabled={loading}>
          {loading ? '...' : '↻ Обновить'}
        </button>
      </div>

      <div className={s.filters}>
        <label className={s.dateLabel}>С <input type="date" className={s.dateInput} value={dateFrom} onChange={e=>setDateFrom(e.target.value)} /></label>
        <label className={s.dateLabel}>По <input type="date" className={s.dateInput} value={dateTo} onChange={e=>setDateTo(e.target.value)} /></label>
        <button className={s.btnApply} onClick={load}>Применить</button>
        <button className={s.btnReset} onClick={()=>{setDateFrom('');setDateTo('');onSave?.({...saved,dateFrom:'',dateTo:''})}}>Сбросить</button>
      </div>

      <div className={s.tabs}>
        <button className={`${s.tab} ${tab==='dashboard'?s.activeTab:''}`} onClick={()=>setTab('dashboard')}>📊 Дашборд</button>
        <button className={`${s.tab} ${tab==='products'?s.activeTab:''}`} onClick={()=>setTab('products')}>📦 По товарам</button>
      </div>

      {tab === 'dashboard' && dashboard && (
        <div>
          {/* Сводные карточки */}
          <div className={s.summary}>
            <div className={s.card}>
              <div className={s.cardVal}>{fmt(dashboard.total_revenue)} ₽</div>
              <div className={s.cardLabel}>Выручка</div>
            </div>
            <div className={s.card}>
              <div className={s.cardVal}>{dashboard.total_orders}</div>
              <div className={s.cardLabel}>Заказов всего</div>
            </div>
            {dashboard.orders_by_status.map(st => (
              <div key={st.status} className={s.card}>
                <div className={s.cardVal}>{st.count}</div>
                <div className={s.cardLabel}>{st.label}</div>
              </div>
            ))}
          </div>

          {/* Топ по выручке */}
          {dashboard.top_by_revenue.length > 0 && (
            <div className={s.topSection}>
              <h2 className={s.sectionTitle}>🏆 Топ по выручке</h2>
              <table className={s.table}>
                <thead><tr><th>#</th><th>Товар</th><th>Кол-во</th><th>Выручка</th></tr></thead>
                <tbody>
                  {dashboard.top_by_revenue.map((r, i) => (
                    <tr key={r.product_id}>
                      <td className={s.rank}>{i+1}</td>
                      <td>{r.name}</td>
                      <td className={s.num}>{fmt(r.total_qty)}</td>
                      <td className={s.num}>{fmt(r.total_sum)} ₽</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Топ по количеству */}
          {dashboard.top_by_qty.length > 0 && (
            <div className={s.topSection}>
              <h2 className={s.sectionTitle}>📦 Топ по количеству</h2>
              <table className={s.table}>
                <thead><tr><th>#</th><th>Товар</th><th>Кол-во</th><th>Выручка</th></tr></thead>
                <tbody>
                  {dashboard.top_by_qty.map((r, i) => (
                    <tr key={r.product_id}>
                      <td className={s.rank}>{i+1}</td>
                      <td>{r.name}</td>
                      <td className={s.num}>{fmt(r.total_qty)}</td>
                      <td className={s.num}>{fmt(r.total_sum)} ₽</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {dashboard.total_orders === 0 && (
            <p className={s.msg}>Нет данных за выбранный период</p>
          )}
        </div>
      )}

      {tab === 'products' && (
        loading ? <p className={s.msg}>Загрузка...</p> : (
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
              {sorted.map(st => {
                const p = products[st.product_id]
                return (
                  <tr key={st.product_id}>
                    <td>{p ? p.name : `ID ${st.product_id}`}</td>
                    <td className={s.num}>{st.added_to_cart}</td>
                    <td className={s.num}>{st.ordered}</td>
                    <td className={`${s.num} ${st.returned>0?s.warn:''}`}>{st.returned}</td>
                    <td className={s.num}>{st.period_sold_qty||0}</td>
                    <td className={s.num}>{fmt(st.period_sold_sum||0)} ₽</td>
                    <td>
                      <button className={s.btnReturn}
                        onClick={() => api.trackReturn(st.product_id).then(load)}
                        title="Зарегистрировать возврат">↩️</button>
                    </td>
                  </tr>
                )
              })}
              {sorted.length === 0 && (
                <tr><td colSpan={7} style={{textAlign:'center',color:'#aaa',padding:20}}>Нет данных</td></tr>
              )}
            </tbody>
          </table>
        )
      )}
    </div>
  )
}
