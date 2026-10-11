import { Text, View } from 'react-native';
import type { Memory } from '../domain/memory';
import { styles } from './theme';

export function readableDate(timestamp: string): string {
  if (!Number.isFinite(Date.parse(timestamp))) return 'a valid observation date';
  return new Date(timestamp).toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric',
    hour: 'numeric', minute: '2-digit' });
}

export function MemoryCard({ memory }: { memory: Memory }) {
  return <View style={styles.card}>
    <Text style={styles.small}>OBJECT · YOUR CONFIRMED RECORD</Text>
    <Text style={styles.cardTitle}>{memory.name}</Text>
    <View style={styles.evidence}>
      <Text style={styles.body}>{memory.location.state === 'known'
        ? `Last recorded: ${memory.location.text}` : 'Location unknown'}</Text>
      <Text style={styles.small}>Observed {readableDate(memory.observedAt)}</Text>
      <Text selectable style={styles.small}>{memory.observedAt}</Text>
    </View>
    {!!memory.notes && <Text style={styles.body}>{memory.notes}</Text>}
    <Text style={styles.small}>Typed by you · Saved {readableDate(memory.savedAt)}</Text>
    <Text style={styles.small}>This is a past record. Nook has not checked where it is now.</Text>
  </View>;
}
