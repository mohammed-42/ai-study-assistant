import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useNote, useUpdateNote } from '@/hooks/use-notes'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ArrowLeft, Save } from 'lucide-react'
import { Badge } from '@/components/ui/badge'

export default function NotesDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: note, isLoading } = useNote(id!)
  const updateNote = useUpdateNote()
  const [editing, setEditing] = useState(false)
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')

  useEffect(() => {
    if (note) {
      setTitle(note.title)
      setContent(note.content)
    }
  }, [note])

  const handleSave = async () => {
    if (!id) return
    await updateNote.mutateAsync({ id, data: { title, content } })
    setEditing(false)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    )
  }

  if (!note) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-4">
        <p className="text-muted-foreground">Note not found</p>
        <Button onClick={() => navigate('/notes')}>Back to Notes</Button>
      </div>
    )
  }

  const noteTypeLabel = (t: string) => {
    const map: Record<string, string> = { summary: 'Summary', key_concepts: 'Key Concepts', definitions: 'Definitions', revision: 'Revision' }
    return map[t] || t
  }

  const noteTypeColor = (t: string) => {
    const map: Record<string, string> = {
      summary: 'bg-blue-100 text-blue-700',
      key_concepts: 'bg-green-100 text-green-700',
      definitions: 'bg-purple-100 text-purple-700',
      revision: 'bg-orange-100 text-orange-700',
    }
    return map[t] || 'bg-gray-100'
  }

  return (
    <div className="space-y-6">
      <Button variant="ghost" size="sm" onClick={() => navigate('/notes')}>
        <ArrowLeft className="mr-2 h-4 w-4" /> Back
      </Button>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          {editing ? (
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="text-2xl font-bold flex-1 mr-4 bg-background border rounded px-2 py-1"
            />
          ) : (
            <CardTitle className="text-2xl">{note.title}</CardTitle>
          )}
          <Badge className={noteTypeColor(note.note_type)}>{noteTypeLabel(note.note_type)}</Badge>
        </CardHeader>
        <CardContent>
          {editing ? (
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              className="w-full min-h-[300px] p-4 rounded-md border bg-background text-sm leading-relaxed"
            />
          ) : (
            <div className="prose prose-sm max-w-none whitespace-pre-wrap text-sm leading-relaxed">
              {note.content}
            </div>
          )}
          <p className="mt-4 text-xs text-muted-foreground">
            Created {new Date(note.created_at).toLocaleString()}
            {note.updated_at !== note.created_at && ` · Updated ${new Date(note.updated_at).toLocaleString()}`}
          </p>
        </CardContent>
      </Card>

      <div className="flex gap-2">
        {editing ? (
          <>
            <Button onClick={handleSave} disabled={updateNote.isPending}>
              <Save className="mr-2 h-4 w-4" /> Save
            </Button>
            <Button variant="outline" onClick={() => { setEditing(false); setTitle(note.title); setContent(note.content); }}>
              Cancel
            </Button>
          </>
        ) : (
          <Button onClick={() => setEditing(true)}>
            <Save className="mr-2 h-4 w-4" /> Edit Note
          </Button>
        )}
      </div>
    </div>
  )
}
