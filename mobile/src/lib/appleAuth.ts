import { Platform } from 'react-native';
import * as AppleAuthentication from 'expo-apple-authentication';
import * as Crypto from 'expo-crypto';

import { supabase } from './supabase';
import { exchangeIdToken, type AuthResult } from './guestConversion';

export async function isAppleAuthAvailable(): Promise<boolean> {
  if (Platform.OS !== 'ios') return false;
  try {
    return await AppleAuthentication.isAvailableAsync();
  } catch {
    return false;
  }
}

/**
 * Native "Sign in with Apple" -> Supabase native token exchange
 * (supabase.auth.signInWithIdToken) — no email confirmation step, and no
 * detour through the web app the way email/password sign-up currently has.
 * The nonce round-trip (raw here, SHA-256 to Apple) is Apple's documented
 * replay-attack mitigation for this flow.
 */
export async function signInWithApple(opts: { linkGuest?: boolean } = {}): Promise<AuthResult> {
  try {
    const rawNonce = Crypto.randomUUID();
    const hashedNonce = await Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256, rawNonce);
    const credential = await AppleAuthentication.signInAsync({
      requestedScopes: [
        AppleAuthentication.AppleAuthenticationScope.FULL_NAME,
        AppleAuthentication.AppleAuthenticationScope.EMAIL,
      ],
      nonce: hashedNonce,
    });
    if (!credential.identityToken) {
      return { error: "Apple didn't return an identity token." };
    }
    // linkGuest: attach Apple to the current anonymous user (same user id)
    // instead of signing in as a separate user.
    return await exchangeIdToken(supabase.auth, {
      provider: 'apple',
      token: credential.identityToken,
      nonce: rawNonce,
      linkGuest: Boolean(opts.linkGuest),
    });
  } catch (err) {
    const code = (err as { code?: string } | null)?.code;
    if (code === 'ERR_REQUEST_CANCELED') {
      return { error: null };
    }
    return { error: err instanceof Error ? err.message : 'Apple sign-in failed.' };
  }
}
