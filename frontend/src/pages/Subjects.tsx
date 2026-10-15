import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '@/services/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { toast } from '@/hooks/use-toast'
import type { Subject } from '@/types'

export default function Subjects() {
  const queryClient = useQueryClient()
  const [newSubject, setNewSubject] = useState({ name: '', description: '' })
  const [open, setOpen] = useState(false)

  const { data: subjects, isLoading } = useQuery({
    queryKey: ['subjects'],
    queryFn: () => apiFetch<Subject[]>('/subjects/'),
  })

  const createMutation = useMutation({
    mutationFn: (data: { name: string; description?: string }) =>
      apiFetch<Subject>('/subjects/', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subjects'] })
      setOpen(false)
      setNewSubject({ name: '', description: '' })
      toast({ title: 'Subject created', description: 'Your new subject has been added.' })
    },
    onError: (err: Error) => {
      toast({ title: 'Failed to create subject', description: err.message, variant: 'destructive' })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiFetch(`/subjects/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subjects'] })
      toast({ title: 'Subject deleted' })
    },
    onError: (err: Error) => {
      toast({ title: 'Failed to delete', description: err.message, variant: 'destructive' })
    },
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Subjects</h2>
          <p className="text-muted-foreground">Manage your study subjects</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              New Subject
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create subject</DialogTitle>
              <DialogDescription>Add a new subject to organize your study materials.</DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  value={newSubject.name}
                  onChange={(e) => setNewSubject((s) => ({ ...s, name: e.target.value }))}
                  placeholder="e.g., Mathematics"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Description (optional)</Label>
                <Input
                  id="description"
                  value={newSubject.description}
                  onChange={(e) => setNewSubject((s) => ({ ...s, description: e.target.value }))}
                  placeholder="Brief description..."
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
              <Button onClick={() => createMutation.mutate(newSubject)} disabled={!newSubject.name.trim()}>
                Create
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {isLoading ? (
        <div className="flex h-32 items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      ) : subjects?.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>No subjects yet</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">Create your first subject to start organizing your study materials.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {subjects?.map((subject: Subject) => (
            <Card key={subject.id} className="flex items-center justify-between">
              <CardContent className="flex flex-1 items-center gap-4 px-6 py-4">
                <div className="flex-1">
                  <h3 className="font-semibold">{subject.name}</h3>
                  {subject.description && <p className="text-sm text-muted-foreground">{subject.description}</p>}
                </div>
              </CardContent>
              <div className="flex items-center gap-2 pr-6">
                <Button variant="ghost" size="icon" onClick={() => deleteMutation.mutate(subject.id)} title="Delete subject">
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
