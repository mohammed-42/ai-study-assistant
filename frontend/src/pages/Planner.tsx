import { usePlannerPlans, useDeletePlan, useCreatePlan } from '@/hooks/use-planner'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { ErrorState } from '@/components/error-state'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Plus, Trash2, Calendar, Clock } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'
import { toast } from '@/hooks/use-toast'
import type { StudyPlan } from '@/types'

const planFormSchema = z.object({
  title: z.string().min(1, 'Title is required').max(500),
  exam_date: z.string().min(1, 'Exam date is required'),
  daily_minutes: z.coerce.number().min(15).max(480),
  preferred_days: z.array(z.string()),
  topics: z.string().min(1, 'Add at least one topic'),
})

type PlanFormValues = z.infer<typeof planFormSchema>

const DAY_OPTIONS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']

export default function Planner() {
  const { data: plans, isLoading, isError, error, refetch } = usePlannerPlans()
  const deletePlan = useDeletePlan()
  const createPlan = useCreatePlan()
  const [createOpen, setCreateOpen] = useState(false)

  const form = useForm<PlanFormValues>({
    resolver: zodResolver(planFormSchema),
    defaultValues: {
      title: '',
      exam_date: '',
      daily_minutes: 60,
      preferred_days: ['mon', 'tue', 'wed', 'thu', 'fri'],
      topics: '',
    },
  })

  const onSubmit = async (values: PlanFormValues) => {
    try {
      await createPlan.mutateAsync({
        ...values,
        topics: values.topics.split(',').map(t => t.trim()).filter(Boolean),
      })
      setCreateOpen(false)
      form.reset()
      toast({ title: 'Plan created', description: 'Your study plan has been created.' })
    } catch {
      // The mutation hook shows the readable error toast.
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Study Planner</h1>
          <p className="text-muted-foreground">Create and manage your study plans.</p>
        </div>
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger>
            <Button className="shrink-0">
              <Plus className="mr-2 h-4 w-4" /> New Plan
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create Study Plan</DialogTitle>
            </DialogHeader>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                <FormField control={form.control} name="title" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Title</FormLabel>
                    <FormControl><Input {...field} placeholder="e.g. Final Exam - Math" /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
                <FormField control={form.control} name="exam_date" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Exam Date</FormLabel>
                    <FormControl><Input type="date" {...field} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
                <FormField control={form.control} name="daily_minutes" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Daily Study Minutes</FormLabel>
                    <FormControl><Input type="number" {...field} min={15} max={480} /></FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
                <FormField control={form.control} name="topics" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Topics (comma-separated)</FormLabel>
                    <FormControl>
                      <Input {...field} placeholder="Ch1, Ch2, Ch3" />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
                <FormField control={form.control} name="preferred_days" render={({ field }) => (
                  <FormItem>
                    <FormLabel>Study Days</FormLabel>
                    <FormControl>
                      <div className="flex flex-wrap gap-2">
                        {DAY_OPTIONS.map(day => (
                          <Button
                            key={day}
                            type="button"
                            variant={field.value?.includes(day) ? 'default' : 'outline'}
                            size="sm"
                            className="capitalize"
                            onClick={() => {
                              const current = field.value || []
                              const next = current.includes(day)
                                ? current.filter(d => d !== day)
                                : [...current, day]
                              field.onChange(next)
                            }}
                          >
                            {day.slice(0, 3)}
                          </Button>
                        ))}
                      </div>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )} />
                <div className="flex justify-end gap-2">
                  <Button type="button" variant="ghost" onClick={() => setCreateOpen(false)}>Cancel</Button>
                  <Button type="submit" disabled={createPlan.isPending}>
                    {createPlan.isPending ? 'Creating...' : 'Create Plan'}
                  </Button>
                </div>
              </form>
            </Form>
          </DialogContent>
        </Dialog>
      </div>

      {isError ? (
        <ErrorState
          title="Failed to load study plans"
          message={error instanceof Error ? error.message : undefined}
          onRetry={() => refetch()}
        />
      ) : isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-48 w-full" />
          ))}
        </div>
      ) : !plans || plans.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>No study plans yet</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground mb-4">Create a study plan to organize your exam preparation.</p>
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="mr-2 h-4 w-4" /> Create Plan
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {plans.map((plan: StudyPlan) => (
            <Card key={plan.id} className="hover:shadow-md transition-shadow">
              <CardHeader>
                <CardTitle className="flex items-center justify-between gap-2 break-words text-lg">
                  {plan.title}
                  <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs ${
                    plan.status === 'active' ? 'bg-green-100 text-green-700' :
                    plan.status === 'paused' ? 'bg-yellow-100 text-yellow-700' :
                    'bg-gray-100 text-gray-700'
                  }`}>{plan.status}</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Calendar className="h-4 w-4" />
                  <span>Exam: {plan.exam_date}</span>
                </div>
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Clock className="h-4 w-4" />
                  <span>{plan.daily_minutes} min/day · {plan.topics.length} topics</span>
                </div>
                <Separator />
                <div className="flex gap-2">
                  <Link to={`/planner/${plan.id}`} className="flex-1">
                    <Button variant="outline" size="sm" className="w-full">View Plan</Button>
                  </Link>
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-destructive hover:text-destructive"
                    disabled={deletePlan.isPending}
                    aria-label={`Delete study plan ${plan.title}`}
                    onClick={async () => {
                      if (confirm('Delete this study plan and all its tasks?')) {
                        try {
                          await deletePlan.mutateAsync(plan.id)
                        } catch {
                          // The mutation hook shows the readable error toast.
                        }
                      }
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
