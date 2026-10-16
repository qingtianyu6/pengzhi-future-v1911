import { getStoredUser } from '../api/authApi'
import { isGuestMode } from '../api/guestMode'
export function canManage() { return isGuestMode() || ['admin', 'agronomist'].includes(getStoredUser()?.role ?? '') }
export function canOperate() { return canManage() || getStoredUser()?.role === 'executor' }
