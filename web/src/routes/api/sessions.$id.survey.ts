import { createFileRoute } from '@tanstack/react-router'
import { env } from 'cloudflare:workers'
import { isValidId, jsonError } from '#/lib/server'
import { survey, validateAnswers } from '#/lib/survey'

export const Route = createFileRoute('/api/sessions/$id/survey')({
  server: {
    handlers: {
      // The QR code can be scanned before the booth finishes uploading, so this
      // creates the row if needed. A survey can be submitted only once.
      POST: async ({ request, params }) => {
        if (!isValidId(params.id)) return jsonError(404, 'not found')
        let body: unknown
        try {
          body = await request.json()
        } catch {
          return jsonError(400, 'invalid JSON')
        }
        const result = validateAnswers((body as { answers?: unknown })?.answers)
        if (!result.ok) return jsonError(400, result.error)

        const update = await env.DB.prepare(
          `INSERT INTO sessions (id, submitted_at, survey_version, answers)
           VALUES (?1, ?2, ?3, ?4)
           ON CONFLICT(id) DO UPDATE SET
             submitted_at = ?2, survey_version = ?3, answers = ?4
           WHERE submitted_at IS NULL`,
        )
          .bind(params.id, new Date().toISOString(), survey.version, JSON.stringify(result.answers))
          .run()
        if (update.meta.changes === 0) return jsonError(409, 'already submitted')
        return Response.json({ ok: true })
      },
    },
  },
})
