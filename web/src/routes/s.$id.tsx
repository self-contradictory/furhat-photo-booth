import { createFileRoute } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { survey } from '#/lib/survey'
import type { Answers, SurveyItem } from '#/lib/survey'

// The page a participant reaches by scanning the booth's QR code:
// survey first, then the photo.
export const Route = createFileRoute('/s/$id')({ component: SessionPage })

type Status = { submitted: boolean; hasPhoto: boolean }

function SessionPage() {
  const { id } = Route.useParams()
  const [status, setStatus] = useState<Status | null>(null)
  const [loadError, setLoadError] = useState(false)

  useEffect(() => {
    fetch(`/api/sessions/${id}`)
      .then((r) => (r.ok ? (r.json() as Promise<Status>) : Promise.reject(r.status)))
      .then((s) => setStatus(s))
      .catch(() => setLoadError(true))
  }, [id])

  if (loadError) return <p className="pt-8">This link is not valid. Please scan the QR code again.</p>
  if (!status) return <p className="pt-8 text-[var(--ink-soft)]">Loading…</p>
  if (status.submitted) return <PhotoView id={id} />
  return <SurveyForm id={id} onDone={() => setStatus({ ...status, submitted: true })} />
}

function SurveyForm({ id, onDone }: { id: string; onDone: () => void }) {
  const [answers, setAnswers] = useState<Answers>({})
  const [missing, setMissing] = useState<string[]>([])
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')

  const set = (itemId: string, value: number | string) => {
    setAnswers((a) => ({ ...a, [itemId]: value }))
    setMissing((m) => m.filter((x) => x !== itemId))
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    const unanswered = survey.sections
      .flatMap((s) => s.items)
      .filter((i) => (i.required ?? true) && (answers[i.id] === undefined || answers[i.id] === ''))
      .map((i) => i.id)
    if (unanswered.length > 0) {
      setMissing(unanswered)
      document.getElementById(`item-${unanswered[0]}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      return
    }
    setSending(true)
    setError('')
    const res = await fetch(`/api/sessions/${id}/survey`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ answers }),
    }).catch(() => null)
    setSending(false)
    // 409 means it was already submitted (e.g. a double tap), so the photo is unlocked anyway.
    if (res && (res.ok || res.status === 409)) {
      window.scrollTo(0, 0)
      onDone()
    } else {
      setError('Could not send your answers. Check your connection and try again.')
    }
  }

  return (
    <form onSubmit={submit} className="space-y-8 pt-4" noValidate>
      <div>
        <h1 className="mb-2 text-2xl font-bold">{survey.title}</h1>
        <p className="text-[var(--ink-soft)]">{survey.intro}</p>
      </div>

      {survey.sections.map((section) => (
        <fieldset key={section.title} className="space-y-5">
          <legend className="mb-1 text-lg font-semibold">{section.title}</legend>
          {section.description && <p className="text-sm text-[var(--ink-soft)]">{section.description}</p>}
          {section.items.map((item) => (
            <Item
              key={item.id}
              item={item}
              value={answers[item.id]}
              missing={missing.includes(item.id)}
              onChange={(v) => set(item.id, v)}
            />
          ))}
        </fieldset>
      ))}

      {missing.length > 0 && <p className="text-[var(--accent)]">Please answer the highlighted questions.</p>}
      {error && <p className="text-[var(--accent)]">{error}</p>}
      <button
        type="submit"
        disabled={sending}
        className="w-full rounded-xl bg-[var(--accent)] px-4 py-3 text-lg font-semibold text-[var(--accent-ink)] disabled:opacity-60"
      >
        {sending ? 'Sending…' : 'Submit and get my photo'}
      </button>
    </form>
  )
}

function Item({
  item,
  value,
  missing,
  onChange,
}: {
  item: SurveyItem
  value: number | string | undefined
  missing: boolean
  onChange: (v: number | string) => void
}) {
  const border = missing ? 'border-[var(--accent)]' : 'border-[var(--line)]'
  return (
    <div id={`item-${item.id}`} className={`rounded-xl border bg-[var(--surface)] p-4 ${border}`}>
      {item.text && <p className="mb-3 font-medium">{item.text}</p>}

      {item.type === 'scale' && (
        <>
          <div className="flex justify-between gap-1">
            {range(item.min, item.max).map((n) => (
              <button
                type="button"
                key={n}
                aria-label={`${n}`}
                aria-pressed={value === n}
                onClick={() => onChange(n)}
                className={`h-10 flex-1 rounded-lg border text-sm font-semibold ${
                  value === n
                    ? 'border-[var(--accent)] bg-[var(--accent)] text-[var(--accent-ink)]'
                    : 'border-[var(--line)]'
                }`}
              >
                {n}
              </button>
            ))}
          </div>
          <div className="mt-1 flex justify-between text-xs text-[var(--ink-soft)]">
            <span>{item.minLabel}</span>
            <span>{item.maxLabel}</span>
          </div>
        </>
      )}

      {item.type === 'choice' && (
        <div className="space-y-2">
          {item.options.map((o) => (
            <label key={o.value} className="flex items-center gap-3">
              <input
                type="radio"
                name={item.id}
                checked={value === o.value}
                onChange={() => onChange(o.value)}
                className="h-5 w-5 accent-[var(--accent)]"
              />
              {o.label}
            </label>
          ))}
        </div>
      )}

      {item.type === 'text' && (
        <textarea
          rows={3}
          maxLength={item.maxLength}
          value={(value as string) ?? ''}
          onChange={(e) => onChange(e.target.value)}
          className="w-full rounded-lg border border-[var(--line)] bg-transparent p-2"
        />
      )}
    </div>
  )
}

function PhotoView({ id }: { id: string }) {
  // The booth may still be uploading if the participant was very fast; retry until it appears.
  const [attempt, setAttempt] = useState(0)
  const [ready, setReady] = useState(false)
  const src = `/api/sessions/${id}/photo?t=${attempt}`

  useEffect(() => {
    if (ready) return
    const timer = setTimeout(() => setAttempt((a) => a + 1), 4000)
    return () => clearTimeout(timer)
  }, [attempt, ready])

  return (
    <section className="space-y-4 pt-4">
      <h1 className="text-2xl font-bold">Thank you! Here is your photo</h1>
      <img
        key={attempt}
        src={src}
        alt="Your photo with Furhat"
        onLoad={() => setReady(true)}
        className={`w-full rounded-xl border border-[var(--line)] ${ready ? '' : 'hidden'}`}
      />
      {ready ? (
        <a
          href={`/api/sessions/${id}/photo?download=1`}
          className="block w-full rounded-xl bg-[var(--accent)] px-4 py-3 text-center text-lg font-semibold text-[var(--accent-ink)] no-underline"
        >
          Download photo
        </a>
      ) : (
        <p className="text-[var(--ink-soft)]">Your photo is still uploading from the booth. This page will update by itself.</p>
      )}
      <p className="text-sm text-[var(--ink-soft)]">This link keeps working, so you can come back to it later.</p>
    </section>
  )
}

function range(min: number, max: number) {
  return Array.from({ length: max - min + 1 }, (_, i) => min + i)
}
