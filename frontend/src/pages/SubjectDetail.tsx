import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/services/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ArrowLeft } from 'lucide-react'
import type { Subject } from '@/types'

export default function SubjectDetail() {
  const { id } = useParams<{ id: string }>()

  const { data: subject, isLoading } = useQuery({
    queryKey: ['subject', id],
    queryFn: () => apiFetch<Subject>(`/subjects/${id}`),
    enabled: !!id,
  })

  if (isLoading) {
    return (
      <div className="flex h-32 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    )
  }

  if (!subject) {
    return (
      <div className="space-y-4">
        <Link to="/subjects">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Subjects
          </Button>
        </Link>
        <Card>
          <CardContent className="pt-6">
            <p className="text-muted-foreground">Subject not found.</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <Link to="/subjects">
        <Button variant="ghost" size="sm">
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Subjects
        </Button>
      </Link>

      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">{subject.name}</CardTitle>
        </CardHeader>
        <CardContent>
          {subject.description && (
            <p className="text-muted-foreground">{subject.description}</p>
          )}
          <div className="mt-6 flex gap-3">
            <Button variant="outline" disabled>Documents (coming soon)</Button>
            <Button variant="outline" disabled>Tutor (coming soon)</Button>
            <Button variant="outline" disabled>Quizzes (coming soon)</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
