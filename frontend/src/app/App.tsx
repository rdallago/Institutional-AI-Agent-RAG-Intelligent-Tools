import { BrowserRouter } from 'react-router-dom'
import { AppProviders } from './providers'
import { AppRoutes } from '../router/routes'

export function App() {
  return <AppProviders><BrowserRouter><AppRoutes /></BrowserRouter></AppProviders>
}
