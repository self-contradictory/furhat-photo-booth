import { createFileRoute } from '@tanstack/react-router'
import { env } from 'cloudflare:workers'
import { getSession, isBooth, isValidId, jsonError, photoKey } from '#/lib/server'

export const Route = createFileRoute('/api/sessions/$id')({
  server: {
    handlers: {
      // Public: lets the survey page decide what to show. Never exposes the condition.
      GET: async ({ params }) => {
        if (!isValidId(params.id)) return jsonError(404, 'not found')
        const row = await getSession(params.id)
        return Response.json({
          submitted: Boolean(row?.submitted_at),
          hasPhoto: Boolean(row?.photo_key),
        })
      },

      // Booth only: upload the photo (raw JPEG body). Idempotent, so retries are safe.
      PUT: async ({ request, params }) => {
        if (!isBooth(request)) return jsonError(401, 'unauthorized')
        if (!isValidId(params.id)) return jsonError(400, 'bad id')
        const condition = request.headers.get('x-condition')
        const capturedAt = request.headers.get('x-captured-at')
        if (!condition || !capturedAt) return jsonError(400, 'missing x-condition or x-captured-at')

        const key = photoKey(params.id)
        await env.PHOTOS.put(key, request.body, {
          httpMetadata: { contentType: 'image/jpeg' },
        })
        await env.DB.prepare(
          `INSERT INTO sessions (id, condition, captured_at, uploaded_at, photo_key)
           VALUES (?1, ?2, ?3, ?4, ?5)
           ON CONFLICT(id) DO UPDATE SET
             condition = ?2, captured_at = ?3, uploaded_at = ?4, photo_key = ?5`,
        )
          .bind(params.id, condition, capturedAt, new Date().toISOString(), key)
          .run()
        return Response.json({ ok: true })
      },

      // Booth only: used by `orchestrator.py --check` to remove its test session.
      DELETE: async ({ request, params }) => {
        if (!isBooth(request)) return jsonError(401, 'unauthorized')
        if (!isValidId(params.id)) return jsonError(400, 'bad id')
        await env.PHOTOS.delete(photoKey(params.id))
        await env.DB.prepare('DELETE FROM sessions WHERE id = ?').bind(params.id).run()
        return Response.json({ ok: true })
      },
    },
  },
})
