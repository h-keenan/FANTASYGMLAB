import { Platform } from 'react-native';
import * as AppleAuthentication from 'expo-apple-authentication';
import * as Crypto from 'expo-crypto';

import { supabase } from './supabase';

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
export async function signInWithApple(): Promise<{ error: string | null }> {
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
    const { error } = await supabase.auth.signInWithIdToken({
      provider: 'apple',
      token: credential.identityToken,
      nonce: rawNonce,
    });
    return { error: error?.message ?? null };
  } catch (err) {
    const code = (err as { code?: string } | null)?.code;
    if (code === 'ERR_REQUEST_CANCELED') {
      return { error: null };
    }
    return { error: err instanceof Error ? err.message : 'Apple sign-in failed.' };
  }
}
