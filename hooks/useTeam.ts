'use client'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/contexts/AuthContext'
import { apiClient } from '@/lib/api'
export function useTeam() { const { user } = useAuth(); return useQuery({ queryKey: ['team', user?.uid], queryFn: () => apiClient.getTeam(), enabled: !!user }) }
