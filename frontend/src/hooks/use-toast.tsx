import { useEffect, useState } from 'react'

type ToastProps = {
  id: string
  title?: string
  description?: string
  variant?: 'default' | 'destructive'
}

const toasts = new Map<string, ToastProps>()

function forceUpdate() {
  window.dispatchEvent(new Event('toast-changed'))
}

export function toast(props: Omit<ToastProps, 'id'>) {
  const id = Math.random().toString(36).slice(2)
  toasts.set(id, { ...props, id })
  setTimeout(() => {
    toasts.delete(id)
    forceUpdate()
  }, 5000)
  forceUpdate()
}

export function useToast() {
  const [, setToasts] = useState<string[]>([])

  useEffect(() => {
    const handler = () => setToasts([...toasts.keys()])
    window.addEventListener('toast-changed', handler)
    return () => window.removeEventListener('toast-changed', handler)
  }, [])

  return { toast, toasts: Array.from(toasts.values()) }
}

export function Toaster() {
  const [list, setList] = useState<ToastProps[]>([])

  useEffect(() => {
    const update = () => setList([...toasts.values()])
    window.addEventListener('toast-changed', update)
    return () => window.removeEventListener('toast-changed', update)
  }, [])

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {list.map((t) => (
        <div
          key={t.id}
          className={`rounded-md border px-4 py-3 shadow-lg bg-background text-foreground ${
            t.variant === 'destructive' ? 'border-destructive' : ''
          }`}
        >
          {t.title && <div className="text-sm font-semibold">{t.title}</div>}
          {t.description && <div className="text-sm text-muted-foreground">{t.description}</div>}
        </div>
      ))}
    </div>
  )
}
