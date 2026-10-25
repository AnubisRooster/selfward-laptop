import axios from 'axios';

// Served by the API itself (the window, a browser, or a phone through the private https address) -> same origin. Anywhere else (the dev server, the splash page) -> localhost:8100.
export const BASE = typeof location !== 'undefined' && (location.protocol === 'http:' || location.protocol === 'https:') && location.port !== '1420' ? '' : 'http://localhost:8100';
export const http = axios.create({ baseURL: BASE + '/api', timeout: 30000 });
// Changes can start slow work (fetching a page, building a brief), so they get longer than reads.
const LONG = { timeout: 300000 };

export const get = <T = any>(url: string, params?: any) => http.get<T>(url, { params }).then(r => r.data);
export const post = <T = any>(url: string, body?: any) => http.post<T>(url, body ?? {}, LONG).then(r => r.data);
export const put = <T = any>(url: string, body?: any) => http.put<T>(url, body ?? {}, LONG).then(r => r.data);
export const patch = <T = any>(url: string, body?: any) => http.patch<T>(url, body ?? {}, LONG).then(r => r.data);
export const del = <T = any>(url: string) => http.delete<T>(url).then(r => r.data);

export const errText = (e: any): string =>
  e?.response?.data?.detail || (e?.code === 'ERR_NETWORK' ? 'Can’t reach the Selfward backend.' : e?.message || 'Something went wrong.');

export function ago(ts?: number | null) {
  if (!ts) return '';
  const s = Date.now() / 1000 - ts;
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  if (s < 86400 * 14) return `${Math.floor(s / 86400)}d ago`;
  return new Date(ts * 1000).toLocaleDateString();
}

// A phone that isn't signed in gets 401 {remote_auth: true}: the app shows its sign-in screen.
http.interceptors.response.use(r => r, e => {
  if (e?.response?.status === 401 && e.response.data?.remote_auth) window.dispatchEvent(new Event('sf-remote-auth'));
  return Promise.reject(e);
});
