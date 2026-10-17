"use client";

import { useState } from "react";

import { BRAND_NAME as PRODUCT_NAME } from "@/lib/brand";

/**
 * Ports modules/age_gate.py's web COPPA gate: a neutral date-of-birth
 * entry, not an "I am 13+" checkbox (a self-attestation checkbox reads as
 * coaching the answer, not a real age check). Nothing about the entered
 * date is persisted anywhere — kept only in this component's React state,
 * lost on refresh, exactly like Streamlit's session-scoped behavior (the
 * Python docstring explicitly calls out that not surviving a refresh is an
 * accepted platform property, not a bug to fix).
 */

const MINIMUM_AGE = 13;

function calculateAge(birthDate: Date, today: Date = new Date()): number {
  let age = today.getFullYear() - birthDate.getFullYear();
  const monthDay = [today.getMonth(), today.getDate()];
  const birthMonthDay = [birthDate.getMonth(), birthDate.getDate()];
  if (monthDay[0] < birthMonthDay[0] || (monthDay[0] === birthMonthDay[0] && monthDay[1] < birthMonthDay[1])) {
    age -= 1;
  }
  return age;
}

export function AgeGate({ onConfirmed }: { onConfirmed: () => void }) {
  const [month, setMonth] = useState("");
  const [day, setDay] = useState("");
  const [year, setYear] = useState("");
  const [blocked, setBlocked] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (blocked) {
    return (
      <p role="alert" className="text-sm" style={{ color: "var(--color-danger)" }}>
        You must be at least {MINIMUM_AGE} years old to use {PRODUCT_NAME}. Nothing you entered has been saved.
      </p>
    );
  }

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    // SignInForm renders this inside its own <form> during create-account
    // (invalid nested-<form> markup, but React happily creates it in the
    // live DOM either way) — without this, confirming a birthdate also
    // bubbles the submit event up into the outer form's onSubmit, silently
    // firing a signUp/signIn call with whatever (blank) email/password the
    // user hasn't typed in yet.
    event.stopPropagation();
    const m = Number(month);
    const d = Number(day);
    const y = Number(year);
    const birthDate = new Date(y, m - 1, d);
    const isValid =
      month.length > 0 &&
      day.length > 0 &&
      year.length === 4 &&
      birthDate.getMonth() === m - 1 &&
      birthDate.getDate() === d &&
      y >= 1900 &&
      birthDate <= new Date();

    if (!isValid) {
      setError("Enter a valid date of birth.");
      return;
    }
    if (calculateAge(birthDate) < MINIMUM_AGE) {
      setBlocked(true);
      return;
    }
    setError(null);
    onConfirmed();
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        You must be at least {MINIMUM_AGE} to use {PRODUCT_NAME}. Enter your date of birth — it is not stored.
      </p>
      <div className="flex gap-2">
        <input
          aria-label="Birth month"
          placeholder="MM"
          maxLength={2}
          value={month}
          onChange={(event) => setMonth(event.target.value.replace(/\D/g, ""))}
          className="w-16 px-2 py-2 text-center"
          style={{
            background: "var(--color-surface-secondary)",
            color: "var(--color-text-primary)",
            border: "var(--border-width-default) solid var(--color-border)",
          }}
        />
        <input
          aria-label="Birth day"
          placeholder="DD"
          maxLength={2}
          value={day}
          onChange={(event) => setDay(event.target.value.replace(/\D/g, ""))}
          className="w-16 px-2 py-2 text-center"
          style={{
            background: "var(--color-surface-secondary)",
            color: "var(--color-text-primary)",
            border: "var(--border-width-default) solid var(--color-border)",
          }}
        />
        <input
          aria-label="Birth year"
          placeholder="YYYY"
          maxLength={4}
          value={year}
          onChange={(event) => setYear(event.target.value.replace(/\D/g, ""))}
          className="w-20 px-2 py-2 text-center"
          style={{
            background: "var(--color-surface-secondary)",
            color: "var(--color-text-primary)",
            border: "var(--border-width-default) solid var(--color-border)",
          }}
        />
      </div>
      {error ? (
        <p role="alert" className="text-xs" style={{ color: "var(--color-warning)" }}>
          {error}
        </p>
      ) : null}
      <button
        type="submit"
        className="px-4 py-2 text-sm font-bold self-start"
        style={{
          background: "var(--color-accent-strong)",
          color: "var(--color-brand-mark-ink)",
          fontWeight: "var(--font-weight-button)",
        }}
      >
        Confirm date of birth
      </button>
    </form>
  );
}
