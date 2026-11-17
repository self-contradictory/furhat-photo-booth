import { Link, createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/')({ component: Home })

function Home() {
  return (
    <section className="pt-8">
      <h1 className="mb-3 text-3xl font-bold">Take a photo with Furhat</h1>
      <p className="mb-4 text-[var(--ink-soft)]">
        Furhat is a social robot. Take a photo with it at the booth, scan the QR code, answer a short
        survey and download your photo.
      </p>
      <Link to="/about" className="text-[var(--accent)]">
        How we use your data
      </Link>
    </section>
  )
}
