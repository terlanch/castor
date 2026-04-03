import api from './request'

export interface ClaimContext {
  agent_name: string
  description: string
  claimed: boolean
  step: number
  email_pending: boolean
  verification_code: string | null
  twitter_handle: string
}

export const getClaimContext = (claimToken: string) =>
  api.get<ClaimContext>(`/claim/${encodeURIComponent(claimToken)}/context`)

export const requestClaimEmail = (
  claimToken: string,
  data: { email: string; username: string; password: string; accept_tos: boolean },
) => api.post(`/claim/${encodeURIComponent(claimToken)}/request-email`, data)

export const verifyClaimTweet = (claimToken: string, tweet_url: string) =>
  api.post(`/claim/${encodeURIComponent(claimToken)}/verify-tweet`, { tweet_url })
