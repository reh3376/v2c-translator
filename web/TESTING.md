# Manual acceptance test for the web app

Run these steps on your own computer before you merge a change to `web/`.

## Prerequisites

1. Clone the repository. In its root, run `uv sync`.
2. Build the index: `uv run dd214kw build-index --download`.
3. Run `cd web && pnpm install && pnpm dev`.
4. Open http://localhost:3009.

## Steps

1. Look at the empty page. Expected: the heading "Translate your service record into civilian keywords", a drop zone with **Choose files**, a **Try with sample documents** button, and a "Stays on this computer" note that says nothing is uploaded or stored.
2. Click **Try with sample documents**. Expected: army_2000.txt, army_2000_dd215.json and army_vmet.txt appear in the list, and a "Civilian keywords" report appears below within a few seconds.
3. Read the report. Expected: Army, E6 (SSG), 9 years, 1 month. The **Military specialties** table has a row for 11B30 INFANTRYMAN matched to 11B Infantryman and a row for 92Y20 UNIT SUPPLY SPECIALIST matched to 92Y Unit Supply Specialist. The **Experience** group shows "9+ Years Professional Experience".
4. Click **Copy** next to the keyword string, then paste into a text editor. Expected: the button reads "Copied", and the pasted text starts with "Security Guards, Management of Personnel Resources".
5. Click **Download Markdown**, then **Download JSON**. Expected: civilian-keywords.md starts with "# Civilian Workforce Keywords", and civilian-keywords.json has a "matches" list with 11B and 92Y.
6. Click **Remove** next to army_vmet.txt. Expected: the file leaves the list, the report goes away, and the button reads "Translate 2 documents".
7. Make a text file named hello.txt that contains the word hello. Add it with **Choose files**, then click **Translate 3 documents**. Expected: the hello.txt row turns red, and an alert says "Couldn't read hello.txt" and "Unrecognised document: no extractor knows this layout."
8. Reload the page and put the mouse aside. Press Tab to move and Enter or Space to press a button. Expected: each control shows a visible focus ring. Enter on **Try with sample documents** shows the report and moves focus to the "Civilian keywords" heading. Tab then reaches **Download Markdown**, **Download JSON** and **Copy**. Space on a **Remove** button removes that file.

Report pass or fail for each step in the chat.
