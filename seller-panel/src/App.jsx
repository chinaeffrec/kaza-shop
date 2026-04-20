import { useState } from 'react'
import ProductsPage from './pages/ProductsPage.jsx'
import OrdersPage from './pages/OrdersPage.jsx'
import ImportPage from './pages/ImportPage.jsx'
import styles from './App.module.css'

const NAV = [
  { id: 'products', label: '📦 Товары' },
  { id: 'orders',   label: '🧾 Заказы' },
  { id: 'import',   label: '📥 Импорт' },
]

export default function App() {
  const [page, setPage] = useState('products')

  return (
    <div className={styles.layout}>
      <aside className={styles.sidebar}>
        <div className={styles.logo}>Kaza Shop</div>
        <nav>
          {NAV.map(n => (
            <button
              key={n.id}
              className={`${styles.navBtn} ${page === n.id ? styles.active : ''}`}
              onClick={() => setPage(n.id)}
            >
              {n.label}
            </button>
          ))}
        </nav>
      </aside>
      <main className={styles.main}>
        {page === 'products' && <ProductsPage />}
        {page === 'orders'   && <OrdersPage />}
        {page === 'import'   && <ImportPage />}
      </main>
    </div>
  )
}
