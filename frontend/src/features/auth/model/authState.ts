import type { AuthMe, CambioPasswordContexto, UsuarioRespuesta } from '../../../api/contracts'

export type AuthState =
  | { status: 'anonymous' | 'authenticating' | 'validating' | 'closing'; user: null }
  | { status: 'authenticated'; user: UsuarioRespuesta }
  | { status: 'passwordChangeRequired'; user: null; context: CambioPasswordContexto }
export type AuthAction =
  | { type: 'start' | 'validate' | 'reset' | 'close' }
  | { type: 'success'; user: AuthMe }
export const initialState: AuthState = { status: 'anonymous', user: null }
export function authReducer(_state: AuthState, action: AuthAction): AuthState {
  switch (action.type) {
    case 'start': return { status: 'authenticating', user: null }
    case 'validate': return { status: 'validating', user: null }
    case 'success': return action.user.debe_cambiar_password
      ? { status: 'passwordChangeRequired', user: null, context: { id: action.user.id, debe_cambiar_password: true } }
      : { status: 'authenticated', user: action.user }
    case 'reset': return initialState
    case 'close': return { status: 'closing', user: null }
  }
}
