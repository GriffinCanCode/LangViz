/**
 * Type definitions matching backend models.
 * 
 * Ensures type safety across API boundary.
 */

export type LanguageBranch =
	| 'indo_iranian'
	| 'hellenic'
	| 'italic'
	| 'germanic'
	| 'celtic'
	| 'balto_slavic'
	| 'armenian'
	| 'albanian'
	| 'anatolian'
	| 'tocharian';

export interface Language {
	iso_code: string;
	name: string;
	branch: LanguageBranch;
	subfamily?: string;
	coordinates?: [number, number];
}

export interface Entry {
	id: string;
	headword: string;
	ipa: string;
	language: string;
	definition: string;
	etymology?: string;
	pos_tag?: string;
	embedding?: number[];
	created_at: string;
}

export interface SimilarityScore {
	entry_a: string;
	entry_b: string;
	phonetic: number;
	semantic: number;
	combined: number;
	confidence: number;
}

export interface CognateSet {
	id: string;
	entries: string[];
	confidence: number;
	proto_form?: string;
	semantic_core: string;
}

