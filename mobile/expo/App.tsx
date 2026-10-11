import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, TextInput, View } from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { randomUUID } from 'expo-crypto';
import { VaultError } from './src/domain/memory';
import type { Memory, MemoryDraft, Recall } from './src/domain/memory';
import { ADAPTER_LABEL, interpret, WELCOME } from './src/domain/conversation';
import type { ConversationContext } from './src/domain/conversation';
import type { Reminder, ReminderDraft } from './src/domain/reminder';
import { MemoryVault } from './src/storage/vault';
import type { Preview } from './src/storage/vault';
import { ReminderBook } from './src/storage/reminders';
import type { ReminderPreview } from './src/storage/reminders';
import { openExpoDatabase } from './src/storage/expoDatabase';
import { CAPABILITY_DETAILS } from './src/ai/capabilities';
import { LaptopClient } from './src/ai/laptopClient';
import { GENERATED_LABEL,generalConversation,PERSONAL_CAUTION } from './src/ai/laptopContract';
import { Button } from './src/ui/Button';
import { MemoryCard, readableDate } from './src/ui/MemoryCard';
import { ReminderCard } from './src/ui/ReminderCard';
import { colors, styles } from './src/ui/theme';

type Tab = 'chat' | 'memories' | 'reminders' | 'setup';
type Message = { id: string; role: 'user' | 'assistant'; text: string; sources?: Memory[]; ambiguous?: boolean; generated?:boolean };
type Pending = { kind: 'memory'; preview: Preview } | { kind: 'reminder'; preview: ReminderPreview };
type Services = { vault: MemoryVault; reminders: ReminderBook };
const blankMemory = (): MemoryDraft => ({ kind:'object', name:'', location:{ state:'known', text:'' }, notes:'', observedAt:new Date().toISOString() });

function Nook() {
  const [services, setServices] = useState<Services | null>(null);
  const [bootAttempt, setBootAttempt] = useState(0), [bootError, setBootError] = useState('');
  const [tab, setTab] = useState<Tab>('chat');
  const [messages, setMessages] = useState<Message[]>([]);
  const [context, setContext] = useState<ConversationContext>(null);
  const [input, setInput] = useState(''), [pending, setPending] = useState<Pending | null>(null);
  const [saved, setSaved] = useState<Memory[]>([]), [reminders, setReminders] = useState<Reminder[]>([]);
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const [memoryEditor, setMemoryEditor] = useState<MemoryDraft | null>(null);
  const [reminderEditor, setReminderEditor] = useState<ReminderDraft | null>(null);
  const [now, setNow] = useState(() => new Date());
  const busyRef = useRef(false), mounted = useRef(true);
  const laptop=useRef(new LaptopClient());
  const [laptopEnabled,setLaptopEnabled]=useState(false),[laptopStatus,setLaptopStatus]=useState('Disabled. No laptop model request has been made.');
  const [generating,setGenerating]=useState(false);

  useEffect(() => {
    let active = true;
    let opened: MemoryVault | null = null;
    let closeRequested = false;
    const closeOnce = async () => {
      if (!opened || closeRequested) return;
      closeRequested = true; await opened.close().catch(() => undefined);
    };
    setBootError('');
    void (async () => {
      const database = await openExpoDatabase();
      try {
        opened = await MemoryVault.open(database, () => new Date(), randomUUID);
        if (!active) { await closeOnce(); return; }
        const reminderBook = await ReminderBook.open(database, () => new Date(), randomUUID);
        const records = await opened.recent(), jobs = await reminderBook.recent();
        if (active) { setSaved(records); setReminders(jobs); setServices({ vault:opened, reminders:reminderBook }); }
        else await closeOnce();
      } catch (failure) {
        if (opened) await closeOnce(); else await database.close().catch(() => undefined);
        throw failure;
      }
    })().catch(() => { if (active) setBootError('Could not open the local vault. Your data has not been reset.'); });
    return () => { active = false; void closeOnce(); };
  }, [bootAttempt]);
  useEffect(() => {
    mounted.current = true;
    const timer = setInterval(() => setNow(new Date()), 30_000);
    return () => { mounted.current = false; clearInterval(timer); laptop.current.disable(); };
  }, []);

  function begin(): boolean {
    if (busyRef.current) return false;
    busyRef.current = true; setBusy(true); setError(''); setNotice(''); return true;
  }
  function finish() { busyRef.current = false; if (mounted.current) setBusy(false); }
  function message(role: Message['role'], text: string, sources?: Memory[], ambiguous = false, generated=false) {
    if (!mounted.current) return;
    setMessages((prior) => [...prior, { id:randomUUID(), role, text, generated, ...(sources ? { sources, ambiguous } : {}) }].slice(-40));
  }
  function discard() {
    if (pending?.kind === 'memory') services?.vault.cancel(pending.preview.id);
    if (pending?.kind === 'reminder') services?.reminders.cancelPreview(pending.preview.id);
    setPending(null);
  }
  function navigate(next: Tab) { if (!busyRef.current) { setTab(next); setError(''); } }
  async function refresh() {
    if (!services) return;
    setSaved(await services.vault.recent()); setReminders(await services.reminders.recent());
  }
  async function reviewMemory(draft: MemoryDraft) {
    if (!services) return;
    discard(); setPending({ kind:'memory', preview:await services.vault.preview(draft) });
    setMemoryEditor(null); setReminderEditor(null); setTab('chat');
    message('assistant', 'Memory draft ready for review. It has not been saved.');
  }
  function reviewReminder(draft: ReminderDraft) {
    if (!services) return;
    discard(); setPending({ kind:'reminder', preview:services.reminders.preview(draft) });
    setMemoryEditor(null); setReminderEditor(null); setTab('chat');
    message('assistant', 'Reminder draft ready for review. Nothing is scheduled or sent.');
  }
  function showRecall(result: Recall, focus: 'place' | 'time') {
    if (result.kind === 'not_found') {
      setContext(null); message('assistant', 'No confirmed memory matches “' + result.query + '”. I can’t tell where it is.'); return;
    }
    if (result.kind === 'ambiguous') {
      setContext(null); message('assistant', 'These records share a name. Choose a dated source for follow-up questions; I won’t merge their locations.', result.matches, true); return;
    }
    setContext({ memoryId:result.memory.id, name:result.memory.name });
    message('assistant', focus === 'time' ? 'This is the time you reported, not a sensor observation.'
      : result.kind === 'unknown' ? 'You recorded this item, but its location is unknown.' : 'Here is your last recorded place. I haven’t checked its current location.', [result.memory]);
  }
  async function send() {
    if (!services || !input.trim() || !begin()) return;
    const submitted = input; setInput(''); message('user', submitted);
    try {
      const intent = interpret(submitted, context, new Date());
      if (intent.kind === 'memory') await reviewMemory(intent.draft);
      else if (intent.kind === 'reminder') reviewReminder(intent.draft);
      else if (intent.kind === 'recall') {
        if (intent.memoryId) {
          const record = await services.vault.byId(intent.memoryId);
          showRecall(record ? { kind:record.location.state === 'known' ? 'known' : 'unknown', memory:record }
            : { kind:'not_found', query:intent.query }, intent.focus);
        } else showRecall(await services.vault.recall(intent.query), intent.focus);
      } else if (intent.kind === 'show_reminders') {
        setReminders(await services.reminders.recent()); setTab('reminders');
        message('assistant', 'Your confirmed reminder requests are in Reminders. Email is never marked sent by this prototype.');
      } else if (intent.kind === 'capability') message('assistant', CAPABILITY_DETAILS[intent.capability]);
      else if(intent.kind==='help'&&laptopEnabled) {
        if(!generalConversation(submitted)) message('assistant',PERSONAL_CAUTION);
        else {
          setGenerating(true);
          try {message('assistant',await laptop.current.chat(submitted,randomUUID()),undefined,false,true);}
          catch(failure) {
            const code=failure instanceof Error?failure.message:'';
            message('assistant',code==='cancelled'?'Generation cancelled. No generated turn was kept.':
              code==='timeout'?'Laptop model timed out. No generated turn was kept.':
              code==='invalid_output'?'The model returned an invalid reply. No action was taken.':
              'Laptop model unavailable. Confirmed memories and exact approvals still work.');
          } finally {if(mounted.current)setGenerating(false);}
        }
      }
      else message('assistant', intent.text);
    } catch (failure) {
      setError(failure instanceof VaultError ? failure.message : 'Could not complete this request. Check the current preview and local records before retrying.');
    } finally { finish(); }
  }
  async function approve() {
    if (!services || !pending || !begin()) return;
    const exact = pending;
    try {
      if (exact.kind === 'memory') {
        const result = await services.vault.approve(exact.preview.id, exact.preview.payloadJson, true);
        setSaved((prior) => [result.memory, ...prior.filter((item) => item.id !== result.memory.id)].slice(0,100));
        setContext({ memoryId:result.memory.id, name:result.memory.name });
        message('assistant', result.replayed ? 'This exact memory was already saved. No duplicate was added.' : 'Memory confirmed and saved locally.', [result.memory]);
      } else {
        const result = await services.reminders.approve(exact.preview.id, exact.preview.payloadJson, true);
        setReminders((prior) => [result.reminder, ...prior.filter((item) => item.id !== result.reminder.id)]);
        message('assistant', result.reminder.status === 'cancelled' ? 'The confirmed reminder is cancelled. The queue will not attempt delivery.'
          : result.reminder.channel === 'email' ? 'Email request saved to the local queue. No account is connected and no email was sent.'
            : 'Reminder saved locally. Device notifications are not connected; open Reminders to see when it is due.');
      }
      setPending(null); setNotice('Exact approval recorded.');
      try { await refresh(); } catch { setError('The change is confirmed. Could not refresh the other records.'); }
    } catch (failure) {
      if (failure instanceof VaultError) {
        setError(failure.message);
        if (['preview_expired','stale_preview','preview_missing','payload_changed','invalid_reminder_time','duplicate_reminder'].includes(failure.code)) discard();
      } else setError('Could not confirm the result. Retry this exact preview to check the durable receipt; don’t create another copy.');
    } finally { finish(); }
  }
  async function cancelReminder(id: string) {
    if (!services || !begin()) return;
    try { discard(); setPending({ kind:'reminder', preview:await services.reminders.previewCancel(id) }); setTab('chat'); }
    catch (failure) { setError(failure instanceof VaultError ? failure.message : 'Could not prepare the cancellation. Nothing was cancelled.'); }
    finally { finish(); }
  }
  async function reviewEditor() {
    if (!services || !begin()) return;
    try { if (memoryEditor) await reviewMemory(memoryEditor); else if (reminderEditor) reviewReminder(reminderEditor); }
    catch (failure) { setError(failure instanceof VaultError ? failure.message : 'Could not prepare a preview. Nothing was saved.'); }
    finally { finish(); }
  }
  const expired = !!pending && Date.parse(pending.preview.expiresAt) <= now.getTime();

  if (!services) return <SafeAreaView style={styles.safe}><View style={styles.scroll}>
    <Text style={styles.brand}>nook ✦</Text>
    {bootError ? <View style={styles.card}><Text accessibilityRole="alert" style={styles.error}>{bootError}</Text>
      <Text style={styles.small}>{Platform.OS === 'web' ? 'The web preview needs its documented SQLite isolation headers.' : 'No records were erased.'}</Text>
      <Button title="Try opening again" onPress={() => setBootAttempt((attempt) => attempt + 1)} /></View>
      : <><ActivityIndicator color={colors.focus} /><Text style={styles.body}>Opening your local vault…</Text></>}
  </View></SafeAreaView>;

  return <SafeAreaView style={styles.safe}>
    <KeyboardAvoidingView style={styles.keyboard} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.scroll}>
        <View style={styles.header}><Text style={styles.brand}>nook<Text style={{ color:colors.coral }}> ✦</Text></Text>
          <View style={styles.badge}><Text style={styles.badgeText}>{Platform.OS === 'web' ? 'Expo web preview' : 'Local vault'}</Text></View></View>
        <View style={styles.tabs} accessibilityRole="tablist">
          {(['chat','memories','reminders','setup'] as const).map((item) => <Pressable key={item} accessibilityRole="tab"
            accessibilityLabel={item === 'setup' ? 'Setup and capabilities' : item[0]!.toUpperCase()+item.slice(1)}
            accessibilityState={{ selected:tab === item, disabled:busy }} disabled={busy} onPress={() => navigate(item)}
            style={[styles.tab, tab === item && styles.tabSelected]}><Text style={[styles.tabText, tab === item && styles.tabTextSelected]}>
              {item[0]!.toUpperCase()+item.slice(1)}</Text></Pressable>)}
        </View>
        {!!error && <Text accessibilityRole="alert" style={styles.error}>{error}</Text>}
        {!!notice && <Text accessibilityLiveRegion="polite" style={styles.small}>{notice}</Text>}
        {tab === 'chat' && <View style={styles.section}>
          <Text accessibilityRole="header" style={styles.chatHeading}>A little less to keep in your head.</Text>
          <Text style={styles.small}>{laptopEnabled?'General conversation: laptop-local Qwen · unverified replies':ADAPTER_LABEL}</Text>
          <Text style={styles.small}>Chat stays in this session. Confirmed memories and reminder requests persist locally. Unsaved previews end on restart.</Text>
          {!!context && <Text style={styles.small}>Following up on: {context.name}</Text>}
          <View style={styles.section} accessibilityLiveRegion="polite">
            <View style={[styles.message, styles.assistantMessage]}><Text style={styles.small}>NOOK · PROTOTYPE</Text><Text style={styles.body}>{WELCOME}</Text></View>
            {messages.map((entry) => <View key={entry.id} style={styles.section}>
              <View testID={entry.role==='assistant'?'chat-assistant-'+entry.id:undefined} style={[styles.message, entry.role === 'user' ? styles.userMessage : styles.assistantMessage]}>
                <Text style={styles.small}>{entry.role === 'user' ? 'YOU' : entry.sources ? 'NOOK · CONFIRMED MEMORY' : entry.generated?GENERATED_LABEL:'NOOK · PROTOTYPE'}</Text>
                <Text selectable style={styles.body}>{entry.text}</Text></View>
              {entry.generated&&<Text style={styles.small}>Generated suggestion. Not a confirmed memory; no action was performed.</Text>}
              {entry.sources?.map((record) => <View key={record.id} style={styles.section}><MemoryCard memory={record} />
                {entry.ambiguous && <Button secondary title={'Use record: ' + record.name + ' · ' + readableDate(record.observedAt)} disabled={busy}
                  onPress={() => { setContext({ memoryId:record.id, name:record.name }); message('assistant', 'This dated record is selected for follow-up questions.', [record]); }} />}
              </View>)}
            </View>)}
          </View>

          {pending && <View style={[styles.card, styles.preview]}>
            <Text style={styles.small}>{pending.kind === 'memory' ? 'MEMORY' : pending.preview.action === 'cancel_reminder' ? 'REMINDER CANCELLATION' : 'REMINDER'} · EXACT PREVIEW</Text>
            {pending.kind === 'memory' ? <>
              <Text style={styles.cardTitle}>{pending.preview.draft.name}</Text>
              <Text style={styles.body}>{pending.preview.draft.location.state === 'known' ? 'Last recorded: ' + pending.preview.draft.location.text : 'Location unknown'}</Text>
              <Text style={styles.body}>Observed {readableDate(pending.preview.draft.observedAt)}</Text>
              <Text selectable style={styles.small}>{pending.preview.draft.observedAt}</Text>
              <Text style={styles.body}>{pending.preview.draft.notes || 'No notes'}</Text>
              <Text style={styles.small}>Source: your typed description. The time defaults to this request; edit it for an earlier observation.</Text>
            </> : <>
              <Text style={styles.cardTitle}>{pending.preview.draft.title}</Text>
              <Text style={styles.body}>{readableDate(pending.preview.draft.dueAt)}</Text>
              <Text selectable style={styles.small}>{pending.preview.draft.dueAt}</Text>
              <Text style={styles.body}>{pending.preview.draft.channel === 'email' ? 'Email queue · account and recipient not connected · no sending' : 'In-app reminder · device notifications not connected'}</Text>
              <Text style={styles.small}>{pending.preview.action === 'cancel_reminder' ? 'Confirm only this reminder’s cancellation. Other reminders stay unchanged.' : 'Confirm stores this exact request locally. It does not schedule an OS notification or send an email.'}</Text>
            </>}
            <Text style={styles.small}>{expired ? 'Preview expired. Review these details again.' : 'Expires ' + readableDate(pending.preview.expiresAt)}</Text>
            <Button disabled={busy || expired} title={pending.kind === 'memory' ? 'Save this exact memory' : pending.preview.action === 'cancel_reminder' ? 'Confirm this cancellation' : 'Save this exact reminder'} onPress={() => { void approve(); }} />
            {!(pending.kind === 'reminder' && pending.preview.action === 'cancel_reminder') && <Button secondary disabled={busy} title="Edit draft details" onPress={() => {
              if (pending.kind === 'memory') setMemoryEditor(pending.preview.draft); else setReminderEditor(pending.preview.draft);
              discard();
            }} />}
            <Button secondary disabled={busy} title="Discard this preview" onPress={() => { discard(); setNotice('Preview discarded. A previously committed change stays saved.'); }} />
          </View>}

          {memoryEditor && <View style={styles.card}>
            <Text style={styles.cardTitle}>Memory details</Text>
            <TextInput accessibilityLabel="Object name" style={styles.input} value={memoryEditor.name} maxLength={120} editable={!busy}
              onChangeText={(name) => setMemoryEditor({ ...memoryEditor, name })} placeholder="House keys" />
            <TextInput accessibilityLabel="Last recorded place" style={styles.input} value={memoryEditor.location.state === 'known' ? memoryEditor.location.text : ''} maxLength={200} editable={!busy}
              onChangeText={(text) => setMemoryEditor({ ...memoryEditor, location:{ state:'known', text } })} placeholder="In the hall drawer" />
            <Button secondary disabled={busy} title="Set location unknown" onPress={() => setMemoryEditor({ ...memoryEditor, location:{ state:'unknown' } })} />
            <Text style={styles.small}>{memoryEditor.location.state === 'unknown' ? 'Location is unknown.' : 'Location is supplied by you.'}</Text>
            <TextInput accessibilityLabel="Observation date with timezone" style={styles.input} value={memoryEditor.observedAt} maxLength={35} editable={!busy} autoCapitalize="none"
              onChangeText={(observedAt) => setMemoryEditor({ ...memoryEditor, observedAt })} />
            <TextInput accessibilityLabel="Memory notes" style={[styles.input, styles.notes]} value={memoryEditor.notes} maxLength={1500} editable={!busy} multiline
              onChangeText={(notes) => setMemoryEditor({ ...memoryEditor, notes })} placeholder="Optional identifying details" />
            <Button title="Review memory details" disabled={busy} onPress={() => { void reviewEditor(); }} />
            <Button title="Close draft editor" secondary disabled={busy} onPress={() => setMemoryEditor(null)} />
          </View>}
          {reminderEditor && <View style={styles.card}>
            <Text style={styles.cardTitle}>Reminder details</Text>
            <TextInput accessibilityLabel="Reminder title" style={styles.input} value={reminderEditor.title} maxLength={200} editable={!busy}
              onChangeText={(title) => setReminderEditor({ ...reminderEditor, title })} />
            <TextInput accessibilityLabel="Reminder date with timezone" style={styles.input} value={reminderEditor.dueAt} maxLength={35} editable={!busy} autoCapitalize="none"
              onChangeText={(dueAt) => setReminderEditor({ ...reminderEditor, dueAt })} />
            <Button title={reminderEditor.channel === 'local' ? 'Use email queue instead' : 'Use in-app reminder instead'} secondary disabled={busy}
              onPress={() => setReminderEditor({ ...reminderEditor, channel:reminderEditor.channel === 'local' ? 'email' : 'local' })} />
            <Text style={styles.small}>Delivery: {reminderEditor.channel}. No account or device scheduler is connected.</Text>
            <Button title="Review reminder details" disabled={busy} onPress={() => { void reviewEditor(); }} />
            <Button title="Close draft editor" secondary disabled={busy} onPress={() => setReminderEditor(null)} />
          </View>}

          <View style={styles.composer}>
            <TextInput accessibilityLabel="Message Nook" placeholder="What would you like to remember?" placeholderTextColor={colors.muted}
              style={[styles.input, styles.composerInput]} multiline maxLength={2000} value={input} editable={!busy} onChangeText={setInput} />
            <Button title={busy ? 'Working locally…' : 'Send message'} disabled={busy || !input.trim()} onPress={() => { void send(); }} />
          </View>
          {generating&&<Button secondary title="Cancel generation" onPress={()=>laptop.current.cancel()} />}
          <View style={styles.row}>{['Remember my keys are in the hall drawer','Where are my keys?','Remind me to water plants in 10 minutes'].map((example) =>
            <Pressable key={example} accessibilityRole="button" accessibilityLabel={'Example: ' + example} disabled={busy} style={styles.pill}
              onPress={() => setInput(example)}><Text style={styles.pillText}>{example}</Text></Pressable>)}</View>
          <Button secondary title="Enter memory details" disabled={busy} onPress={() => { discard(); setReminderEditor(null); setMemoryEditor(blankMemory()); }} />
          <Button secondary title="Start a fresh conversation" disabled={busy} onPress={() => {
            discard(); laptop.current.clear(); setMessages([]); setContext(null); setInput(''); setMemoryEditor(null); setReminderEditor(null);
            setNotice('Session conversation cleared. Confirmed memories and reminders remain saved.');
          }} />
        </View>}

        {tab === 'memories' && <View style={styles.section}>
          <Text accessibilityRole="header" style={styles.title}>What you’ve remembered.</Text>
          <Text style={styles.subtitle}>Up to 100 confirmed records. Dates and your descriptions show what you knew then.</Text>
          {saved.length ? saved.map((record) => <View key={record.id} style={styles.section}><MemoryCard memory={record} />
            <Button secondary disabled={busy} title={'Ask about ' + record.name} onPress={() => { setContext({ memoryId:record.id, name:record.name });
              message('assistant', 'This confirmed record is selected for your follow-up questions.', [record]); setTab('chat'); }} /></View>)
            : <View style={styles.card}><Text style={styles.body}>No confirmed memories yet. Tell Nook what you observed and review the preview.</Text></View>}
        </View>}
        {tab === 'reminders' && <View style={styles.section}>
          <Text accessibilityRole="header" style={styles.title}>Small things, remembered.</Text>
          <Text style={styles.subtitle}>Up to 100 saved requests. In-app due states work without a connection while Nook is open. Device notifications are not scheduled in this slice.</Text>
          {reminders.length ? reminders.map((job) => <ReminderCard key={job.id} reminder={job} now={now} busy={busy} onCancel={(id) => { void cancelReminder(id); }} />)
            : <View style={styles.card}><Text style={styles.body}>No confirmed reminders. Draft one in chat; you choose whether to save it.</Text></View>}
        </View>}
        {tab === 'setup' && <View style={styles.section}>
          <View style={styles.card}><Text style={styles.cardTitle}>Laptop-local conversation</Text>
            <Text style={styles.body}>Optional Qwen conversation in this web session, using an already installed laptop runtime. This is not on-phone offline AI. Saved memories and source cards are never sent to it.</Text>
            <Text accessibilityLiveRegion="polite" style={styles.small}>{laptopStatus}</Text>
            {Platform.OS==='web'?<Button secondary disabled={busy} title={laptopEnabled?'Disable laptop conversation':'Enable laptop conversation'} onPress={()=>{
              if(!begin())return;
              if(laptopEnabled){laptop.current.disable();setLaptopEnabled(false);setLaptopStatus('Disabled. Generated context cleared.');finish();return;}
              void laptop.current.enable().then((status)=>{if(mounted.current){setLaptopStatus(status);setLaptopEnabled(true);}})
                .catch(()=>{if(mounted.current)setLaptopStatus('Unavailable. Start the documented guarded laptop preview; no cloud fallback.');}).finally(finish);
            }} />:<Text style={styles.small}>Laptop bridge unavailable on this platform. Phone-local inference remains unqualified.</Text>}
          </View>
          <Text accessibilityRole="header" style={styles.title}>Ready for the everyday.</Text>
          <Text style={styles.subtitle}>See what this version can do before granting access or setting up an optional capability.</Text>
          <View style={styles.card}><Text style={styles.cardTitle}>Offline essentials</Text>
            <Text style={styles.body}>Typed memory, confirmed-record recall and saved reminder requests are available locally.</Text>
            <Text style={styles.small}>{Platform.OS === 'web' ? 'This preview uses browser SQLite. Clearing browser site data removes it. Browser offline reload and phone lifecycle are separate checks.' : 'Records use the app-owned SQLite vault. No phone performance or offline cold-launch qualification is claimed yet.'}</Text>
            <Text style={styles.small}>The vault is plaintext in local app/browser storage. This is a source prototype; encryption, export and recovery are not implemented.</Text>
          </View>
          <View style={styles.card}><Text style={styles.cardTitle}>Optional capabilities</Text>
            {Object.entries(CAPABILITY_DETAILS).map(([key,detail]) => <View key={key} style={styles.capability}>
              <Text style={styles.label}>{key === 'model' ? 'Local AI · setup unavailable' : key[0]!.toUpperCase()+key.slice(1)+' · unavailable'}</Text>
              <Text style={styles.body}>{detail}</Text></View>)}
            <View style={styles.capability}><Text style={styles.label}>Email · queue only</Text><Text style={styles.body}>Email needs connectivity, an authorized account, a reviewed recipient and separate send approval. Queueing is not sending. Nothing is transmitted when you save a request.</Text></View>
            <View style={styles.capability}><Text style={styles.label}>Device reminders · not integrated</Text><Text style={styles.body}>A future notification adapter needs permission and a real device test. This version stores the request and shows due status when the app is open.</Text></View>
          </View>
          <View style={styles.card}><Text style={styles.cardTitle}>Setup inside Nook</Text>
            <Text style={styles.body}>No manual file copying is planned. Before optional model or nearby-data setup, Nook must show the compatible pack, download and installed size, required storage, source and license, and what works offline.</Text>
            <Text style={styles.small}>Pack: not selected · Size: not yet known · Storage check: not implemented · Download: not started · Offline model: not ready</Text>
            <Text style={styles.body}>Progress, pause/cancel, retry, verification and readiness checks come with the qualified provisioning adapter. This prototype does not simulate a download.</Text>
          </View>
        </View>}
      </ScrollView>
    </KeyboardAvoidingView>
  </SafeAreaView>;
}

export default function App() {
  return <SafeAreaProvider><StatusBar style="dark" /><Nook /></SafeAreaProvider>;
}
