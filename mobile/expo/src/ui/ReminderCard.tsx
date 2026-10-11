import { Text, View } from 'react-native';
import type { Reminder } from '../domain/reminder';
import { reminderStatus } from '../domain/reminder';
import { readableDate } from './MemoryCard';
import { Button } from './Button';
import { styles } from './theme';

export function ReminderCard({ reminder, now, busy, onCancel }: {
  reminder: Reminder; now: Date; busy: boolean; onCancel: (id: string) => void;
}) {
  return <View style={styles.card}>
    <Text style={styles.small}>{reminder.channel === 'email' ? 'EMAIL QUEUE' : 'IN-APP REMINDER'} · YOUR CONFIRMED REQUEST</Text>
    <Text style={styles.cardTitle}>{reminder.title}</Text>
    <Text style={styles.body}>{readableDate(reminder.dueAt)}</Text>
    <Text selectable style={styles.small}>{reminder.dueAt}</Text>
    <Text style={styles.body}>{reminderStatus(reminder,now)}</Text>
    {reminder.channel === 'email' && <Text style={styles.small}>No recipient, email account or transport is connected. This is a local request only; it will need a separate delivery review.</Text>}
    {reminder.status !== 'cancelled' && <Button secondary disabled={busy} title={`Review cancellation: ${reminder.title}`}
      onPress={() => onCancel(reminder.id)} />}
  </View>;
}
