import { getToken } from './auth';

// Persist a single session id for the tab lifetime so the backend can
// maintain conversation history across messages.
const SESSION_ID = `web-session-${Date.now()}`;

export async function sendChat(message, awsAccountId) {
  const body = { message, session_id: SESSION_ID };
  if (awsAccountId) body.aws_account_id = awsAccountId;

  const token = getToken();
  if (!token) throw new Error('Not authenticated');

  let res;
  try {
    res = await fetch(window.APP_CONFIG.api.endpoints.chat, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(body),
    });
  } catch (err) {
    throw new Error('Network error — please check your connection.');
  }

  if (res.status === 401) throw new Error('Session expired — please sign in again.');
  if (!res.ok) throw new Error(`Server error (${res.status})`);
  return res.json();
}
