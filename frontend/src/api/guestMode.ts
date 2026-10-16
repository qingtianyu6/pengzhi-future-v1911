const GUEST_KEY = 'pengzhi_guest_mode'

export function enterGuestMode() {
  sessionStorage.setItem(GUEST_KEY, '1')
  localStorage.removeItem('pengzhi_auth_token')
  localStorage.removeItem('pengzhi_auth_user')
}

export function leaveGuestMode() {
  sessionStorage.removeItem(GUEST_KEY)
}

export function isGuestMode() {
  return sessionStorage.getItem(GUEST_KEY) === '1' && !localStorage.getItem('pengzhi_auth_token')
}
