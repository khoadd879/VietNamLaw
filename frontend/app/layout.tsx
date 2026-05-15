import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'LexVN — Luật sư AI Việt Nam',
  description: 'Tư vấn pháp luật Việt Nam bằng AI',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="vi" data-theme="light" suppressHydrationWarning>
      <head>
        <meta charSet="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;600&family=DM+Sans:wght@300;400;500;600&display=swap"
          rel="stylesheet"
        />
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){var t=localStorage.getItem('lexvn-theme')||'light';document.documentElement.setAttribute('data-theme',t);})()`,
          }}
        />
      </head>
      <body style={{ margin: 0 }}>{children}</body>
    </html>
  )
}