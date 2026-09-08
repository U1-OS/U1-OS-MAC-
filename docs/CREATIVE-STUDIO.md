# Creative Studio

Open `/studio.html` on the running local U1 OS server. The desktop Studio menu,
creation card, and quick-access dock all lead to this workspace.

## Documents

Choose a daily planner, weekly planner, meal-prep sheet, workout log, calendar,
habit tracker, coloring collection, or workbook. Customize the title, subtitle,
owner, content, footer, dates, paper size, accent, and typography.

- Daily and workout pages advance by day.
- Weekly and meal-prep pages advance by week, beginning on Monday.
- Calendars and habit trackers advance by calendar month.
- Workbook prompts are distributed across pages, four per page.
- Coloring sheets offer mandala, botanical, and cosmic patterns.
- A document is limited to 24 pages. Workbook content beyond 96 prompts is not
  included in a single export; split longer workbooks into separate projects.
- Text areas are finite. Use the preview to check long headings and lists; some
  templates intentionally show only the first items that fit their layout.

The workout and meal templates are blank planning tools, not personalized
medical, nutrition, or exercise recommendations.

## Export formats

**PDF:** The browser renders pages at 150 or 300 DPI, then assembles a real PDF
locally. Each page is a high-resolution image. Text is not searchable and the
document does not contain interactive form fields or PDF accessibility tags.
For editable artwork, export SVG instead.

**SVG:** Exports the currently selected page as vector artwork. This is useful
for further editing or manual upload to a compatible design application.

**Print:** Uses the browser's print dialog with A4 or US Letter page sizing.

**Project JSON:** Preserves editable document settings for backup or import.
Importing a project creates a new draft; choose Save project to add it to the
library. Files must use the supported U1 project format and be under 256 KB.

Downloads are requested through the browser. If the automatic download does not
start, use the persistent Save file link in the prepared-download banner. The
latest file stays available until another export, dismissal, or page navigation.
Browser permissions and download preferences determine where it is saved.

## Drafts and projects

The latest draft and up to 24 saved projects use local browser storage. They are
not encrypted, are scoped to this browser and app address, and are not synced to
Gmail, Canva, GitHub, or another device. Clearing browser data can remove them.
Export JSON backups for work you want to preserve, and avoid saving secrets.

Multiple tabs are not a collaborative editor. A warning appears when storage
changes in another tab; export a backup before replacing a draft if both
versions matter.

## Prompt builder

The prompt builder structures an objective, audience, context, output format,
tone, and constraints into a reusable brief. Provider and purpose choices
adjust the instructions. It does not contact a model, generate model-written
answers, or consume a subscription. Copy the result to an authorized assistant
or download it as plain text.

## Canva and paid accounts

Canva currently uses an explicit export-and-open workflow: export an SVG or PDF,
open Canva, and upload it yourself. Browser sign-in does not grant this local
application API authorization. No OAuth sync, subscription entitlement sharing,
or automatic Canva import is implied.

## Desktop navigation

Use Command-K on macOS or Control-K elsewhere to open the workspace command
menu. Existing desktop search buttons open the same menu. Arrow keys choose a
result, Enter opens it, and Escape closes the menu.

Appearance commands can pause decorative motion without stopping data refreshes,
or increase contrast on the new quick-access surfaces. System reduced-motion
preferences remain respected. These controls do not claim to change every
inherited module's appearance.
