import { useEffect, useState } from 'react';
import { Platform } from 'react-native';
import * as AuthSession from 'expo-auth-session';
import * as Crypto from 'expo-crypto';
import * as WebBrowser from 'expo-web-browser';
import { discovery as googleDiscovery } from 'expo-auth-session/providers/google';

import { supabase } from './supabase';
import { env } from './env';

WebBrowser.maybeCompleteAuthSession();

function resolveClientId(): string {
  return (
    Platform.select({
      ios: env.googleIosClientId,
      android: env.googleAndroidClientId,
      default: env.googleWebClientId,
    }) || env.googleWebClientId
  );
}

/**
 * Google sign-in -> Supabase native token exchange (signInWithIdToken),
 * requesting an id_token directly from Google's own OAuth endpoint via
 * expo-auth-session (no separate native Google SDK/prebuild dependency).
 * `available` is false — and the button should stay hidden — until a real
 * Google Cloud OAuth client id exists; see mobile/.env.example.
 */
export function useGoogleSignIn() {
  const clientId = resolveClientId();
  const available = Boolean(clientId);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState<{ raw: string; hashed: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    const rawNonce = Crypto.randomUUID();
    Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256, rawNonce).then((hashedNonce) => {
      if (!cancelled) setNonce({ raw: rawNonce, hashed: hashedNonce });
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const redirectUri = AuthSession.makeRedirectUri({ scheme: 'fantasygmlab' });
  const [request, response, promptAsync] = AuthSession.useAuthRequest(
    {
      clientId: clientId || 'unset',
      scopes: ['openid', 'profile', 'email'],
      redirectUri,
      responseType: AuthSession.ResponseType.IdToken,
      usePKCE: false,
      extraParams: nonce ? { nonce: nonce.hashed } : {},
    },
    googleDiscovery,
  );

  useEffect(() => {
    if (response?.type !== 'success') {
      if (response?.type === 'error') {
        setError(response.error?.message ?? 'Google sign-in failed.');
      }
      return;
    }
    const idToken = response.params.id_token;
    if (!idToken) {
      setError("Google didn't return an identity token.");
      return;
    }
    setSubmitting(true);
    supabase.auth
      .signInWithIdToken({ provider: 'google', token: idToken, nonce: nonce?.raw })
      .then(({ error: signInError }) => {
        setError(signInError?.message ?? null);
      })
      .finally(() => setSubmitting(false));
    // Only the response identity should re-trigger this exchange.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [response]);

  const signIn = async () => {
    setError(null);
    await promptAsync();
  };

  return { available, ready: Boolean(request) && Boolean(nonce), submitting, error, signIn };
}
