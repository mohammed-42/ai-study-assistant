import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { plannerApi } from '@/services/api'
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
  return useMutation({
    mutationFn: (data: StudyPlanCreate) => plannerApi.createPlan(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['planner-plans'] }),
  })
}

export function useUpdatePlan() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: StudyPlanUpdate }) =>
      plannerApi.updatePlan(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['planner-plans'] })
      qc.invalidateQueries({ queryKey: ['planner-dashboard'] })
    },
  })
}

export function useDeletePlan() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => plannerApi.deletePlan(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['planner-plans'] })
      qc.invalidateQueries({ queryKey: ['planner-dashboard'] })
    },
  })
}

export function useGenerateSchedule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (planId: string) => plannerApi.generateSchedule(planId),
    onSuccess: (_, planId) => {
      qc.invalidateQueries({ queryKey: ['planner-plan', planId] })
      qc.invalidateQueries({ queryKey: ['planner-plans'] })
      qc.invalidateQueries({ queryKey: ['planner-dashboard'] })
    },
  })
}

export function useRegenerateSchedule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (planId: string) => plannerApi.regenerateSchedule(planId),
    onSuccess: (_, planId) => {
      qc.invalidateQueries({ queryKey: ['planner-plan', planId] })
      qc.invalidateQueries({ queryKey: ['planner-plans'] })
      qc.invalidateQueries({ queryKey: ['planner-dashboard'] })
    },
  })
}

export function useUpdateTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ taskId, data }: { taskId: string; data: StudyTaskUpdate }) =>
      plannerApi.updateTask(taskId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['planner-dashboard'] })
    },
  })
}

export function useDashboard() {
  return useQuery({
    queryKey: ['planner-dashboard'],
    queryFn: plannerApi.getDashboard,
  })
}
