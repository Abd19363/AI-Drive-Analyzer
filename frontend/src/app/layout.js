import "./globals.css";

export const metadata = {
  title: "AI-Drive Analyzer | Secure Document Intelligence",
  description: "Secure, intelligent document search and analysis for Google Drive with multi-layer privacy protection.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body>{children}</body>
    </html>
  );
}
