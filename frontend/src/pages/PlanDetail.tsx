import { usePlannerPlan, useGenerateSchedule, useRegenerateSchedule, useUpdateTask } from '@/hooks/use-planner'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Calendar, Clock, CheckCircle, Loader2, RotateCw } from 'lucide-react'
import { useParams, Link } from 'react-router-dom'
import { toast } from '@/hooks/use-toast'
import type { StudyTask } from '@/types'
import { useState } from 'react'

export default function PlanDetail() {
  const { id } = useParams<{ id: string }>()
  const { data: plan, isLoading } = usePlannerPlan(id!)
  const generate = useGenerateSchedule()
  const regenerate = useRegenerateSchedule()
  const updateTask = useUpdateTask()
  const [generating, setGenerating] = useState(false)

  if (isLoading) {
    return (
      <div className="flex h-32 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    )
  }

  if (!plan) {
    return (
      <Card>
        <CardHeader><CardTitle>Plan not found</CardTitle></CardHeader>
        <CardContent>
          <Link to="/planner"><Button variant="outline">Back to Plans</Button></Link>
        </CardContent>
      </Card>
    )
  }

  const tasks = plan.tasks || []
  const pendingTasks = tasks.filter(t => t.status === 'pending' || t.status === 'in_progress')
  const completedTasks = tasks.filter(t => t.status === 'completed')

  const handleGenerate = async () => {
    setGenerating(true)
    try {
      await generate.mutateAsync(id!)
      toast({ title: 'Schedule generated', description: 'Your study tasks have been scheduled.' })
    } catch (err) {
      toast({ title: 'Failed', description: err instanceof Error ? err.message : 'Could not generate schedule', variant: 'destructive' })
    } finally {
      setGenerating(false)
    }
  }

  const handleRegenerate = async () => {
    try {
      await regenerate.mutateAsync(id!)
      toast({ title: 'Schedule regenerated', description: 'Pending tasks have been rescheduled.' })
    } catch (err) {
      toast({ title: 'Failed', description: err instanceof Error ? err.message : 'Could not regenerate', variant: 'destructive' })
    }
  }

  const handleTaskStatus = async (task: StudyTask, status: 'pending' | 'in_progress' | 'completed') => {
    try {
      await updateTask.mutateAsync({ taskId: task.id, data: { status } })
    } catch (err) {
      toast({ title: 'Failed', description: 'Could not update task', variant: 'destructive' })
    }
  }

  const daysUntilExam = plan.exam_date ? Math.ceil((new Date(plan.exam_date).getTime() - Date.now()) / 86400000) : null

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Link to="/planner"><Button variant="ghost" size="sm">← Back</Button></Link>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={handleRegenerate} disabled={regenerate.isPending}>
            <RotateCw className="mr-2 h-4 w-4" /> Regenerate
          </Button>
          <Button size="sm" onClick={handleGenerate} disabled={generating || generate.isPending}>
            {generating || generate.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
            Generate Schedule
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-xl">{plan.title}</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 text-sm">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Calendar className="h-4 w-4" />
            <span>Exam: <strong>{plan.exam_date}</strong></span>
          </div>
          <div className="flex items-center gap-2 text-muted-foreground">
            <Clock className="h-4 w-4" />
            <span>{plan.daily_minutes} min/day</span>
          </div>
          <div className="flex items-center gap-2 text-muted-foreground">
            <span>Topics: <strong>{plan.topics.length}</strong></span>
          </div>
          <div className="flex items-center gap-2 text-muted-foreground">
            <span>Days until exam: <strong>{daysUntilExam ?? '—'}</strong></span>
          </div>
          <div className="sm:col-span-2 lg:col-span-4 flex flex-wrap gap-1 mt-1">
            {plan.preferred_days.map(d => (
              <Badge key={d} variant="outline" className="capitalize">{d.slice(0, 3)}</Badge>
            ))}
          </div>
        </CardContent>
      </Card>

      {pendingTasks.length > 0 && (
        <div className="space-y-3">
          <h3 className="font-semibold text-lg">Upcoming Tasks</h3>
          {pendingTasks.map(task => (
            <Card key={task.id}>
              <CardContent className="p-4 flex items-center justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{task.topic}</span>
                    <Badge variant={task.status === 'in_progress' ? 'default' : 'secondary'} className="text-xs">
                      {task.status}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-4 mt-1 text-sm text-muted-foreground">
                    {task.scheduled_date && (
                      <span className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" /> {task.scheduled_date}
                      </span>
                    )}
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3" /> {task.estimated_minutes} min
                    </span>
                  </div>
                  {task.reason && (
                    <p className="text-xs text-muted-foreground mt-1">{task.reason}</p>
                  )}
                </div>
                <div className="flex gap-2">
                  <Button
                    variant={task.status === 'in_progress' ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => handleTaskStatus(task, 'in_progress')}
                    disabled={updateTask.isPending}
                  >
                    Start
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-green-600 hover:text-green-700"
                    onClick={() => handleTaskStatus(task, 'completed')}
                    disabled={updateTask.isPending}
                  >
                    <CheckCircle className="h-4 w-4 mr-1" /> Done
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {completedTasks.length > 0 && (
        <div className="space-y-3">
          <h3 className="font-semibold text-lg text-muted-foreground">Completed ({completedTasks.length})</h3>
          {completedTasks.slice(-5).reverse().map(task => (
            <Card key={task.id}>
              <CardContent className="p-4 flex items-center gap-4 text-sm text-muted-foreground">
                <CheckCircle className="h-4 w-4 text-green-500 shrink-0" />
                <span className="flex-1 line-through">{task.topic}</span>
                {task.scheduled_date && <span>{task.scheduled_date}</span>}
                {task.actual_minutes && <span>{task.actual_minutes} min</span>}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {tasks.length === 0 && (
        <Card>
          <CardHeader><CardTitle>No tasks yet</CardTitle></CardHeader>
          <CardContent>
            <p className="text-muted-foreground mb-4">Generate a study schedule to create tasks for your topics.</p>
            <Button onClick={handleGenerate} disabled={generating || generate.isPending}>
              {generating || generate.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
              Generate Schedule
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function Plus({ className }: { className?: string }) {
  return <svg className={className} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
}
