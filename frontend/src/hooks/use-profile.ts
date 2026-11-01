import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { profileApi } from '@/services/api'
import { toast } from '@/hooks/use-toast'

const PROFILE_KEY = ['profile']

export function useProfile() {
  return useQuery({
    queryKey: PROFILE_KEY,
    queryFn: profileApi.get,
  })
}

export function useUpdateProfile() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (fullName: string) => profileApi.update(fullName),
    onSuccess: (profile) => {
      queryClient.setQueryData(PROFILE_KEY, profile)
      toast({ title: 'Profile updated' })
    },
  })
}

export function useDeleteAccount() {
  return useMutation({
    mutationFn: profileApi.deleteAccount,
  })
}
