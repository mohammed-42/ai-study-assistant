import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { plannerApi } from '@/services/api'
import { useToast } from './use-toast'
import type { StudyPlanCreate, StudyPlanUpdate, StudyTaskUpdate } from '@/types'

export function usePlannerPlans() {
  return useQuery({
    queryKey: ['planner-plans'],
    queryFn: plannerApi.listPlans,
  })
}

export function usePlannerPlan(id: string) {
  return useQuery({
    queryKey: ['planner-plan', id],
    queryFn: () => plannerApi.getPlan(id),
    enabled: !!id,
  })
}

export function useCreatePlan() {
  const qc = useQueryClient()
  const { toast } = useToast()
  return useMutation({
    mutationFn: (data: StudyPlanCreate) => plannerApi.createPlan(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['planner-plans'] }),
    onError: (error: Error) => {
      toast({ title: 'Failed to create plan', description: error.message, variant: 'destructive' })
    },
  })
}

export function useUpdatePlan() {
  const qc = useQueryClient()
  const { toast } = useToast()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: StudyPlanUpdate }) =>
      plannerApi.updatePlan(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['planner-plans'] })
      qc.invalidateQueries({ queryKey: ['planner-dashboard'] })
    },
    onError: (error: Error) => {
      toast({ title: 'Failed to update plan', description: error.message, variant: 'destructive' })
    },
  })
}

export function useDeletePlan() {
  const qc = useQueryClient()
  const { toast } = useToast()
  return useMutation({
    mutationFn: (id: string) => plannerApi.deletePlan(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['planner-plans'] })
      qc.invalidateQueries({ queryKey: ['planner-dashboard'] })
    },
    onError: (error: Error) => {
      toast({ title: 'Failed to delete plan', description: error.message, variant: 'destructive' })
    },
  })
}

export function useGenerateSchedule() {
  const qc = useQueryClient()
  const { toast } = useToast()
  return useMutation({
    mutationFn: (planId: string) => plannerApi.generateSchedule(planId),
    onSuccess: (_, planId) => {
      qc.invalidateQueries({ queryKey: ['planner-plan', planId] })
      qc.invalidateQueries({ queryKey: ['planner-plans'] })
      qc.invalidateQueries({ queryKey: ['planner-dashboard'] })
    },
    onError: (error: Error) => {
      toast({ title: 'Failed to generate schedule', description: error.message, variant: 'destructive' })
    },
  })
}

export function useRegenerateSchedule() {
  const qc = useQueryClient()
  const { toast } = useToast()
  return useMutation({
    mutationFn: (planId: string) => plannerApi.regenerateSchedule(planId),
    onSuccess: (_, planId) => {
      qc.invalidateQueries({ queryKey: ['planner-plan', planId] })
      qc.invalidateQueries({ queryKey: ['planner-plans'] })
      qc.invalidateQueries({ queryKey: ['planner-dashboard'] })
    },
    onError: (error: Error) => {
      toast({ title: 'Failed to regenerate schedule', description: error.message, variant: 'destructive' })
    },
  })
}

export function useUpdateTask() {
  const qc = useQueryClient()
  const { toast } = useToast()
  return useMutation({
    mutationFn: ({ taskId, data }: { taskId: string; data: StudyTaskUpdate }) =>
      plannerApi.updateTask(taskId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['planner-dashboard'] })
    },
    onError: (error: Error) => {
      toast({ title: 'Failed to update task', description: error.message, variant: 'destructive' })
    },
  })
}

export function useDashboard() {
  return useQuery({
    queryKey: ['planner-dashboard'],
    queryFn: plannerApi.getDashboard,
  })
}
