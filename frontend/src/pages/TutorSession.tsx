import { useEffect, useRef, useState } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { chatApi } from '@/services/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { ErrorState } from '@/components/error-state'
import { useToast } from '@/hooks/use-toast'
import type { ChatMessage } from '@/types'
import { Send, ChevronLeft, Loader2 } from 'lucide-react'

const QUERY_KEY = (sessionId: string) => ['chat-messages', sessionId]

export default function TutorSession() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const [isTyping, setIsTyping] = useState(false)

  const { data: messages, isLoading, isError, error, refetch } = useQuery({
    queryKey: QUERY_KEY(sessionId!),
    queryFn: () => chatApi.listMessages(sessionId!),
    refetchInterval: 3000, // Poll for new messages
  })

  const sendMutation = useMutation({
    mutationFn: (content: string) =>
      chatApi.sendMessage(sessionId!, { content }),
    onMutate: () => {
      setIsTyping(true)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEY(sessionId!) })
      setIsTyping(false)
    },
    onError: (error: Error) => {
      toast({ title: 'Failed to send', description: error.message, variant: 'destructive' })
      setIsTyping(false)
    },
  })

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || sendMutation.isPending) return
    
    const message = input.trim()
    setInput('')
    sendMutation.mutate(message)
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3 border-b pb-3">
        <Button variant="ghost" size="sm" onClick={() => navigate('/tutor')}>
          <ChevronLeft className="h-4 w-4 mr-1" />
          Back
        </Button>
        <h1 className="text-lg font-semibold">AI Tutor</h1>
      </div>

      {/* Messages */}
      <div className="flex-1 space-y-4 overflow-auto py-4" aria-live="polite">
        {isLoading ? (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex gap-3">
                <Skeleton className="h-10 w-10 rounded-full" />
                <Skeleton className="h-16 flex-1" />
              </div>
            ))}
          </div>
        ) : isError ? (
          <ErrorState
            title="Failed to load messages"
            message={error instanceof Error ? error.message : undefined}
            onRetry={() => refetch()}
          />
        ) : messages && messages.length > 0 ? (
          messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <p className="text-muted-foreground">
              Ask a question about your study materials
            </p>
            <p className="text-sm text-muted-foreground mt-1">
              The AI will search your documents and provide cited answers
            </p>
          </div>
        )}
        {isTyping && (
          <div className="flex gap-3">
            <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
              <Loader2 className="h-5 w-5 text-primary animate-spin" />
            </div>
            <div className="flex-1">
              <Skeleton className="h-16 w-3/4" />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t pt-4">
        <form onSubmit={handleSubmit} className="flex gap-2 max-w-3xl mx-auto">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about your study materials..."
            disabled={sendMutation.isPending}
            className="flex-1"
            aria-label="Ask a question about your study materials"
          />
          <Button type="submit" disabled={sendMutation.isPending || !input.trim()}>
            {sendMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <>
                <Send className="h-4 w-4 mr-2" />
                Send
              </>
            )}
          </Button>
        </form>
      </div>
    </div>
  )
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'
  
  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className={`h-10 w-10 rounded-full flex items-center justify-center flex-shrink-0 ${
        isUser ? 'bg-primary text-primary-foreground' : 'bg-muted'
      }`}>
        {isUser ? 'You' : 'AI'}
      </div>
      <div className={`min-w-0 max-w-[80%] ${isUser ? 'text-right' : ''}`}>
        <div className={`rounded-lg px-4 py-3 ${
          isUser ? 'bg-primary text-primary-foreground' : 'bg-muted'
        }`}>
          <p className="whitespace-pre-wrap break-words text-sm">{message.content}</p>
        </div>
        
        {/* Citations */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2 justify-start" aria-label="Sources">
            {message.citations.map((citation) => {
              const pageLabel =
                citation.page_start === citation.page_end
                  ? `p. ${citation.page_start}`
                  : `pp. ${citation.page_start}-${citation.page_end}`
              return (
                <Link
                  key={citation.chunk_id}
                  to={`/documents/${citation.document_id}`}
                  className="inline-flex max-w-full flex-wrap items-center gap-1 rounded bg-secondary px-2 py-0.5 text-xs text-secondary-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <span className="break-words">
                    {citation.document_name}, {pageLabel}
                  </span>
                  {citation.has_unverified_ocr && (
                    <Badge
                      variant="outline"
                      className="border-yellow-300 bg-yellow-50 text-yellow-800"
                    >
                      OCR - unverified
                    </Badge>
                  )}
                </Link>
              )
            })}
          </div>
        )}
        
        {message.is_insufficient && (
          <p className="text-xs text-muted-foreground mt-1 italic">
            No relevant materials found for this question
          </p>
        )}
        
        <p className="text-xs text-muted-foreground mt-1">
          {new Date(message.created_at).toLocaleTimeString()}
        </p>
      </div>
    </div>
  )
}
