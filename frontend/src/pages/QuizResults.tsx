import { useParams, useNavigate } from 'react-router-dom'
import { useQuiz, useQuizSummary } from '@/hooks/use-quizzes'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ArrowLeft, Trophy, BarChart3 } from 'lucide-react'
import type { QuizAttempt } from '@/types'

export default function QuizResults() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: quiz, isLoading } = useQuiz(id!)
  const { data: summary, isLoading: loadingSummary } = useQuizSummary(id!)

  if (isLoading || loadingSummary) {
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

  const recentAttempts: QuizAttempt[] = summary?.recent_attempts ?? []

  return (
    <div className="space-y-6">
      <Button variant="ghost" size="sm" onClick={() => navigate('/quizzes')}>
        <ArrowLeft className="mr-2 h-4 w-4" /> Back to Quizzes
      </Button>

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{quiz.title}</h1>
          <p className="text-muted-foreground mt-1">
            {quiz.question_count} questions · {quiz.difficulty} · {quiz.quiz_type}
          </p>
        </div>
        <Button onClick={() => navigate(`/quizzes/${id}`)}>
          Take Quiz
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Attempts</CardTitle>
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{summary?.total_attempts ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Average Score</CardTitle>
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{summary?.average_score ?? '—'}%</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Best Score</CardTitle>
            <Trophy className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{summary?.best_score ?? '—'}%</div>
          </CardContent>
        </Card>
      </div>

      {recentAttempts.length > 0 ? (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold">Recent Attempts</h2>
          {recentAttempts.map((attempt) => (
            <Card key={attempt.id}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0">
                <div>
                  <CardTitle className="text-base">
                    Attempt {recentAttempts.indexOf(attempt) + 1}
                  </CardTitle>
                  <CardDescription>
                    {new Date(attempt.created_at).toLocaleString()}
                  </CardDescription>
                </div>
                <div className="text-right">
                  <div className={`text-2xl font-bold ${
                    (attempt.score ?? 0) >= 70 ? 'text-green-600' :
                    (attempt.score ?? 0) >= 40 ? 'text-yellow-600' : 'text-red-600'
                  }`}>
                    {attempt.score ?? 0}%
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {attempt.correct_answers}/{attempt.total_questions} correct
                  </p>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {attempt.responses.map((resp) => {
                    const q = quiz.questions?.find(q => q.id === resp.question_id)
                    if (!q) return null
                    return (
                      <div key={resp.question_id} className={`flex items-start gap-3 text-sm rounded-md p-2 ${resp.is_correct ? 'bg-green-50' : 'bg-red-50'}`}>
                        {resp.is_correct ? (
                          <Badge variant="outline" className="bg-green-100 text-green-700 shrink-0">✓</Badge>
                        ) : (
                          <Badge variant="outline" className="bg-red-100 text-red-700 shrink-0">✗</Badge>
                        )}
                        <div className="flex-1 min-w-0">
                          <p className="font-medium truncate">{q.question_text}</p>
                          {q.question_type === 'mcq' && resp.selected_option_index !== null && (
                            <p className="text-xs text-muted-foreground">
                              Your: {q.options?.[resp.selected_option_index] ?? '?'}
                              {!resp.is_correct && q.options && resp.correct_option_index !== null && (
                                <span className="text-green-700 ml-1">→ {q.options[resp.correct_option_index]}</span>
                              )}
                            </p>
                          )}
                          {q.question_type === 'short_answer' && (
                            <p className="text-xs text-muted-foreground">
                              Your: {resp.user_answer ?? '(none)'}
                              {!resp.is_correct && resp.model_answer && (
                                <span className="text-green-700 ml-1">→ {resp.model_answer}</span>
                              )}
                            </p>
                          )}
                          {q.explanation && <p className="text-xs text-muted-foreground italic mt-1">{q.explanation}</p>}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>No attempts yet</CardTitle>
            <CardDescription>Take this quiz to see your results here.</CardDescription>
          </CardHeader>
          <CardFooter>
            <Button onClick={() => navigate(`/quizzes/${id}`)}>Take Quiz</Button>
          </CardFooter>
        </Card>
      )}
    </div>
  )
}
