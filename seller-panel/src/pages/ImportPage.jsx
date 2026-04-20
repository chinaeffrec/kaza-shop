import { useState, useRef } from 'react'
import { api } from '../api.js'
import s from './ImportPage.module.css'

export default function ImportPage() {
  const [dragging, setDragging]   = useState(false)
  const [file, setFile]           = useState(null)
  const [result, setResult]       = useState(null)
  const [error, setError]         = useState(null)
  const [loading, setLoading]     = useState(false)
  const inputRef                  = useRef()

  function onDrop(e) {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) pickFile(f)
  }

  function pickFile(f) {
    if (!f.name.endsWith('.xlsx')) {
      setError('Только .xlsx файлы')
      return
    }
    setFile(f)
    setResult(null)
    setError(null)
  }

  async function handleUpload() {
    if (!file) return
    setLoading(true)
    setResult(null)
    setError(null)
    try {
      const res = await api.importXlsx(file)
      setResult(res)
      setFile(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h1 className={s.title}>Импорт каталога</h1>
      <p className={s.hint}>
        Загрузите .xlsx файл с колонками:{' '}
        <code>category</code>, <code>subcategory</code>, <code>name</code>,{' '}
        <code>price</code>, <code>description</code>, <code>characteristics</code>, <code>is_active</code>
      </p>

      <div
        className={`${s.dropzone} ${dragging ? s.dragging : ''} ${file ? s.hasFile : ''}`}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".xlsx"
          style={{ display: 'none' }}
          onChange={e => e.target.files[0] && pickFile(e.target.files[0])}
        />
        {file ? (
          <div className={s.fileInfo}>
            <span className={s.fileIcon}>📄</span>
            <span className={s.fileName}>{file.name}</span>
            <span className={s.fileSize}>{(file.size / 1024).toFixed(1)} KB</span>
          </div>
        ) : (
          <div className={s.dropText}>
            <span className={s.dropIcon}>📥</span>
            <span>Перетащите .xlsx файл сюда</span>
            <span className={s.or}>или нажмите для выбора</span>
          </div>
        )}
      </div>

      {file && (
        <button className={s.btnUpload} onClick={handleUpload} disabled={loading}>
          {loading ? 'Загрузка...' : '⬆️ Загрузить'}
        </button>
      )}

      {result && (
        <div className={s.success}>
          ✅ Импорт завершён: добавлено товаров — <strong>{result.created}</strong>
        </div>
      )}

      {error && (
        <div className={s.errorBox}>
          ❌ {error}
        </div>
      )}

      <div className={s.template}>
        <h2 className={s.sectionTitle}>Шаблон файла</h2>
        <table className={s.tpl}>
          <thead>
            <tr>
              <th>category</th>
              <th>subcategory</th>
              <th>name</th>
              <th>price</th>
              <th>description</th>
              <th>characteristics</th>
              <th>is_active</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Электроника</td>
              <td>Смартфоны</td>
              <td>iPhone 16</td>
              <td>89990</td>
              <td>Флагман Apple</td>
              <td>RAM: 8GB, ROM: 128GB</td>
              <td>True</td>
            </tr>
            <tr>
              <td>Напитки</td>
              <td>Соки</td>
              <td>Апельсиновый сок</td>
              <td>120</td>
              <td>Свежевыжатый</td>
              <td></td>
              <td>True</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}
