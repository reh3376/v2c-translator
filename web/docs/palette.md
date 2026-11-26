# Coastal steel

The palette this app is painted in, light and dark, and the measurements that say it is readable.

Everything here is produced from one file, `src/app/theme.css`. Nothing else in the app holds a
colour: `src/theme/contrast.test.ts` fails if a hexadecimal value, an `rgb()` or a `color-mix()`
turns up in `globals.css`, and fails if a declared pair drops below its WCAG AA threshold.

## How it is put together

Two layers, and a switch.

1. **Primitive ramps.** `--steel-*`, `--teal-*`, `--amber-*`, `--danger-*`, `--warning-*`,
   `--success-*`. Fixed values with no meaning attached. The same in both themes.
2. **Semantic tokens.** `--color-*`. What the page uses. Each is declared once, as
   `light-dark(light value, dark value)`, so the two themes sit on the same line and neither can
   be edited without the other in view.
3. **The switch.** `color-scheme` on `:root`: `light dark` while the choice is System, `only
   light` or `only dark` once the reader picks one. `light-dark()` resolves against it, and so do
   form controls and scrollbars, which is why the page needs no separate dark stylesheet.

To change a colour, change a stop in a ramp. To use one, reach for a `--color-*` token; if none
of them says what you mean, add one, with both values, and add the pair it forms to `PAIRS` in
`src/theme/contrast.ts`.

## The tokens

| Token | Light | Dark |
| --- | --- | --- |
| `--color-bg` | `#f3f6f5` | `#0d1615` |
| `--color-surface` | `#ffffff` | `#152120` |
| `--color-surface-raised` | `#ffffff` | `#1e2a29` |
| `--color-surface-sunken` | `#e8eeed` | `#1e2a29` |
| `--color-text` | `#152120` | `#e3ecea` |
| `--color-text-secondary` | `#50605f` | `#9cb0ad` |
| `--color-text-muted` | `#5d6e6c` | `#8ba09d` |
| `--color-border` | `#d3dddb` | `#2a3837` |
| `--color-border-strong` | `#6f8280` | `#6f8280` |
| `--color-primary` | `#1e5c63` | `#7cc3c9` |
| `--color-primary-hover` | `#174a52` | `#93d0d5` |
| `--color-on-primary` | `#ffffff` | `#0d1615` |
| `--color-primary-text` | `#174a52` | `#93d0d5` |
| `--color-primary-tint` | `#ecf3f3` | `#0b2528` |
| `--color-link` | `#1e5c63` | `#93d0d5` |
| `--color-link-hover` | `#152120` | `#ffffff` |
| `--color-focus` | `#1e5c63` | `#7cc3c9` |
| `--color-accent` | `#b9782a` | `#e3a85b` |
| `--color-chip-bg` | `#f6e6cf` | `#3a2a15` |
| `--color-chip-text` | `#6e4310` | `#edbe7c` |
| `--color-danger-text` | `#8f1d16` | `#f3aba3` |
| `--color-danger-bg` | `#fcebe9` | `#2a110f` |
| `--color-danger-border` | `#e0948d` | `#74332d` |
| `--color-danger-rule` | `#8f1d16` | `#d4615a` |
| `--color-warning-text` | `#6b4500` | `#f0cd82` |
| `--color-warning-bg` | `#fff3d6` | `#2b2008` |
| `--color-warning-border` | `#e1bd68` | `#6a5420` |
| `--color-success-text` | `#15664a` | `#7ed3ae` |

## The measurements

Every pair the page actually puts on screen, in both themes. WCAG 2.1 AA asks 4.5:1 of text under
24 px, and 3:1 of larger text, of the edge of a control, and of a graphic you have to make out.
These are the numbers `src/theme/contrast.test.ts` asserts; it reads `theme.css`, so they cannot
drift from what ships.

| Pair | Light | Dark | Needs |
| --- | --- | --- | --- |
| Body text on the page | 15.20:1 | 15.27:1 | 4.5:1 |
| Body text on a surface | 16.53:1 | 13.73:1 | 4.5:1 |
| Body text on a raised surface | 16.53:1 | 12.30:1 | 4.5:1 |
| The entry copied off the document | 14.07:1 | 12.30:1 | 4.5:1 |
| Secondary text on the page | 6.07:1 | 8.07:1 | 4.5:1 |
| Secondary text on a surface | 6.60:1 | 7.26:1 | 4.5:1 |
| Captions on the page | 4.93:1 | 6.66:1 | 4.5:1 |
| Captions on a surface | 5.36:1 | 5.99:1 | 4.5:1 |
| Primary button label | 7.59:1 | 9.19:1 | 4.5:1 |
| Primary button label, hovered | 9.82:1 | 10.69:1 | 4.5:1 |
| Secondary button label | 9.82:1 | 9.62:1 | 4.5:1 |
| Quiet button label on the page | 9.03:1 | 10.69:1 | 4.5:1 |
| Secondary button label, hovered | 8.73:1 | 9.33:1 | 4.5:1 |
| A link on the page | 6.98:1 | 10.69:1 | 4.5:1 |
| A link on a surface | 7.59:1 | 9.62:1 | 4.5:1 |
| A keyword chip | 6.92:1 | 8.05:1 | 4.5:1 |
| The branch the documents named | 6.92:1 | 8.05:1 | 4.5:1 |
| A file that could not be read | 7.72:1 | 9.41:1 | 4.5:1 |
| A note from the translator | 7.68:1 | 10.48:1 | 4.5:1 |
| A copy that worked | 6.37:1 | 10.34:1 | 4.5:1 |
| The wordmark | 6.98:1 | 9.19:1 | 3.0:1 |
| The focus ring on the page | 6.98:1 | 9.19:1 | 3.0:1 |
| The focus ring on a surface | 7.59:1 | 8.27:1 | 3.0:1 |
| The edge of the drop zone | 4.05:1 | 4.07:1 | 3.0:1 |
| A section rule on the page | 3.72:1 | 4.53:1 | 3.0:1 |
| The primary button against the page | 6.98:1 | 9.19:1 | 3.0:1 |
| The rule beside a file that could not be read | 7.72:1 | 4.77:1 | 3.0:1 |
| The accent rule | 3.33:1 | 8.76:1 | 3.0:1 |
| The accent rule on a surface | 3.63:1 | 7.88:1 | 3.0:1 |

### What is not measured, and why

- `--color-border`. A hairline between two rows of text, not the boundary of a control. WCAG
  1.4.11 does not ask 3:1 of it, and at 3:1 the table would read as a grid of boxes rather than a
  list of rows. The lines that do mark a control, `--color-border-strong` and `--color-focus`,
  are measured.
- The 3 px rule over the caption of the branch the documents named. The mark is carried by the
  words "From your documents" and by the tint behind them, both measured; the rule agrees with
  them rather than carrying the meaning alone.
- `--color-primary-tint` as a background on its own. It is only ever behind text that is measured
  against it, under "Secondary button label, hovered".

## Adjustments to the chosen values

The seed values were kept wherever they measured. Three had to move, and one is recorded here
because it reads as a change and is not:

- **Light body text, `#14201f` to `#152120`.** One step on each channel, so that the same stop
  serves as the light page's ink and the dark page's surface. Indistinguishable; one fewer value
  to keep in step.
- **The label on the branch the documents named.** The accent, `#b9782a`, reaches only 2.96:1 on
  the chip background it sits on, so that label uses the chip text colour, `#6e4310`, at 6.92:1.
  The accent still draws the rule above the caption, where 3:1 against the page is enough.
- **The smallest captions.** A third text level, `#5d6e6c` light and `#8ba09d` dark, a step
  quieter than secondary text and still over 4.5:1 on both the page and a surface. Without it
  `--color-text-muted` would have been a second name for `--color-text-secondary`.
- **The edge of the drop zone and the section rules, `#6f8280`.** The seed list gives one border
  value, `#d3dddb` light, a hairline at 1.39:1 on a white surface. A second, stronger stop was
  needed for the things WCAG counts as boundaries: the dashed drop zone, and the rule that heads
  each section.

## The branch pictures

The six illustrations have a dark twin each, written by `scripts/dark-art.mjs` from the light
file. One transform does it: every colour goes through OKLCH, its lightness is pulled into the
night band, some chroma comes off, and the hue is left alone. It is monotonic in lightness, so
the shapes keep the order of light and dark they had by day, and nothing in the drawing moves.
Space Force is already a night scene, so it is taken only three tenths of the way.

Both pictures are in the markup and the stylesheet shows one, so the right picture is painted
before React runs and the hidden one leaves the accessibility tree with it.

Run `pnpm dark-art` after changing a light picture. `src/content/branch-art.test.ts` fails if the
committed dark files are not what the generator produces today.
