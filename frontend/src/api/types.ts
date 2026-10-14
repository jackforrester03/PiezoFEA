// Aliases for the types generated from the backend OpenAPI schema (npm run gen:api).
import type { components } from './schema'

type S = components['schemas']

export type Project = S['Project']
export type Body = S['DiscBody'] | S['RingBody']
export type DiscBody = S['DiscBody']
export type RingBody = S['RingBody']
export type Electrode = S['Electrode']
export type AnnulusExtent = S['AnnulusExtent']
export type BandExtent = S['BandExtent']
export type Terminal = S['Terminal']
export type Study = S['Study']
export type EigenSettings = S['EigenSettings']
export type HarmonicSettings = S['HarmonicSettings']
export type MeshSettings = S['MeshSettings']
export type JobStatus = S['JobStatus']
export type JobResults = S['JobResults']
export type MaterialSummary = S['MaterialSummary']
export type Example = S['Example']
