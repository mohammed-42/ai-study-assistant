import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/services/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Plus } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { Subject } from '@/types'

export default function Dashboard() {
  const { data: subjects, isLoading } = useQuery({
    queryKey: ['subjects'],
    queryFn: () => apiFetch<Subject[]>('/subjects/'),
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Dashboard</h2>
          <p className="text-muted-foreground">Welcome back! Here&apos;s your study overview.</p>
        </div>
        <Link to="/subjects">
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            New Subject
          </Button>
        </Link>
      </div>

      {isLoading ? (
        <div className="flex h-32 items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      ) : subjects?.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>No subjects yet</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground mb-4">
              Create your first subject to start organizing your study materials.
            </p>
            <Link to="/subjects">
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                Create Subject
              </Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {subjects?.map((subject: Subject) => (
            <Card key={subject.id} className="hover:shadow-md transition-shadow">
              <CardHeader>
                <CardTitle className="text-lg">{subject.name}</CardTitle>
              </CardHeader>
              <CardContent>
                {subject.description && (
                  <p className="text-sm text-muted-foreground line-clamp-2">
                    {subject.description}
                  </p>
                )}
                <Link to={`/subjects/${subject.id}`} className="mt-4 block text-sm text-primary hover:underline">
                  View subject →
                </Link>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
