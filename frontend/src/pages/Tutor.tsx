import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { chatApi } from '@/services/api'
import { Link, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Plus, Trash2, MessageSquare } from 'lucide-react'
import { useToast } from '@/hooks/use-toast'
import { Skeleton } from '@/components/ui/skeleton'

const QUERY_KEY = ['chat-sessions']

export default function Tutor() {
  const navigate = useNavigate()
  const { toast } = useToast()
  const queryClient = useQueryClient()

  const { data: sessions, isLoading } = useQuery({
    queryKey: QUERY_KEY,
    queryFn: () => chatApi.listSessions(),
  })

  const createMutation = useMutation({
    mutationFn: (title: string) => chatApi.createSession({ title }),
    onSuccess: (session) => {
      if (session) {
        queryClient.invalidateQueries({ queryKey: QUERY_KEY })
        navigate(`/tutor/${session.id}`)
      }
    },
    onError: (error: Error) => {
      toast({ title: 'Failed to create session', description: error.message, variant: 'destructive' })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => chatApi.deleteSession(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEY })
    },
  })

  const handleCreate = () => {
    createMutation.mutate('New Chat')
  }

  const handleDelete = (e: React.MouseEvent, id: string) => {
    e.preventDefault()
    e.stopPropagation()
    if (confirm('Delete this chat session?')) {
      deleteMutation.mutate(id)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">AI Tutor</h1>
          <p className="text-muted-foreground">Ask questions about your study materials</p>
        </div>
        <Button onClick={handleCreate} disabled={createMutation.isPending}>
          <Plus className="h-4 w-4 mr-2" />
          New Chat
        </Button>
      </div>

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-32 rounded-lg" />
          ))}
        </div>
      ) : sessions && sessions.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {sessions && sessions.map((session) => (
            <Link
              key={session.id}
              to={`/tutor/${session.id}`}
              className="group relative flex flex-col gap-2 rounded-lg border p-4 hover:bg-accent transition-colors"
            >
              <div className="flex items-start justify-between">
                <MessageSquare className="h-5 w-5 text-primary mt-0.5" />
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 w-8 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
                  onClick={(e) => handleDelete(e, session.id)}
                  disabled={deleteMutation.isPending}
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium truncate">{session.title}</p>
                <p className="text-xs text-muted-foreground mt-1">
                  {session.subject_id ? 'Subject: ' + session.subject_id.slice(0, 8) : 'General'}
                </p>
              </div>
              <p className="text-xs text-muted-foreground">
                {new Date(session.updated_at).toLocaleDateString()}
              </p>
            </Link>
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <MessageSquare className="h-12 w-12 text-muted-foreground mb-4" />
          <h2 className="text-lg font-semibold">No chat sessions yet</h2>
          <p className="text-muted-foreground mt-1 max-w-md">
            Create a new chat session to ask questions about your study materials.
            The AI will use your uploaded documents to provide grounded answers with citations.
          </p>
          <Button onClick={handleCreate} className="mt-4" disabled={createMutation.isPending}>
            <Plus className="h-4 w-4 mr-2" />
            Create First Chat
          </Button>
        </div>
      )}
    </div>
  )
}
