# U1 OS: a personal operating workspace

## Life, Create, Earn, Control

The main rail now makes daily life, Digital Studio and Income first-class
destinations. Existing workspaces remain available; less frequent controls live
under More workspaces. Home includes direct launch cards for My Day, Digital
Studio and Income. These are local application workspaces, not a replacement for
macOS or independently connected cloud services.

## Digital Studio

The native Studio lives at `/#studio`, inside the canonical U1 OS shell.

- Weekly and daily planners.
- Workout and meal planners.
- Monthly calendars and geometric colouring pages.
- Course workbooks from an operator-written outline.
- Budget planners, habit trackers and content calendars.
- Product launch workbooks.
- Original downloadable SVG covers in orbital and editorial styles.
- Existing Prompt Builder and an explicitly external Canva hand-off.

PDF generation is local. The existing six printable templates use the business
document endpoint. Five additional workbook templates use
`/api/workspace/life-studio`. Course lessons and custom sections are supplied by
the user: the app creates the workbook structure, not fabricated course content.
The on-screen miniature is an illustrative layout, not a render of the PDF.
PDF text currently uses a basic ASCII font; unsupported characters are replaced.
These exports are static documents, not fillable forms.

The cover lab produces actual SVG files, not AI-generated bitmap artwork. AI
image generation and automatic Canva account sync are not connected by this
release. A saved API field or paid chat subscription is not proof of API access.
Provider requests, public listings and publishing are not performed automatically.

## My Day and Income

My Day reads actual local events, open tasks and projects. It does not invent a
schedule or read an unconnected email account. The workspace timezone determines
which events fall today. Reopen My Day to fetch a fresh view; the page is not a
continuous calendar stream.

Income provides workflows for digital products, courses, client services and
content. The offer builder creates a real local project with audience, channel,
outcome and next action. It does not create a store or take payment. The existing
manual ledger records actual entries; there are no demo earnings, earnings
guarantees or automatically combined currencies.

Crypto and Trading are restored as visible research destinations. Available
prices are provider snapshots. Market hours are published schedules, not live
halt detection. These views do not execute trades or claim brokerage access.

## Privacy and persistence

Studio and offer drafts are saved in this browser's local storage. This is not
encrypted storage or cross-device sync. Downloads contain the text you entered.
Created income projects use the existing managed local records store. Treat
exports and browser backups as private business material.

## Validation and release status

This increment is source implementation, not production certification. No live
image provider, Canva sync, purchase, publishing, trading, emergency response or
whole-Mac lockdown is claimed. This increment requires its own functional and
visual validation; previous build test results do not validate these new files.
