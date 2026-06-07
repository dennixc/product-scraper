import type { Metadata } from "next";
import "./globals.css";
import { EnvProvider } from "@/lib/mode";

export const metadata: Metadata = {
  title: "Product Data Scraper",
  description:
    "Scrape product data from manufacturer websites for Shopline e-commerce",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <EnvProvider>{children}</EnvProvider>
      </body>
    </html>
  );
}
