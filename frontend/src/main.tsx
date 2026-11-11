import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { AppErrorBoundary } from './components/AppErrorBoundary'
import { DesktopHost } from './desktop/DesktopHost'

createRoot(document.getElementById('root')!).render(<StrictMode><DesktopHost><AppErrorBoundary><App /></AppErrorBoundary></DesktopHost></StrictMode>)
