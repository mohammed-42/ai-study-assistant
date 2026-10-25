import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/services/api'
import { Button, buttonVariants } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { UploadDialog } from '@/components/upload-dialog'
import { ArrowLeft, Upload } from 'lucide-react'
import type { Subject } from '@/types'

export default function SubjectDetail() {
  const { id } = useParams<{ id: string }>()
  const [uploadOpen, setUploadOpen] = useState(false)

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
          <CardTitle className="break-words text-2xl">{subject.name}</CardTitle>
          {subject.description && (
            <CardDescription className="break-words">{subject.description}</CardDescription>
          )}
          <CardAction>
            <Button onClick={() => setUploadOpen(true)}>
              <Upload className="mr-2 h-4 w-4" />
              Upload
            </Button>
          </CardAction>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <Link to="/documents" className={buttonVariants({ variant: 'outline' })}>
              Documents
            </Link>
            <Link to="/tutor" className={buttonVariants({ variant: 'outline' })}>
              Tutor
            </Link>
            <Link to="/quizzes" className={buttonVariants({ variant: 'outline' })}>
              Quizzes
            </Link>
          </div>
        </CardContent>
      </Card>

      <UploadDialog
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        preselectedSubjectId={id}
      />
    </div>
  )
}
