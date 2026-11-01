import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/services/api'
import { useDashboard, useUpdateTask } from '@/hooks/use-planner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  AlertCircle,
  BookOpen,
  CalendarDays,
  CheckCircle,
  CircleHelp,
  FileText,
  Plus,
  TrendingUp,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import type { DocumentStatus, Subject } from '@/types'

const documentStatusVariant: Record<
  DocumentStatus,
  'default' | 'secondary' | 'destructive' | 'outline'
> = {
  uploaded: 'outline',
  processing: 'secondary',
  ready: 'default',
  failed: 'destructive',
}

function formatDate(value: string | null) {
  if (!value) return '—'
  return new Date(value).toLocaleDateString()
}

function daysLeftLabel(days: number) {
  if (days === 0) return 'Today'
  if (days === 1) return '1 day left'
  return `${days} days left`
}

function EmptyState({ message, to, label }: { message: string; to: string; label: string }) {
  return (
    <div className="flex flex-col items-start gap-1 py-1">
      <p className="text-sm text-muted-foreground">{message}</p>
      <Link to={to} className="text-sm text-primary hover:underline">
        {label} →
      </Link>
    </div>
  )
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading dashboard">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-28 w-full" />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-48 w-full" />
        ))}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const { data: subjects, isLoading: loadingSubjects } = useQuery({
    queryKey: ['subjects'],
    queryFn: () => apiFetch<Subject[]>('/subjects/'),
  })

  const { data: dashboard, isLoading, isError, error, refetch, isFetching } = useDashboard()
  const updateTask = useUpdateTask()

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Dashboard</h2>
          <p className="text-muted-foreground">Your study overview.</p>
        </div>
        <Link to="/subjects">
          <Button>
            <Plus className="mr-2 h-4 w-4" /> New Subject
          </Button>
        </Link>
      </div>

      {isError ? (
        <Card role="alert" aria-live="polite" className="border-destructive/40">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-destructive">
              <AlertCircle className="h-4 w-4" aria-hidden="true" />
              Could not load your dashboard
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              {error instanceof Error ? error.message : 'Something went wrong. Please try again.'}
            </p>
            <Button
              variant="outline"
              onClick={() => refetch()}
              disabled={isFetching}
              aria-label="Retry loading dashboard"
            >
              {isFetching ? 'Retrying...' : 'Retry'}
            </Button>
          </CardContent>
        </Card>
      ) : isLoading ? (
        <DashboardSkeleton />
      ) : dashboard ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">Documents</CardTitle>
                <FileText className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {Object.values(dashboard.document_counts || {}).reduce((a, b) => a + b, 0)}
                </div>
                <p className="text-xs text-muted-foreground">
                  {(dashboard.document_counts?.ready || 0)} ready
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">Study Plans</CardTitle>
                <CalendarDays className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{dashboard.active_plans_count}</div>
                <p className="text-xs text-muted-foreground">active</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">Today's Tasks</CardTitle>
                <CheckCircle className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{dashboard.today_pending_tasks}</div>
                <p className="text-xs text-muted-foreground">pending</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium">Plan Progress</CardTitle>
                <TrendingUp className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{dashboard.plan_progress?.percentage ?? 0}%</div>
                <p className="text-xs text-muted-foreground">
                  {dashboard.plan_progress?.completed ?? 0}/{dashboard.plan_progress?.total ?? 0} tasks
                </p>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <section aria-labelledby="upcoming-exams-heading">
              <Card className="h-full">
                <CardHeader>
                  <CardTitle id="upcoming-exams-heading" className="text-base">
                    Upcoming Exams
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {dashboard.upcoming_exams.length === 0 ? (
                    <EmptyState
                      message="No upcoming exams."
                      to="/planner"
                      label="Create a study plan"
                    />
                  ) : (
                    dashboard.upcoming_exams.map((exam) => (
                      <Link
                        key={exam.id}
                        to={`/planner/${exam.id}`}
                        className="flex flex-wrap items-center justify-between gap-2 rounded-md p-2 text-sm hover:bg-muted"
                      >
                        <span className="min-w-0 truncate font-medium">{exam.title}</span>
                        <span className="flex items-center gap-2">
                          <span className="text-xs text-muted-foreground">
                            {formatDate(exam.exam_date)}
                          </span>
                          <Badge variant={exam.days_left <= 3 ? 'destructive' : 'secondary'}>
                            {daysLeftLabel(exam.days_left)}
                          </Badge>
                        </span>
                      </Link>
                    ))
                  )}
                  {dashboard.upcoming_exams.length > 0 && (
                    <Link to="/planner" className="inline-block text-sm text-primary hover:underline">
                      View study planner →
                    </Link>
                  )}
                </CardContent>
              </Card>
            </section>

            <section aria-labelledby="today-tasks-heading">
              <Card className="h-full">
                <CardHeader>
                  <CardTitle id="today-tasks-heading" className="text-base">
                    Today's Tasks
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {dashboard.today_tasks.length === 0 ? (
                    <EmptyState
                      message="No tasks scheduled for today."
                      to="/planner"
                      label="Open the study planner"
                    />
                  ) : (
                    dashboard.today_tasks.map((task) => (
                      <div key={task.id} className="flex items-center justify-between gap-3 rounded-md p-2 text-sm hover:bg-muted">
                        <label className="flex min-w-0 items-center gap-2">
                          <input
                            type="checkbox"
                            className="h-4 w-4 shrink-0 rounded border-border accent-primary"
                            checked={task.status === 'completed'}
                            disabled={updateTask.isPending}
                            onChange={() =>
                              updateTask.mutate({
                                taskId: task.id,
                                data: {
                                  status: task.status === 'completed' ? 'pending' : 'completed',
                                },
                              })
                            }
                            aria-label={
                              task.status === 'completed'
                                ? `Mark ${task.topic} as not done`
                                : `Mark ${task.topic} as done`
                            }
                          />
                          <span
                            className={
                              task.status === 'completed'
                                ? 'truncate text-muted-foreground line-through'
                                : 'truncate'
                            }
                          >
                            {task.topic}
                          </span>
                        </label>
                        <Badge variant="outline">{task.estimated_minutes} min</Badge>
                      </div>
                    ))
                  )}
                  {dashboard.today_tasks.length > 0 && (
                    <Link to="/planner" className="inline-block text-sm text-primary hover:underline">
                      View all plans →
                    </Link>
                  )}
                </CardContent>
              </Card>
            </section>

            <section aria-labelledby="recent-materials-heading">
              <Card className="h-full">
                <CardHeader>
                  <CardTitle id="recent-materials-heading" className="text-base">
                    Recent Materials
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {dashboard.recent_documents.length === 0 ? (
                    <EmptyState
                      message="No materials uploaded yet."
                      to="/documents"
                      label="Upload a document"
                    />
                  ) : (
                    dashboard.recent_documents.map((document) => (
                      <Link
                        key={document.id}
                        to={`/documents/${document.id}`}
                        className="flex items-center justify-between gap-3 rounded-md p-2 text-sm hover:bg-muted"
                      >
                        <span className="flex min-w-0 items-center gap-2">
                          <FileText className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                          <span className="truncate">{document.name}</span>
                        </span>
                        <Badge variant={documentStatusVariant[document.status]}>
                          {document.status}
                        </Badge>
                      </Link>
                    ))
                  )}
                  {dashboard.recent_documents.length > 0 && (
                    <Link to="/documents" className="inline-block text-sm text-primary hover:underline">
                      View all documents →
                    </Link>
                  )}
                </CardContent>
              </Card>
            </section>

            <section aria-labelledby="recent-quizzes-heading">
              <Card className="h-full">
                <CardHeader>
                  <CardTitle id="recent-quizzes-heading" className="text-base">
                    Recent Quiz Scores
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {dashboard.recent_quizzes.length === 0 ? (
                    <EmptyState
                      message="No quiz attempts yet."
                      to="/quizzes"
                      label="Take a quiz"
                    />
                  ) : (
                    dashboard.recent_quizzes.map((attempt) => (
                      <Link
                        key={attempt.id}
                        to={`/quizzes/${attempt.quiz_id}/results`}
                        className="flex items-center justify-between gap-3 rounded-md p-2 text-sm hover:bg-muted"
                      >
                        <span className="min-w-0 truncate">{attempt.quiz_title}</span>
                        <span className="flex shrink-0 items-center gap-2">
                          <span className="font-medium">{attempt.score ?? 0}%</span>
                          <span className="text-xs text-muted-foreground">
                            {formatDate(attempt.date)}
                          </span>
                        </span>
                      </Link>
                    ))
                  )}
                  {dashboard.recent_quizzes.length > 0 && (
                    <Link to="/quizzes" className="inline-block text-sm text-primary hover:underline">
                      View all quizzes →
                    </Link>
                  )}
                </CardContent>
              </Card>
            </section>

            <section aria-labelledby="plan-progress-heading">
              <Card className="h-full">
                <CardHeader>
                  <CardTitle id="plan-progress-heading" className="text-base">
                    Plan Progress
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {(dashboard.plan_progress?.total ?? 0) === 0 ? (
                    <EmptyState
                      message="No study plan progress yet."
                      to="/planner"
                      label="Create a study plan"
                    />
                  ) : (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between text-sm">
                        <span className="font-medium">
                          {dashboard.plan_progress.percentage}% complete
                        </span>
                        <span className="text-muted-foreground">
                          {dashboard.plan_progress.completed}/{dashboard.plan_progress.total} tasks
                        </span>
                      </div>
                      <div
                        className="h-2 w-full overflow-hidden rounded-full bg-muted"
                        role="progressbar"
                        aria-label="Plan progress"
                        aria-valuenow={dashboard.plan_progress.percentage}
                        aria-valuemin={0}
                        aria-valuemax={100}
                      >
                        <div
                          className="h-full bg-primary transition-all"
                          style={{ width: `${dashboard.plan_progress.percentage}%` }}
                        />
                      </div>
                      <Link to="/planner" className="inline-block text-sm text-primary hover:underline">
                        View study planner →
                      </Link>
                    </div>
                  )}
                </CardContent>
              </Card>
            </section>

            <section aria-labelledby="quick-actions-heading">
              <Card className="h-full">
                <CardHeader>
                  <CardTitle id="quick-actions-heading" className="text-base">
                    Quick Actions
                  </CardTitle>
                </CardHeader>
                <CardContent className="grid gap-2 sm:grid-cols-2">
                  <Link to="/subjects">
                    <Button variant="outline" className="w-full justify-start">
                      <BookOpen className="mr-2 h-4 w-4" /> Subjects
                    </Button>
                  </Link>
                  <Link to="/documents">
                    <Button variant="outline" className="w-full justify-start">
                      <FileText className="mr-2 h-4 w-4" /> Documents
                    </Button>
                  </Link>
                  <Link to="/notes">
                    <Button variant="outline" className="w-full justify-start">
                      <CalendarDays className="mr-2 h-4 w-4" /> Notes
                    </Button>
                  </Link>
                  <Link to="/quizzes">
                    <Button variant="outline" className="w-full justify-start">
                      <CircleHelp className="mr-2 h-4 w-4" /> Quizzes
                    </Button>
                  </Link>
                  <Link to="/planner" className="sm:col-span-2">
                    <Button variant="outline" className="w-full justify-start">
                      <CalendarDays className="mr-2 h-4 w-4" /> Study Planner
                    </Button>
                  </Link>
                </CardContent>
              </Card>
            </section>
          </div>
        </>
      ) : null}

      {loadingSubjects ? (
        <div className="flex h-24 items-center justify-center">
          <div className="h-6 w-6 animate-spin rounded-full border-4 border-primary border-t-transparent" />
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
                <Plus className="mr-2 h-4 w-4" /> Create Subject
              </Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <section aria-labelledby="subjects-heading">
          <h3 id="subjects-heading" className="font-semibold text-lg mb-4">
            Your Subjects
          </h3>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {subjects?.map((subject: Subject) => (
              <Card key={subject.id} className="hover:shadow-md transition-shadow">
                <CardHeader>
                  <CardTitle className="text-lg">{subject.name}</CardTitle>
                </CardHeader>
                <CardContent>
                  {subject.description && (
                    <p className="text-sm text-muted-foreground line-clamp-2 mb-4">
                      {subject.description}
                    </p>
                  )}
                  <Link to={`/subjects/${subject.id}`} className="block text-sm text-primary hover:underline">
                    View subject →
                  </Link>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
