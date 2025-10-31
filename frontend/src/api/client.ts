/**
 * API client for LangViz backend.
 * 
 * Provides typed interface to REST endpoints with error handling.
 */

import type { Entry, SimilarityScore, CognateSet } from './types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

class ApiError extends Error {
	constructor(
		message: string,
		public status: number,
		public details?: unknown
	) {
		super(message);
		this.name = 'ApiError';
	}
}

async function request<T>(
	endpoint: string,
	options: RequestInit = {}
): Promise<T> {
	const url = `${API_BASE}${endpoint}`;
	
	const response = await fetch(url, {
		...options,
		headers: {
			'Content-Type': 'application/json',
			...options.headers,
		},
	});
	
	if (!response.ok) {
		const details = await response.json().catch(() => null);
		throw new ApiError(
			`API request failed: ${response.statusText}`,
			response.status,
			details
		);
	}
	
	return response.json();
}

export const api = {
	entries: {
		get: (id: string) =>
			request<Entry>(`/entries/${id}`),
		
		create: (entry: Omit<Entry, 'id' | 'created_at'>) =>
			request<Entry>('/entries', {
				method: 'POST',
				body: JSON.stringify(entry),
			}),
	},
	
	similarity: {
		compute: (ipaA: string, ipaB: string) =>
			request<{ distance: number }>('/similarity', {
				method: 'POST',
				body: JSON.stringify({ ipa_a: ipaA, ipa_b: ipaB }),
			}),
	},
	
	cognates: {
		detect: (entries: Entry[]) =>
			request<CognateSet[]>('/cognates/detect', {
				method: 'POST',
				body: JSON.stringify(entries),
			}),
	},
	
	embeddings: {
		get: (text: string) =>
			request<{ embedding: number[] }>(`/embeddings?text=${encodeURIComponent(text)}`),
	},
};

export { ApiError };

