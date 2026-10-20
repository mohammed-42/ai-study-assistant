import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/services/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Plus, FileText, BookOpen, CircleHelp, CalendarDays, CheckCircle, TrendingUp } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { Subject } from '@/types'
import type { DashboardData } from '@/types'

export default function Dashboard() {
  const { data: subjects, isLoading: loadingSubjects } = useQuery({
    queryKey: ['subjects'],
    queryFn: () => apiFetch<Subject[]>('/subjects/'),
  })

  const { data: dashboard, isLoading: loadingDashboard } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => apiFetch<DashboardData>('/planner/dashboard'),
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
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

      {loadingDashboard ? (
        <div className="flex h-24 items-center justify-center">
          <div className="h-6 w-6 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      ) : dashboard && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Documents</CardTitle>
              <FileText className="h-4 w-4 text-muted-foreground" />
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
              <CalendarDays className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{dashboard.active_plans_count}</div>
              <p className="text-xs text-muted-foreground">active</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Today's Tasks</CardTitle>
              <CheckCircle className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{dashboard.today_pending_tasks}</div>
              <p className="text-xs text-muted-foreground">pending</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Plan Progress</CardTitle>
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{dashboard.plan_progress?.percentage ?? 0}%</div>
              <p className="text-xs text-muted-foreground">
                {dashboard.plan_progress?.completed ?? 0}/{dashboard.plan_progress?.total ?? 0} tasks
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        {dashboard?.today_tasks_summary?.length && dashboard.today_tasks_summary.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Today's Tasks</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
            {(dashboard.today_tasks_summary || []).map(task => (
                <div key={task.id} className="flex items-center justify-between text-sm">
                  <span className="flex items-center gap-2">
                    <CircleHelp className="h-4 w-4 text-muted-foreground" />
                    {task.topic}
                  </span>
                  <Badge variant="outline">{task.estimated_minutes} min</Badge>
                </div>
              ))}
              <Link to="/planner">
                <Button variant="link" size="sm" className="mt-2">View all plans →</Button>
              </Link>
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Quick Actions</CardTitle>
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
            <Link to="/planner">
              <Button variant="outline" className="w-full justify-start sm:col-span-2">
                <CalendarDays className="mr-2 h-4 w-4" /> Study Planner
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>

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
        <div>
          <h3 className="font-semibold text-lg mb-4">Your Subjects</h3>
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
        </div>
      )}
    </div>
  )
}
