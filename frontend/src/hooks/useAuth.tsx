import React, { useContext } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch, type UserResponse, type LoginPayload, type RegisterPayload } from '../api/client';
import { AuthContext, type AuthContextType } from './useAuthContext';

export function AuthProvider({ children }: { children: React.ReactNode }): React.JSX.Element {
  const queryClient = useQueryClient();

  const { data: user, isLoading } = useQuery<UserResponse | null>({
    queryKey: ['auth', 'me'],
    queryFn: async () => {
      try {
        return await apiFetch<UserResponse>('/api/auth/me');
      } catch {
        return null;
      }
    },
    staleTime: 1000 * 60 * 5,
    retry: false,
  });

  const loginMutation = useMutation({
    mutationFn: async (payload: LoginPayload) => {
      return await apiFetch<UserResponse>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    },
    onSuccess: (data) => {
      queryClient.setQueryData(['auth', 'me'], data);
    },
  });

  const registerMutation = useMutation({
    mutationFn: async (payload: RegisterPayload) => {
      return await apiFetch<UserResponse>('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    },
  });

  const logoutMutation = useMutation({
    mutationFn: async () => {
      await apiFetch('/api/auth/logout', { method: 'POST' });
    },
    onSuccess: () => {
      queryClient.setQueryData(['auth', 'me'], null);
    },
  });

  const value: AuthContextType = {
    user: user ?? null,
    isLoading,
    isAuthenticated: Boolean(user),
    login: loginMutation.mutateAsync,
    register: registerMutation.mutateAsync,
    logout: async () => {
      await logoutMutation.mutateAsync();
    },
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
