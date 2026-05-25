import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  build: {
    rolldownOptions: {
      output: {
        codeSplitting: {
          minSize: 20_000,
          groups: [
            {
              name: 'react-vendor',
              priority: 60,
              test: /node_modules[\\/](react|react-dom)[\\/]/,
            },
            {
              name: 'router-vendor',
              priority: 55,
              test: /node_modules[\\/](react-router|react-router-dom)[\\/]/,
            },
            {
              name: 'query-vendor',
              priority: 50,
              test: /node_modules[\\/]@tanstack[\\/]/,
            },
            {
              name: 'supabase-vendor',
              priority: 45,
              test: /node_modules[\\/]@supabase[\\/]/,
            },
            {
              entriesAware: true,
              name: 'charts-vendor',
              priority: 40,
              test: /node_modules[\\/](recharts|d3-|victory-vendor|decimal\.js-light|eventemitter3)[\\/]/,
            },
            {
              entriesAware: true,
              name: 'markdown-vendor',
              priority: 40,
              test: /node_modules[\\/](react-markdown|remark-|rehype-|unified|micromark|mdast-|hast-|unist-|vfile|decode-named-character-reference|character-entities|property-information|space-separated-tokens|comma-separated-tokens|trim-lines|devlop|bail|trough|html-url-attributes)[\\/]/,
            },
            {
              entriesAware: true,
              name: 'ui-vendor',
              priority: 35,
              test: /node_modules[\\/](lucide-react|@radix-ui|class-variance-authority|clsx|tailwind-merge)[\\/]/,
            },
          ],
        },
      },
    },
  },
  plugins: [react(), tailwindcss()],
})
