/**
 * AlphaLens API client with credentials, double-submit CSRF, and silent 401 refresh rotation.
 */

import type { paths } from './schema';

export type UserResponse = paths['/api/auth/me']['get']['responses'][200]['content']['application/json'];
export type RegisterPayload = paths['/api/auth/register']['post']['requestBody']['content']['application/json'];
export type LoginPayload = paths['/api/auth/login']['post']['requestBody']['content']['application/json'];

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp('(^|;\\s*)(' + name + ')=([^;]*)'));
  return match && match[3] ? decodeURIComponent(match[3]) : null;
}

let isRefreshing = false;
let refreshSubscribers: Array<(ok: boolean) => void> = [];

function onRefreshed(ok: boolean): void {
  refreshSubscribers.forEach((callback) => callback(ok));
  refreshSubscribers = [];
}

function addRefreshSubscriber(callback: (ok: boolean) => void): void {
  refreshSubscribers.push(callback);
}

export async function apiFetch<T>(
  url: string,
  options: RequestInit = {},
  isRetry = false,
): Promise<T> {
  const headers = new Headers(options.headers ?? {});
  const method = (options.method ?? 'GET').toUpperCase();

  // Attach X-CSRF-Token for state-changing requests
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    let csrfToken = getCookie('csrf_token');
    if (!csrfToken && url !== '/api/auth/csrf') {
      try {
        const csrfRes = await fetch('/api/auth/csrf', { credentials: 'same-origin' });
        if (csrfRes.ok) {
          const csrfJson = (await csrfRes.json()) as { csrf_token: string };
          csrfToken = csrfJson.csrf_token || getCookie('csrf_token');
        }
      } catch {
        // Fallback to cookie check
        csrfToken = getCookie('csrf_token');
      }
    }

    if (csrfToken && !headers.has('X-CSRF-Token')) {
      headers.set('X-CSRF-Token', csrfToken);
    }
    if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
      headers.set('Content-Type', 'application/json');
    }
  }

  const response = await fetch(url, {
    ...options,
    headers,
    credentials: 'same-origin',
  });

  // Handle 401 Unauthorized by silently refreshing the session once
  if (response.status === 401 && !isRetry && url !== '/api/auth/login' && url !== '/api/auth/refresh') {
    if (!isRefreshing) {
      isRefreshing = true;
      try {
        const refreshHeaders = new Headers();
        const csrf = getCookie('csrf_token');
        if (csrf) {
          refreshHeaders.set('X-CSRF-Token', csrf);
        }

        const refreshRes = await fetch('/api/auth/refresh', {
          method: 'POST',
          headers: refreshHeaders,
          credentials: 'same-origin',
        });

        const refreshSuccess = refreshRes.ok;
        isRefreshing = false;
        onRefreshed(refreshSuccess);

        if (refreshSuccess) {
          return apiFetch<T>(url, options, true);
        }
      } catch {
        isRefreshing = false;
        onRefreshed(false);
      }
    } else {
      // Queue concurrent requests while refreshing
      return new Promise<T>((resolve, reject) => {
        addRefreshSubscriber((ok) => {
          if (ok) {
            resolve(apiFetch<T>(url, options, true));
          } else {
            reject(new Error('Session refresh failed'));
          }
        });
      });
    }
  }

  if (!response.ok) {
    let errorDetail = 'API request failed';
    try {
      const errorJson = await response.json();
      if (errorJson && typeof errorJson.detail === 'string') {
        errorDetail = errorJson.detail;
      }
    } catch {
      // Non-JSON response
    }
    throw new Error(errorDetail);
  }

  return (await response.json()) as T;
}

