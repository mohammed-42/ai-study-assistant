import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuizzes, useGenerateQuiz, useDeleteQuiz } from '@/hooks/use-quizzes'
import { useDocuments } from '@/hooks/use-documents'
import { useSubjects } from '@/hooks/use-subjects'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { ErrorState } from '@/components/error-state'
import { Badge } from '@/components/ui/badge'
import { Plus, Sparkles, Trash2, Play } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import type { QuizType, QuizDifficulty, QuizGenerateRequest } from '@/types'

interface QuizzesProps {
  subjectId?: string
}

export default function Quizzes({ subjectId }: QuizzesProps) {
  const navigate = useNavigate()
  const { data: quizzes, isLoading, isError, error, refetch } = useQuizzes(subjectId)
  const generateQuiz = useGenerateQuiz()
  const deleteQuiz = useDeleteQuiz()
  const [generateOpen, setGenerateOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)
  const [selectedSubjectId, setSelectedSubjectId] = useState(subjectId ?? '')
  const [selectedDocumentId, setSelectedDocumentId] = useState('')
  const { data: subjects, isLoading: subjectsLoading } = useSubjects(generateOpen)
  const { data: documents, isLoading: documentsLoading } = useDocuments(selectedSubjectId || undefined)
  const readyDocuments = (documents ?? []).filter((document) => document.status === 'ready')
  const hasNoSubjects = !subjectsLoading && (subjects?.length ?? 0) === 0
  const hasNoReadyDocuments =
    !!selectedSubjectId && !documentsLoading && readyDocuments.length === 0
  const [generateParams, setGenerateParams] = useState<{
    title: string
    quiz_type: QuizType
    difficulty: QuizDifficulty
    question_count: number
  }>({
    title: 'New Quiz',
    quiz_type: 'mixed',
    difficulty: 'medium',
    question_count: 5,
  })

  const handleGenerate = async () => {
    const params: QuizGenerateRequest = { ...generateParams }
    if (selectedSubjectId) params.subject_id = selectedSubjectId
    if (selectedDocumentId) params.document_id = selectedDocumentId
    try {
      await generateQuiz.mutateAsync(params)
      setGenerateOpen(false)
    } catch {
      // The mutation hook shows the readable error toast.
    }
  }

  const handleDelete = async () => {
    if (deleteTarget) {
      try {
        await deleteQuiz.mutateAsync(deleteTarget)
        setDeleteTarget(null)
      } catch {
        // The mutation hook shows the readable error toast.
      }
    }
  }

  const diffColor = (d: string) => {
    const map: Record<string, string> = { easy: 'bg-green-100 text-green-700', medium: 'bg-yellow-100 text-yellow-700', hard: 'bg-red-100 text-red-700' }
    return map[d] || 'bg-gray-100'
  }

  const typeLabel = (t: string) => {
    const map: Record<string, string> = { mcq: 'MCQ', short_answer: 'Short Answer', mixed: 'Mixed' }
    return map[t] || t
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Quizzes</h1>
        <Button onClick={() => setGenerateOpen(true)} className="shrink-0">
          <Sparkles className="mr-2 h-4 w-4" />
          Generate Quiz
        </Button>
      </div>

      {isError ? (
        <ErrorState
          title="Failed to load quizzes"
          message={error instanceof Error ? error.message : undefined}
          onRetry={() => refetch()}
        />
      ) : isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-40 w-full" />
          ))}
        </div>
      ) : !quizzes || quizzes.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>No quizzes yet</CardTitle>
            <CardDescription>
              Generate AI-powered quizzes from your study materials.
            </CardDescription>
          </CardHeader>
          <CardFooter>
            <Button onClick={() => setGenerateOpen(true)} className="shrink-0">
              <Plus className="mr-2 h-4 w-4" />
              Generate First Quiz
            </Button>
          </CardFooter>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {quizzes.map((quiz: any) => (
            <Card key={quiz.id} className="flex flex-col">
              <CardHeader>
                <div className="flex items-start justify-between">
                  <CardTitle className="min-w-0 flex-1 break-words text-base">{quiz.title}</CardTitle>
                </div>
                <CardDescription className="mt-2 flex flex-wrap gap-2">
                  <Badge className={diffColor(quiz.difficulty)}>{quiz.difficulty}</Badge>
                  <Badge variant="outline">{typeLabel(quiz.quiz_type)}</Badge>
                  <Badge variant="secondary">{quiz.question_count} questions</Badge>
                </CardDescription>
              </CardHeader>
              <CardContent className="flex-1">
                <p className="text-xs text-muted-foreground">
                  Created {new Date(quiz.created_at).toLocaleDateString()}
                </p>
              </CardContent>
              <CardFooter className="gap-2">
                <Button variant="outline" size="sm" className="flex-1" onClick={() => navigate(`/quizzes/${quiz.id}`)}>
                  <Play className="mr-1 h-3 w-3" /> Take
                </Button>
                <Button variant="ghost" size="icon" aria-label={`Delete quiz ${quiz.title}`} onClick={() => setDeleteTarget(quiz.id)}>
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={generateOpen} onOpenChange={setGenerateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Generate Quiz</DialogTitle>
            <DialogDescription>
              Create a quiz from your study materials using Gemini.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="quiz-subject">Subject</Label>
              <Select
                value={selectedSubjectId}
                onValueChange={(value) => {
                  setSelectedSubjectId(value ?? '')
                  setSelectedDocumentId('')
                }}
                items={subjects?.map((subject) => ({ value: subject.id, label: subject.name }))}
                disabled={generateQuiz.isPending}
              >
                <SelectTrigger id="quiz-subject" className="w-full" aria-required="true">
                  <SelectValue placeholder={subjectsLoading ? 'Loading subjects...' : 'Select a subject'} />
                </SelectTrigger>
                <SelectContent>
                  {subjects?.map((subject) => (
                    <SelectItem key={subject.id} value={subject.id}>
                      {subject.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {hasNoSubjects && (
                <p className="text-sm text-muted-foreground">
                  You need a subject first.{' '}
                  <Link
                    to="/subjects"
                    className="underline underline-offset-4 hover:text-foreground"
                    onClick={() => setGenerateOpen(false)}
                  >
                    Create a subject
                  </Link>
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="quiz-document">Document (optional)</Label>
              <Select
                value={selectedDocumentId || 'all'}
                onValueChange={(value) => setSelectedDocumentId(value === 'all' ? '' : (value ?? ''))}
                items={[
                  { value: 'all', label: 'All ready documents in subject' },
                  ...readyDocuments.map((document) => ({ value: document.id, label: document.name })),
                ]}
                disabled={generateQuiz.isPending || !selectedSubjectId || documentsLoading}
              >
                <SelectTrigger id="quiz-document" className="w-full">
                  <SelectValue placeholder={documentsLoading ? 'Loading documents...' : 'All ready documents in subject'} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All ready documents in subject</SelectItem>
                  {readyDocuments.map((document) => (
                    <SelectItem key={document.id} value={document.id}>
                      {document.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {hasNoReadyDocuments && (
                <p className="text-sm text-muted-foreground">
                  No ready documents in this subject.{' '}
                  <Link
                    to={`/subjects/${selectedSubjectId}`}
                    className="underline underline-offset-4 hover:text-foreground"
                    onClick={() => setGenerateOpen(false)}
                  >
                    Upload or check documents
                  </Link>
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="quiz-title">Title</Label>
              <Input id="quiz-title" value={generateParams.title} onChange={(e) => setGenerateParams(p => ({ ...p, title: e.target.value }))} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="quiz-type">Question Type</Label>
              <Select value={generateParams.quiz_type} onValueChange={(v) => setGenerateParams(p => ({ ...p, quiz_type: v as QuizType }))}>
                <SelectTrigger id="quiz-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="mcq">Multiple Choice (MCQ)</SelectItem>
                  <SelectItem value="short_answer">Short Answer</SelectItem>
                  <SelectItem value="mixed">Mixed</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="quiz-difficulty">Difficulty</Label>
              <Select value={generateParams.difficulty} onValueChange={(v) => setGenerateParams(p => ({ ...p, difficulty: v as QuizDifficulty }))}>
                <SelectTrigger id="quiz-difficulty">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="easy">Easy</SelectItem>
                  <SelectItem value="medium">Medium</SelectItem>
                  <SelectItem value="hard">Hard</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="quiz-count">Number of Questions</Label>
              <Input id="quiz-count" type="number" min={1} max={20} value={generateParams.question_count} onChange={(e) => setGenerateParams(p => ({ ...p, question_count: parseInt(e.target.value) || 5 }))} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setGenerateOpen(false)}>Cancel</Button>
            <Button onClick={handleGenerate} disabled={generateQuiz.isPending || !selectedSubjectId}>
              {generateQuiz.isPending ? 'Generating...' : 'Generate'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Quiz</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete the quiz and all attempts. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
