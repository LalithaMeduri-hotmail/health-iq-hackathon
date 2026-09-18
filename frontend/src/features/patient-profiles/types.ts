/** Patient-profile contracts mirrored from `backend/app/models/patient_profile.py`. */

export type ProfileStatus = 'active' | 'archived';
export type ConsentStatus = 'pending' | 'granted' | 'withdrawn';

export const RELATIONSHIPS = [
  'self',
  'spouse',
  'parent',
  'child',
  'sibling',
  'grandparent',
  'dependent',
  'other',
] as const;

export type Relationship = (typeof RELATIONSHIPS)[number];

export interface PatientProfile {
  id: string;
  accountId: string;
  displayName: string;
  relationshipToAccountOwner: Relationship;
  dateOfBirth: string | null;
  sex: string | null;
  preferredLanguage: string;
  country: string | null;
  city: string | null;
  dietaryPreference: string | null;
  allergies: string[];
  foodIntolerances: string[];
  dislikedFoods: string[];
  knownConditions: string[];
  healthGoals: string[];
  isAccountOwnerProfile: boolean;
  status: ProfileStatus;
  consentStatus: ConsentStatus;
  consentVersion: string | null;
  createdAt: string;
  updatedAt: string;
  etag: string | null;
}

export interface PatientProfileListResponse {
  profiles: PatientProfile[];
  activeProfileId: string | null;
}

/** Editable fields; the backend never accepts `id`, `accountId`, `status`, or consent here. */
export interface PatientProfileInput {
  displayName: string;
  relationshipToAccountOwner: Relationship | string;
  dateOfBirth?: string | null;
  sex?: string | null;
  country?: string | null;
  city?: string | null;
  dietaryPreference?: string | null;
  allergies?: string[];
  foodIntolerances?: string[];
  dislikedFoods?: string[];
  knownConditions?: string[];
  healthGoals?: string[];
}

export interface PatientProfileCreateInput extends PatientProfileInput {
  consentAccepted: boolean;
  relationshipAssertion?: string;
}