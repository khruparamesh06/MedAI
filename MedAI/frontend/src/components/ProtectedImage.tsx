import { FileImage } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../api/endpoints'

type Loaded = { id: number; src: string | null; failed: boolean }

/**
 * X-ray images are private: they are fetched with the bearer token and shown via a temporary
 * object URL, never through a public static link.
 */
export function ProtectedImage({ xrayId, alt, className = '' }: { xrayId: number; alt: string; className?: string }) {
  const [loaded, setLoaded] = useState<Loaded | null>(null)

  useEffect(() => {
    let url: string | null = null
    let cancelled = false
    api.xrayImage(xrayId)
      .then((blob) => {
        if (cancelled) return
        url = URL.createObjectURL(blob)
        setLoaded({ id: xrayId, src: url, failed: false })
      })
      .catch(() => { if (!cancelled) setLoaded({ id: xrayId, src: null, failed: true }) })
    return () => {
      cancelled = true
      if (url) URL.revokeObjectURL(url)
    }
  }, [xrayId])

  const current = loaded?.id === xrayId ? loaded : null
  if (current?.failed) {
    return <div className={`xray-frame xray-missing ${className}`}><FileImage size={28} aria-hidden /><span>Image unavailable</span></div>
  }
  return (
    <div className={`xray-frame ${className}`}>
      {current?.src ? <img src={current.src} alt={alt} /> : <div className="xray-placeholder" aria-label="Loading image" />}
    </div>
  )
}
