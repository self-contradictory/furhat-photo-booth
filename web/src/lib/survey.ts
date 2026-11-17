import surveyJson from '../survey.json'

export type ScaleItem = {
  id: string
  type: 'scale'
  text?: string
  group?: string
  reverse?: boolean
  required?: boolean
  min: number
  max: number
  minLabel: string
  maxLabel: string
}

export type ChoiceItem = {
  id: string
  type: 'choice'
  text: string
  required?: boolean
  options: { value: number; label: string }[]
}

export type TextItem = {
  id: string
  type: 'text'
  text: string
  required?: boolean
  maxLength: number
}

export type SurveyItem = ScaleItem | ChoiceItem | TextItem

export type Survey = {
  version: number
  title: string
  intro: string
  sections: { title: string; description?: string; items: SurveyItem[] }[]
}

export type Answers = Record<string, number | string>

export const survey = surveyJson as Survey

export const surveyItems = survey.sections.flatMap((s) => s.items)

// Returns cleaned answers, or an error message naming the first bad item.
export function validateAnswers(
  input: unknown,
): { ok: true; answers: Answers } | { ok: false; error: string } {
  if (typeof input !== 'object' || input === null) {
    return { ok: false, error: 'answers must be an object' }
  }
  const raw = input as Record<string, unknown>
  const answers: Answers = {}
  for (const item of surveyItems) {
    const value = raw[item.id]
    const required = item.required ?? true
    if (value === undefined || value === null || value === '') {
      if (required) return { ok: false, error: `missing answer: ${item.id}` }
      continue
    }
    if (item.type === 'text') {
      if (typeof value !== 'string') return { ok: false, error: `bad answer: ${item.id}` }
      answers[item.id] = value.slice(0, item.maxLength)
    } else if (item.type === 'scale') {
      if (!Number.isInteger(value) || (value as number) < item.min || (value as number) > item.max) {
        return { ok: false, error: `bad answer: ${item.id}` }
      }
      answers[item.id] = value as number
    } else {
      if (!item.options.some((o) => o.value === value)) {
        return { ok: false, error: `bad answer: ${item.id}` }
      }
      answers[item.id] = value as number
    }
  }
  return { ok: true, answers }
}
