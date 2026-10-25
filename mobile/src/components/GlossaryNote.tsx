import React from 'react';

import ScreenInfoNote from './ScreenInfoNote';
import { useThemeMode } from '../context/ThemeModeContext';
import { GLOSSARY, type GlossaryKey } from '../lib/glossary';

/**
 * "What do these mean?" under a row of jargon labels (Power Rank, Starter
 * Strength, ...). Tapping opens the shared info sheet (ScreenInfoNote) with
 * one plain-language sentence per term from the shared glossary
 * (lib/glossary.ts), for every account, not only beginners. Mirrors
 * web-next's GlossaryNote.
 */
export default function GlossaryNote({ terms, label = 'What do these mean?' }: { terms: GlossaryKey[]; label?: string }) {
  const { colors } = useThemeMode();
  if (terms.length === 0) return null;
  return (
    <ScreenInfoNote
      label={label}
      text="Plain-language definitions for the labels on this screen."
      legend={terms.map((key) => ({
        label: GLOSSARY[key].label,
        color: colors.accent,
        description: GLOSSARY[key].definition,
      }))}
    />
  );
}
