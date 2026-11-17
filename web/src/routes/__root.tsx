import { HeadContent, Link, Scripts, createRootRoute } from '@tanstack/react-router'

import appCss from '../styles.css?url'

export const Route = createRootRoute({
  head: () => ({
    meta: [
      { charSet: 'utf-8' },
      { name: 'viewport', content: 'width=device-width, initial-scale=1' },
      { title: 'Furhat Photo Booth' },
    ],
    links: [{ rel: 'stylesheet', href: appCss }],
  }),
  shellComponent: RootDocument,
})

function RootDocument({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <HeadContent />
      </head>
      <body className="font-sans antialiased">
        <div className="mx-auto flex min-h-screen max-w-xl flex-col px-4">
          <header className="flex items-center justify-between py-4">
            <Link to="/" className="font-bold text-[var(--ink)] no-underline">
              Furhat Photo Booth
            </Link>
            <Link to="/about" className="text-sm text-[var(--ink-soft)]">
              About &amp; data
            </Link>
          </header>
          <main className="flex-1 pb-12">{children}</main>
        </div>
        <Scripts />
      </body>
    </html>
  )
}
