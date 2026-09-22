import { z } from 'zod'

const requiredText = (label: string, max: number) =>
  z
    .string()
    .trim()
    .min(1, `${label} is required`)
    .max(max, `${label} must be ${max} characters or less`)

export const incidentCreateFormSchema = z
  .object({
    title: requiredText('Title', 200),
    description: z.string().max(5000, 'Description must be 5000 characters or less'),
    service: requiredText('Service', 120),
    severity: z.enum(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']),
    window_start: z.string().min(1, 'Window start is required'),
    window_end: z.string().min(1, 'Window end is required'),
  })
  .superRefine((data, context) => {
    const start = new Date(data.window_start)
    const end = new Date(data.window_end)
    if (Number.isNaN(start.getTime())) {
      context.addIssue({
        code: 'custom',
        path: ['window_start'],
        message: 'Enter a valid start time',
      })
    }
    if (Number.isNaN(end.getTime())) {
      context.addIssue({ code: 'custom', path: ['window_end'], message: 'Enter a valid end time' })
    }
    if (!Number.isNaN(start.getTime()) && !Number.isNaN(end.getTime()) && end <= start) {
      context.addIssue({
        code: 'custom',
        path: ['window_end'],
        message: 'Window end must be later than window start',
      })
    }
  })

export type IncidentCreateForm = z.input<typeof incidentCreateFormSchema>

export const incidentEditFormSchema = z.object({
  title: requiredText('Title', 200),
  description: z.string().max(5000, 'Description must be 5000 characters or less'),
  severity: z.enum(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']),
})

export type IncidentEditForm = z.input<typeof incidentEditFormSchema>
