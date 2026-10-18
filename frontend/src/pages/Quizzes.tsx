import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuizzes, useGenerateQuiz, useDeleteQuiz } from '@/hooks/use-quizzes'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
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
import type { QuizType, QuizDifficulty } from '@/types'

interface QuizzesProps {
  subjectId?: string
}

export default function Quizzes({ subjectId }: QuizzesProps) {
  const navigate = useNavigate()
  const { data: quizzes, isLoading } = useQuizzes(subjectId)
  const generateQuiz = useGenerateQuiz()
  const deleteQuiz = useDeleteQuiz()
  const [generateOpen, setGenerateOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)
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
    const params = {
      ...generateParams,
    } as Record<string, unknown>
    if (subjectId) params.subject_id = subjectId
    await generateQuiz.mutateAsync(params as any)
    setGenerateOpen(false)
  }

  const handleDelete = async () => {
    if (deleteTarget) {
      await deleteQuiz.mutateAsync(deleteTarget)
      setDeleteTarget(null)
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
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold tracking-tight">Quizzes</h2>
        <Button onClick={() => setGenerateOpen(true)}>
          <Sparkles className="mr-2 h-4 w-4" />
          Generate Quiz
        </Button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
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
            <Button onClick={() => setGenerateOpen(true)}>
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
                  <CardTitle className="text-base flex-1">{quiz.title}</CardTitle>
                </div>
                <CardDescription className="flex gap-2 mt-2">
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
                <Button variant="ghost" size="icon" onClick={() => setDeleteTarget(quiz.id)}>
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
            <Button onClick={handleGenerate} disabled={generateQuiz.isPending}>
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
