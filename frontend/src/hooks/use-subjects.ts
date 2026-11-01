import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/services/api'
import type { Subject } from '@/types'

export function useSubjects(enabled = true) {
  return useQuery({
    queryKey: ['subjects'],
    queryFn: () => apiFetch<Subject[]>('/subjects/'),
    enabled,
  })
}
