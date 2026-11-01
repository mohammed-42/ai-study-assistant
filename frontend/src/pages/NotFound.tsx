import { Link } from 'react-router-dom'
import { Home, SearchX } from 'lucide-react'

import { buttonVariants } from '@/components/ui/button'

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4 text-center">
      <SearchX className="h-14 w-14 text-muted-foreground" aria-hidden="true" />
      <h1 className="mt-4 text-3xl font-bold tracking-tight">Page not found</h1>
      <p className="mt-2 max-w-md text-muted-foreground">
        The page you are looking for does not exist or may have moved.
      </p>
      <Link to="/" className={buttonVariants({ className: 'mt-6' })}>
        <Home className="mr-2 h-4 w-4" />
        Back to home
      </Link>
    </div>
  )
}
