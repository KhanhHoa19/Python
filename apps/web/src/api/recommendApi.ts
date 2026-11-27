import { apiGet, apiPut } from './client.ts';
import { Recommendations } from '../types/recommend.ts';

export const getRecommendations = (query: { mood?: string | null; maxMinutes?: number | null; limit?: number } = {}) =>
  apiGet<Recommendations>('/recommendations', { mood: query.mood ?? undefined, max_minutes: query.maxMinutes ?? undefined, limit: query.limit });

/** Choose (or change) the liked topic tags. An empty list with onboarded=true means "skip". */
export const savePreferences = (favoriteCategories: string[], onboarded = true) =>
  apiPut<Recommendations>('/recommendations/preferences', { favorite_categories: favoriteCategories, onboarded });
