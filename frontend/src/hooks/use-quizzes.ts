import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { quizApi } from '@/services/api'
import { useToast } from './use-toast'
import type { QuizGenerateRequest, QuizSubmitRequest } from '@/types'

const QUIZZES_QUERY_KEY = ['quizzes']
const QUIZ_QUERY_KEY = (id: string) => ['quiz', id]
const ATTEMPTS_QUERY_KEY = (id: string) => ['quiz-attempts', id]
const SUMMARY_QUERY_KEY = (id: string) => ['quiz-summary', id]

export function useQuizzes(subjectId?: string) {
  return useQuery({
    queryKey: [...QUIZZES_QUERY_KEY, subjectId],
    queryFn: () => quizApi.list(subjectId),
  })
}

export function useQuiz(id: string) {
  return useQuery({
    queryKey: QUIZ_QUERY_KEY(id),
    queryFn: () => quizApi.get(id),
    enabled: !!id,
  })
}

export function useQuizAttempts(quizId: string) {
  return useQuery({
    queryKey: ATTEMPTS_QUERY_KEY(quizId),
    queryFn: () => quizApi.getAttempts(quizId),
    enabled: !!quizId,
  })
}

export function useQuizSummary(quizId: string) {
  return useQuery({
    queryKey: SUMMARY_QUERY_KEY(quizId),
    queryFn: () => quizApi.getSummary(quizId),
    enabled: !!quizId,
  })
}

export function useGenerateQuiz() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: (data: QuizGenerateRequest) => quizApi.generate(data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: QUIZZES_QUERY_KEY })
      if (data?.id) {
        queryClient.setQueryData(QUIZ_QUERY_KEY(data.id), data)
      }
    },
    onError: (error: Error) => {
      toast({ title: 'Failed to generate quiz', description: error.message, variant: 'destructive' })
    },
  })
}

export function useSubmitQuiz() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: ({ quizId, data }: { quizId: string; data: QuizSubmitRequest }) =>
      quizApi.submit(quizId, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ATTEMPTS_QUERY_KEY(variables.quizId) })
      queryClient.invalidateQueries({ queryKey: SUMMARY_QUERY_KEY(variables.quizId) })
      queryClient.invalidateQueries({ queryKey: QUIZ_QUERY_KEY(variables.quizId) })
    },
    onError: (error: Error) => {
      toast({ title: 'Failed to submit quiz', description: error.message, variant: 'destructive' })
    },
  })
}

export function useDeleteQuiz() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: (id: string) => quizApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUIZZES_QUERY_KEY })
      toast({ title: 'Quiz deleted' })
    },
    onError: (error: Error) => {
      toast({ title: 'Failed to delete', description: error.message, variant: 'destructive' })
    },
  })
}
