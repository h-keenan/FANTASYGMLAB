import React from 'react';
import { Ionicons } from '@expo/vector-icons';

import ToneBadge from './ToneBadge';

type IconName = React.ComponentProps<typeof Ionicons>['name'];

const EVENT_TYPE_ICONS: Record<string, IconName> = {
  'injury/status': 'add',
  transaction: 'swap-horizontal',
  'role/depth chart': 'stats-chart',
};

/** The one glyph per news/alert event type (mirrors web-next's EventTypeGlyph). */
export function eventTypeIconName(eventType: string | null | undefined): IconName {
  return EVENT_TYPE_ICONS[eventType ?? ''] ?? 'chatbubble-outline';
}

export default function EventTypeGlyph({
  eventType,
  color,
  size = 14,
}: {
  eventType: string | null | undefined;
  color: string;
  size?: number;
}) {
  return <Ionicons name={eventTypeIconName(eventType)} size={size} color={color} />;
}

/** Event-type pill: glyph + label in the event's semantic tint (web's EventTypePill). */
export function EventTypePill({
  eventType,
  label,
  color,
}: {
  eventType: string | null | undefined;
  label: string;
  color: string;
}) {
  return <ToneBadge label={label} color={color} icon={eventTypeIconName(eventType)} />;
}
