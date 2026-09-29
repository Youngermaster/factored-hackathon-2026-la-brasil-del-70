# Components

The design system's primitives in `apps/web/src/shared/ui/`, imported only from `@/shared/ui`. Each has a colocated test (`*.test.tsx` beside it). Visual rules are in [`docs/design/DESIGN.md`](../design/DESIGN.md). All copy comes from the locale files; the examples below show literals only for brevity.

Compound components are namespaces (`Dialog.Root`, `Dialog.Content`, ...): the parts share state through context, and callers compose them with `children` instead of boolean props.

## Actions

### Button, IconButton, TextLink

```tsx
<Button onClick={save}>{t('auth.verify')}</Button>                 // variant: primary | secondary | ghost | danger
<Button variant="secondary" pending={mutation.isPending}>...</Button> // aria-busy, clicks ignored, width kept
<Button asChild variant="secondary"><Link to="/">{t('common.goHome')}</Link></Button>
<IconButton label={t('preferences.title')} icon={<SettingsIcon />} /> // label is required: it is the accessible name
<TextLink href={url} external>{t('...')}</TextLink>                 // target _blank, rel noopener noreferrer, says so
```

The primary action is ink, never an accent color. `danger` is for destructive confirmations only (phase 13's card block).

## Forms

### Field (compound), Input, Textarea, Select

```tsx
<Field.Root invalid={errors.phone !== undefined} required hasHint>
  <Field.Label>{t('auth.phoneLast4')}</Field.Label>
  <Field.Control>
    <Input inputMode="numeric" {...register('phone')} />
  </Field.Control>
  <Field.Hint>{t('auth.phoneLast4Hint')}</Field.Hint>
  <Field.Error>{t('auth.phoneLast4Invalid')}</Field.Error>
</Field.Root>
```

`Field.Control` passes `id`, `aria-describedby` (hint, then error), `aria-invalid`, and `aria-required` to its single child. The label is always above, the error below; there are no placeholder labels. `Select` is a styled native `<select>` (the platform picker on phones, native typeahead).

### OneTimeCodeInput

```tsx
<OneTimeCodeInput value={code} onValueChange={setCode} onComplete={enableSubmit} />
```

One real text field (`autocomplete="one-time-code"`, `inputmode="numeric"`) drawn as six digit boxes. Paste keeps the digits only ("482 915" becomes `482915`), extra digits are dropped, backspace and selection are native. It never submits on its own: changing context on input would fail WCAG 3.2.2.

## Overlays

### Dialog (compound)

```tsx
<Dialog.Root open={open} onOpenChange={setOpen}>
  <Dialog.Trigger asChild><Button>...</Button></Dialog.Trigger>
  <Dialog.Content>
    <Dialog.Header>
      <Dialog.Title>...</Dialog.Title>
      <Dialog.Description>...</Dialog.Description>
    </Dialog.Header>
    ...
    <Dialog.Footer><Dialog.Close asChild><Button variant="secondary">...</Button></Dialog.Close></Dialog.Footer>
  </Dialog.Content>
</Dialog.Root>
```

Radix: focus moves in and is trapped, Escape and the labeled close button close it, focus returns to the trigger, the page behind is inert. A title is required.

### Sheet (compound)

The same focus management as a side panel: `Sheet.Root`, `Sheet.Trigger`, `Sheet.Content`, `Sheet.Title`, `Sheet.Description`, `Sheet.Close`. Used for preferences; phase 13 uses it for the glass box on narrow screens.

### Tabs (compound)

`Tabs.Root`, `Tabs.List` (give it an `aria-label`), `Tabs.Trigger`, `Tabs.Panel`. Arrow keys move between tabs; Tab moves into the panel.

### Tooltip

```tsx
<Tooltip content={t('preferences.title')}><IconButton label={t('preferences.title')} icon={<SettingsIcon />} /></Tooltip>
```

A visual echo of an existing accessible name, never the only place information lives. `TooltipProvider` is mounted once by the app.

### Toast

```tsx
const { notify } = useToast();
notify({ title: t('auth.stepUpDone'), tone: 'decision' });   // tone: neutral | decision | risk
```

Transient confirmations only (blocking errors stay inline). Confirmations are announced politely, `risk` toasts assertively; F8 focuses the region; each toast has a labeled close button and pauses on hover and focus.

## Display

| Component | Use | Notes |
|---|---|---|
| `Card.Root`, `Card.Header`, `Card.Body`, `Card.Footer` | A real object: a session, a balance, a handoff | Name the region with `aria-labelledby` pointing at the header title |
| `Badge` | A short neutral label (role, demo mode) | Tones `understanding`, `decision`, `risk` only when the label has that meaning |
| `StatusPill` | `verified`, `pending`, `failed`, `escalated`, `review_required` | Icon plus word; only `verified` is yellow; a review never looks like success |
| `AsOfNote` | The as-of instant of snapshot data | `<AsOfNote at={balance.as_of} />` renders a `<time>` in the viewer's locale |
| `Stack`, `Inline` | Vertical rhythm and wrapping rows | `gap` is 1, 2, 3, 4, 6, 8, or 12 (4 px steps); `as` picks the element |
| `Skeleton`, `SkeletonGroup` | Loading placeholders shaped like the content | The group is a status region announced once |
| `EmptyState` | Nothing to show yet | Title, why, and what would fill it |
| `ErrorState` | A failed load or action | `role="alert"`, the request id for support, a retry action |
| `KeyValueList.Root`, `KeyValueList.Item` | Label and value pairs as a `<dl>` | `numeric` switches the value to tabular mono figures |
| `DataTable.*` with `useTableSort` | Records in rows | Caption required (it names the scrollable region); sortable headers are buttons with `aria-sort`; `numeric` cells right-align in mono |
| `Timeline.Root`, `Timeline.Item` | An ordered trace (phase 13 glass box) | `tone` colors the marker by meaning; the text states the meaning too |
| `JsonView` | Read-only records (handoffs, execution records) | Serialized and rendered as a text node: markup inside values is shown, never interpreted; the region is focusable for keyboard scrolling |

```tsx
const table = useTableSort(rows, { key: 'date', direction: 'descending' }, compareRows);
<DataTable.Root caption={t('...')}>
  <DataTable.Head>
    <tr>
      <DataTable.HeaderCell sort={table.directionOf('date')} onSort={() => { table.sortBy('date'); }}>...</DataTable.HeaderCell>
      <DataTable.HeaderCell numeric>...</DataTable.HeaderCell>
    </tr>
  </DataTable.Head>
  <DataTable.Body>{table.rows.map((row) => <DataTable.Row key={row.id}>...</DataTable.Row>)}</DataTable.Body>
</DataTable.Root>
```

## Theme, locale, and icons

- `ThemeProvider` and `useTheme()` (`preference`: system, light, dark; `resolved`), `ThemeSwitcher`. `public/theme-init.js` applies the stored choice before first paint.
- `LocaleProvider`, `useLocale()`, `useFormat()` (money, number, date, dateTime, time, relative, countdown), and `LocaleSwitcher` live in `@/shared/i18n`.
- Icons come from `@/shared/ui` (`icons.ts` re-exports the Phosphor glyphs in use under role names such as `CheckIcon`, `HumanIcon`). Add a glyph there; never import `@phosphor-icons/react` elsewhere, never hand-draw an SVG. Decorative icons get `aria-hidden="true"`.

## Feature-level compounds (auth)

`StepUp` (from `@/features/auth`) is a compound dialog: `StepUp.Root` owns the challenge and the verification, and `StepUp.Title`, `StepUp.Description`, and `StepUp.CodeForm` compose its content. Features do not render it; they call `useStepUp().requestStepUp()`, which resolves `true` once the session is stepped up and `false` if the person cancels or the session ends. `AuthProvider` hosts the default composition.
