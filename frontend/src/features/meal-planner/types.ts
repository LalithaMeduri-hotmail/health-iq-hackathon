import type { SourceRef } from '@/lib/types';

export type MealType = 'breakfast' | 'lunch' | 'dinner' | 'snack';
export type MealPlanBudget = 'low' | 'medium' | 'high';

export interface MealPlanPreferences {
  cuisine: string;
  budget: MealPlanBudget;
  days: number;
}

export interface MealPlanMeal {
  type: MealType;
  items: string[];
  notes: string;
  source: SourceRef;
}

export interface MealPlanDay {
  day: number;
  meals: MealPlanMeal[];
}

export interface MealPlanRationale {
  text: string;
  source: SourceRef;
}

export interface MealPlan {
  conditionTags: string[];
  preferences: MealPlanPreferences;
  days: MealPlanDay[];
  rationale: MealPlanRationale[];
  avoidList: string[];
  disclaimer: string;
}

export interface GenerateMealPlanRequest {
  reportId: string;
  preferences: MealPlanPreferences;
  profileId?: string;
}

export interface ReportListItem {
  reportId: string;
  reportDate: string;
  labName: string;
  parameterCount: number;
  abnormalCount: number;
}

export interface ReportListResponse {
  reports: ReportListItem[];
}