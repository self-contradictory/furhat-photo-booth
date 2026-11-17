import { createFileRoute } from '@tanstack/react-router'
import { env } from 'cloudflare:workers'
import { getSession, isValidId, jsonError } from '#/lib/server'

export const Route = createFileRoute('/api/sessions/$id/photo')({
  server: {
    handlers: {
      // The photo is the reward for the survey, so it is served only after submission.
      GET: async ({ request, params }) => {
        if (!isValidId(params.id)) return jsonError(404, 'not found')
        const row = await getSession(params.id)
        if (!row?.submitted_at) return jsonError(403, 'survey not submitted')
        if (!row.photo_key) return jsonError(404, 'photo still uploading')
        const object = await env.PHOTOS.get(row.photo_key)
        if (!object) return jsonError(404, 'photo still uploading')

        const download = new URL(request.url).searchParams.has('download')
        return new Response(object.body, {
          headers: {
            'content-type': 'image/jpeg',
            'cache-control': 'private, max-age=3600',
            ...(download && {
              'content-disposition': `attachment; filename="furhat-photo-${params.id}.jpg"`,
            }),
          },
        })
      },
    },
  },
})
