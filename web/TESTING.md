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
5. Click **Download Markdown**, then **Download JSON**. Expected: the files save as army_2000-civilian-keywords-<today>.md and army_2000-civilian-keywords-<today>.json, with today's date as YYYY-MM-DD. The .md file starts with "# Civilian Workforce Keywords", and the .json file has a "matches" list with 11B and 92Y.
6. Click **Remove** next to army_vmet.txt. Expected: the file leaves the list, the report goes away, and the button reads "Translate 2 documents".
7. Make a text file named hello.txt that contains the word hello. Add it with **Choose files**, then click **Translate 3 documents**. Expected: the hello.txt row turns red, and an alert says "Couldn't read hello.txt" and "Unrecognised document: no extractor knows this layout."
8. Reload the page and put the mouse aside. Press Tab to move and Enter or Space to press a button. Expected: each control shows a visible focus ring. Enter on **Try with sample documents** shows the report and moves focus to the "Civilian keywords" heading. Tab then reaches **Download Markdown**, **Download JSON** and **Copy**. Space on a **Remove** button removes that file.

## The branch pictures

9. Reload the page and look at the row of six pictures under the headline. Expected: Navy, Coast Guard, Marine Corps, Army, Air Force and Space Force, in that order, with the horizon carrying across them from sea level to orbit. Every picture draws; none is a broken image. None shows a service seal, emblem, logo or insignia. The line underneath reads "Drawn for this page, sea level to orbit. No service seal, emblem or logo is used."
10. Click **Try with sample documents**. Expected: the Army picture is marked with a warm rule and the caption "From your documents", the other five step back, and the line under the row reads "Your documents name the Army."
11. Hover the pointer over each picture. Expected: a small lift, and nothing else. They are not links, so clicking one does nothing.
12. Turn the computer's Wi-Fi off and reload. Expected: the page and all six pictures still load. Nothing on the page comes from another site.

## The resources

13. Scroll to **Resources for veterans**. Expected: three groups, "Your records", "Work and transition" and "Benefits", then the **Veterans Crisis Line** panel reading "Dial 988, then press 1. Or text 838255."
14. Click every link in turn. Expected: each opens in a **new tab**, this page stays where it was, and each lands on the site its name promises:

    | Link | Site |
    | --- | --- |
    | Request military service records | archives.gov, "Request Military Service Records" |
    | milConnect | milconnect.dmdc.osd.mil |
    | DoD SkillBridge | skillbridge.mil |
    | Veterans' Employment and Training Service | dol.gov, DOL VETS |
    | CareerOneStop Veteran and Military Transition Center | careeronestop.org |
    | My Next Move for Veterans | mynextmove.org/vets |
    | DoD COOL | cool.osd.mil |
    | Hire Heroes USA | hireheroesusa.org |
    | VA benefits and health care | va.gov |
    | Veteran Readiness and Employment | va.gov, Chapter 31 |
    | GI Bill | va.gov, GI Bill |
    | Chat online at VeteransCrisisLine.net | veteranscrisisline.net |

    `pnpm check-links` walks the same list from the command line, and the weekly **Link check** workflow runs it on GitHub. Neither is part of pull-request CI, because these sites are outside this repository's control.

## The motion, with reduced motion off

15. Reload and click **Try with sample documents**. Expected: a thin bar sweeps under the buttons while the report is built, the report fades up, and the keyword chips arrive in a quick run rather than all at once. Nothing jumps, and no text moves while you are reading it.
16. Drag a file over the drop zone without letting go. Expected: the border turns solid and the zone swells very slightly. Drag the file away and it settles back.
17. In a **Military specialties** row that has one, press **Show 3 more**. Expected: the extra occupations open in about a fifth of a second and the button reads **Show fewer**. Press it again and they close as smoothly.
18. Hover and press a resource link and a button. Expected: a small, quick response to each, under a fifth of a second.

## The motion, with reduced motion on

19. Turn reduced motion on. On macOS: **System Settings > Accessibility > Display > Reduce motion**. On Windows: **Settings > Accessibility > Visual effects**, then turn **Animation effects** off. On GNOME: **Settings > Accessibility > Reduce Animation**.
20. Reload the page and repeat steps 15 to 18. Expected: everything still works and every part of the report appears, but nothing slides, lifts, swells or sweeps. The progress bar fills and sits still. The disclosure opens at once. Hovering a picture or a link changes nothing but the usual link styling.
21. Turn reduced motion back off.

## Mobile layout

22. Open the browser's responsive mode (Safari: **Develop > Enter Responsive Design Mode**; Chrome and Firefox: **F12**, then the device-toolbar button) and set the width to 390 px.
23. Walk the page from top to bottom. Expected: the six pictures sit two across in three rows, the drop zone and the "Stays on this computer" note stack, each specialty becomes a block instead of a table row that scrolls sideways, and the resource groups stack in one column. Nothing is cut off and nothing needs sideways scrolling.
24. Repeat at 768 px. Expected: the pictures sit three across in two rows, and the rest still reads cleanly.

## Keyboard only

25. Reload at full width and put the mouse aside. Tab from the top of the page to the bottom. Expected: focus is visible at every stop, the order follows the page, and the pictures are skipped, because they are not controls.
26. Tab into **Resources for veterans**. Expected: every link takes focus with a visible ring, and Enter opens it in a new tab. Close that tab and focus is where you left it.
27. Tab to a **Show 3 more** button and press Enter. Expected: it expands, the button becomes **Show fewer**, and focus stays on it.

## Swapping in a photograph

The six pictures are original illustrations. To use a public-domain DoD or DVIDS photograph instead of one:

1. Put the file in `web/public/branches/`, for example `web/public/branches/navy.jpg`. Choose an image with no identifiable faces and no service seal, emblem or logo.
2. In `web/src/content/branches.ts`, add a `photo` to that branch:

   ```ts
   photo: {
     src: "/branches/navy.jpg",
     credit: "U.S. Navy photo by Mass Communication Specialist 2nd Class A. Example",
   },
   ```

   Update `alt` to describe the photograph. The credit is part of the type, so a photograph without one does not compile, and it is shown under the picture.
3. Run `pnpm test`, then step 9 above.

## Taking the screenshots again

```bash
cd web
pnpm build && pnpm start        # one terminal
pnpm screenshots                # another
```

They land in `web/docs/screenshots/`, built from the fixture report, so no real document is involved.

Report pass or fail for each step in the chat.
