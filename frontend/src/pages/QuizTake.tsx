import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuiz, useSubmitQuiz } from '@/hooks/use-quizzes'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ArrowLeft, CheckCircle2, XCircle } from 'lucide-react'
import type { QuizQuestion } from '@/types'

export default function QuizTake() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: quiz, isLoading } = useQuiz(id!)
  const submitQuiz = useSubmitQuiz()
  const [answers, setAnswers] = useState<Record<string, number | string | null>>({})
  const [submitted, setSubmitted] = useState(false)
  const [result, setResult] = useState<any>(null)

  useEffect(() => {
    setAnswers({})
    setSubmitted(false)
    setResult(null)
  }, [id])

  const handleSelect = (questionId: string, index: number) => {
    setAnswers(a => ({ ...a, [questionId]: index }))
  }

  const handleTextChange = (questionId: string, value: string) => {
    setAnswers(a => ({ ...a, [questionId]: value }))
  }

  const handleSubmit = async () => {
    if (!quiz || !id) return
    const responses = (quiz.questions || []).map((q: QuizQuestion) => {
      const ans = answers[q.id]
      if (q.question_type === 'mcq') {
        return { question_id: q.id, selected_option_index: ans as number }
      }
      return { question_id: q.id, user_answer: ans as string }
    })
    const res = await submitQuiz.mutateAsync({ quizId: id, data: { responses } })
    setResult(res)
    setSubmitted(true)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    )
  }

  if (!quiz) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-4">
        <p className="text-muted-foreground">Quiz not found</p>
        <Button onClick={() => navigate('/quizzes')}>Back to Quizzes</Button>
      </div>
    )
  }

  const questions: QuizQuestion[] = quiz.questions || []

  if (submitted && result) {
    const score = result.score ?? 0
    const total = result.total_questions
    const correct = result.correct_answers
    return (
      <div className="space-y-6">
        <Button variant="ghost" size="sm" onClick={() => navigate('/quizzes')}>
          <ArrowLeft className="mr-2 h-4 w-4" /> Back to Quizzes
        </Button>

        <Card>
          <CardHeader>
            <CardTitle className="text-center">Quiz Results</CardTitle>
            <CardDescription className="text-center">
              {quiz.title}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col items-center gap-4 py-6">
              <div className={`text-6xl font-bold ${score >= 70 ? 'text-green-600' : score >= 40 ? 'text-yellow-600' : 'text-red-600'}`}>
                {score}%
              </div>
              <p className="text-lg text-muted-foreground">
                {correct} out of {total} correct
              </p>
              <Button onClick={() => navigate(`/quizzes/${id}`)}>Retry Quiz</Button>
            </div>

            <div className="space-y-4 mt-6">
              <h3 className="font-semibold">Detailed Results</h3>
              {result.responses.map((resp: any, i: number) => {
                const q = questions[i]
                if (!q) return null
                return (
                  <div key={q.id} className={`rounded-lg border p-4 ${resp.is_correct ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'}`}>
                    <div className="flex items-start gap-3">
                      {resp.is_correct ? <CheckCircle2 className="h-5 w-5 text-green-600 mt-0.5 shrink-0" /> : <XCircle className="h-5 w-5 text-red-600 mt-0.5 shrink-0" />}
                      <div className="flex-1">
                        <p className="font-medium">{q.question_text}</p>
                        {q.question_type === 'mcq' && resp.selected_option_index !== null && (
                          <p className="text-sm text-muted-foreground mt-1">
                            Your answer: {q.options?.[resp.selected_option_index] ?? 'N/A'}
                            {!resp.is_correct && (
                              <span className="ml-2 text-green-700 font-medium">
                                → Correct: {q.options?.[resp.correct_option_index ?? -1]}
                              </span>
                            )}
                          </p>
                        )}
                        {q.question_type === 'short_answer' && (
                          <div className="text-sm mt-1 space-y-1">
                            <p><span className="text-muted-foreground">Your answer:</span> {resp.user_answer ?? '(no answer)'}</p>
                            {!resp.is_correct && <p><span className="text-muted-foreground">Expected:</span> {resp.model_answer}</p>}
                          </div>
                        )}
                        {resp.explanation && (
                          <p className="text-sm text-muted-foreground mt-2 italic">{resp.explanation}</p>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <Button variant="ghost" size="sm" onClick={() => navigate('/quizzes')}>
        <ArrowLeft className="mr-2 h-4 w-4" /> Back
      </Button>

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{quiz.title}</h1>
          <div className="flex gap-2 mt-2">
            <Badge variant="outline">{quiz.quiz_type}</Badge>
            <Badge className={quiz.difficulty === 'easy' ? 'bg-green-100 text-green-700' : quiz.difficulty === 'hard' ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'}>
              {quiz.difficulty}
            </Badge>
            <Badge variant="secondary">{questions.length} questions</Badge>
          </div>
        </div>
      </div>

      <div className="space-y-4">
        {questions.map((q, idx) => (
          <Card key={q.id}>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <span className="bg-primary text-primary-foreground rounded-full w-6 h-6 inline-flex items-center justify-center text-xs">{idx + 1}</span>
                {q.question_text}
              </CardTitle>
              <CardDescription>
                {q.question_type === 'mcq' ? 'Select one answer' : 'Type your answer'}
                {q.page_start && <span className="ml-2">· Pages {q.page_start}–{q.page_end}</span>}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {q.question_type === 'mcq' && q.options ? (
                <div className="space-y-2">
                  {q.options.map((opt, i) => (
                    <button
                      key={i}
                      type="button"
                      aria-pressed={answers[q.id] === i}
                      onClick={() => handleSelect(q.id, i)}
                      className={`w-full text-left px-4 py-3 rounded-lg border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                        answers[q.id] === i
                          ? 'border-primary bg-primary/10'
                          : 'border-border hover:bg-accent'
                      }`}
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              ) : (
                <textarea
                  value={(answers[q.id] as string) ?? ''}
                  onChange={(e) => handleTextChange(q.id, e.target.value)}
                  placeholder="Type your answer here..."
                  aria-label={`Answer for question ${idx + 1}`}
                  className="w-full min-h-[100px] p-3 rounded-md border bg-background text-sm"
                />
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={() => navigate('/quizzes')}>Cancel</Button>
        <Button onClick={handleSubmit} disabled={submitQuiz.isPending || questions.some(q => answers[q.id] === undefined || answers[q.id] === null)}>
          {submitQuiz.isPending ? 'Submitting...' : 'Submit Answers'}
        </Button>
      </div>
    </div>
  )
}
