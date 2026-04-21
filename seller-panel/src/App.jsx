import { useState, useEffect } from 'react'
import { api } from './api.js'
import ProductsPage from './pages/ProductsPage.jsx'
import OrdersPage from './pages/OrdersPage.jsx'
import ImportPage from './pages/ImportPage.jsx'
import StatsPage from './pages/StatsPage.jsx'
import SettingsPage from './pages/SettingsPage.jsx'
import s from './App.module.css'

const NAV = [
  { id: 'products', label: '📦 Товары' },
  { id: 'orders',   label: '🧾 Заказы' },
  { id: 'stats',    label: '📊 Статистика' },
  { id: 'import',   label: '📥 Импорт' },
  { id: 'settings', label: '⚙️ Настройки' },
]

export default function App() {
  const [page, setPage]       = useState('products')
  const [shopName, setShopName] = useState('Kaza Shop')
  const [logoUrl, setLogoUrl]   = useState(null)
  const [statsState, setStatsState] = useState({ dateFrom:'', dateTo:'', stats:[], products:{} })

  useEffect(() => {
    api.getSettings().then(s => {
      setShopName(s.shop_name || 'Kaza Shop')
      setLogoUrl(s.logo_url ? `${api.BASE}${s.logo_url}` : null)
    }).catch(() => {})
    return () => clearInterval(t)
  }, [])

  function onSettingsSaved(cfg) {
    setShopName(cfg.shop_name || 'Kaza Shop')
    setLogoUrl(cfg.logo_url ? api.BASE + cfg.logo_url : null)
  }

  return (
    <div className={s.layout}>
      <aside className={s.sidebar}>
        <div className={s.logo}>
          {logoUrl && <img src={logoUrl} className={s.logoImg} alt="" />}
          <span className={s.logoText} style={{cursor:'pointer'}} onClick={()=>setPage('products')}>{shopName}</span>
        </div>
      </aside>
      <main className={s.main}>
        {page === 'products' && <ProductsPage />}
        {page === 'orders'   && <OrdersPage />}
        {page === 'stats' && <StatsPage saved={statsState} onSave={setStatsState} />}
        {page === 'import'   && <ImportPage />}
        {page === 'settings' && <SettingsPage onSaved={onSettingsSaved} />}
      </main>
    </div>
  )
}
