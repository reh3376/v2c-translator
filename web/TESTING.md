# Manual acceptance test for the web app

Run these steps on your own computer before you merge a change to `web/`.

Steps 1 to 57 are the app in **local** mode, which is what `pnpm dev` gives you and what
most changes affect. Steps 58 to 66 are the **hosted** mode, which runs from the container
image; do those as well for any change to the mode switch, the privacy copy, the robot
check, the limits, or anything the page loads by path.

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

9. Reload the page and look at the row of six pictures under the headline. Expected: Navy, Coast Guard, Marine Corps, Army, Air Force and Space Force, in that order, with the horizon carrying across them from sea level to orbit. Every picture draws; none is a broken image, and none has a visible seam, gap or sliver of a different colour along any edge. None shows a service seal, emblem, logo or insignia. The line underneath reads "Drawn for this page, sea level to orbit. No service seal, emblem or logo is used. Press one to watch its scene."
10. Click **Try with sample documents**. Expected: the Army picture is marked with a warm rule and the caption "From your documents", the other five step back, and the line under the row reads "Your documents name the Army."
11. Turn the computer's Wi-Fi off and reload. Expected: the page and all six pictures still load. Nothing on the page comes from another site.

## The depth in the pictures

Each picture is three drawn planes, stacked: sky, subject, foreground.

12. Reload at full width and scroll slowly so the row of pictures travels from the bottom of the
    window to the top. Expected: within each picture the sky, the subject and the near ground
    slide by slightly different amounts, so the picture reads as having depth. Nothing travels
    far: the whole effect is a few pixels. No edge of any plane ever becomes visible, and the
    captions under the pictures do not move at all.
13. Move the pointer slowly from the left edge of one picture to the right edge. Expected: the
    near ground leans further than the sky, and taking the pointer away settles it back rather
    than snapping it.
14. Scroll the row off the top of the window and back. Expected: nothing jumps, and no picture
    is ever drawn in a half-moved state when it comes back.

## The six scenes

Each picture is a button. Pressing it plays that branch's scene once.

15. Press each picture in turn and watch it to the end. Expected, in order:

    | Branch | The scene | About |
    | --- | --- | --- |
    | Navy | A pennant breaks out at the mast, then three puffs of white smoke rise from the forward gun and drift out to open sea | 2.9 s |
    | Coast Guard | The small boat comes alongside, then two crew step across to the cutter's after deck | 3.0 s |
    | Marine Corps | Three Marines come down the ramp and walk up the sand, the nearest the largest | 2.7 s |
    | Army | A tracked carrier pulls up in front of the truck, its rear ramp drops, and three soldiers step down behind it | 3.3 s |
    | Air Force | Three swept-wing silhouettes cross the frame in formation, trailing contrails | 2.4 s |
    | Space Force | A map grid comes up on the earth, a soft beam sweeps across it, and three status markers settle into view | 3.2 s |

    In every one: nothing is aimed at anything, no weapon, round, flame, explosion, target or
    casualty is drawn, and no seal, emblem, logo, insignia or unit marking appears anywhere.
    Figures are plain silhouettes and no face is drawn. When the scene ends, the picture is
    exactly as it was before it started.
16. Press a picture again while it is still playing. Expected: the scene starts over from the
    beginning. Nothing is left behind from the run you interrupted.
17. Press one picture, and while it is playing press a second. Expected: both play, each at its
    own pace, and neither disturbs the other.
18. Watch the caption under a picture while its scene plays. Expected: it does not move, and
    neither does anything else on the page.
19. Put the mouse aside. Tab to a picture. Expected: a focus ring is drawn just inside the frame
    and is not clipped at any edge. Press Enter: the scene plays. Press Space: it plays again.
    Focus stays on the picture throughout.
20. Click **Try with sample documents**, then press the Army picture. Expected: the scene plays,
    and the Army picture stays marked with its warm rule and "From your documents" caption while
    it does.

## The resources

21. Scroll to **Resources for veterans**. Expected: three groups, "Your records", "Work and transition" and "Benefits", then the **Veterans Crisis Line** panel reading "Dial 988, then press 1. Or text 838255."
22. Click every link in turn. Expected: each opens in a **new tab**, this page stays where it was, and each lands on the site its name promises:

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

23. Reload and click **Try with sample documents**. Expected: a thin bar sweeps under the buttons while the report is built, the report fades up, and the keyword chips arrive in a quick run rather than all at once. Nothing jumps, and no text moves while you are reading it.
24. Drag a file over the drop zone without letting go. Expected: the border turns solid and the zone swells very slightly. Drag the file away and it settles back.
25. In a **Military specialties** row that has one, press **Show 3 more**. Expected: the extra occupations open in about a fifth of a second and the button reads **Show fewer**. Press it again and they close as smoothly.
26. Hover and press a resource link and a button. Expected: a small, quick response to each, under a fifth of a second.

## The motion, with reduced motion on

27. Turn reduced motion on. On macOS: **System Settings > Accessibility > Display > Reduce motion**. On Windows: **Settings > Accessibility > Visual effects**, then turn **Animation effects** off. On GNOME: **Settings > Accessibility > Reduce Animation**.
28. Reload the page and repeat steps 23 to 26. Expected: everything still works and every part of the report appears, but nothing slides, lifts, swells or sweeps. The progress bar fills and sits still. The disclosure opens at once. Hovering a picture or a link changes nothing but the usual link styling.
29. Turn reduced motion back off.

## Mobile layout

30. Open the browser's responsive mode (Safari: **Develop > Enter Responsive Design Mode**; Chrome and Firefox: **F12**, then the device-toolbar button) and set the width to 390 px.
31. Walk the page from top to bottom. Expected: the six pictures sit two across in three rows, the drop zone and the "Stays on this computer" note stack, each specialty becomes a block instead of a table row that scrolls sideways, and the resource groups stack in one column. Nothing is cut off and nothing needs sideways scrolling.
32. Repeat at 768 px. Expected: the pictures sit three across in two rows, and the rest still reads cleanly.

## Keyboard only

33. Reload at full width and put the mouse aside. Tab from the top of the page to the bottom. Expected: focus is visible at every stop, and the order follows the page. Each of the six pictures takes focus in turn, because each one is a button that plays its scene.
34. Tab into **Resources for veterans**. Expected: every link takes focus with a visible ring, and Enter opens it in a new tab. Close that tab and focus is where you left it.
35. Tab to a **Show 3 more** button and press Enter. Expected: it expands, the button becomes **Show fewer**, and focus stays on it.

## Light and dark

36. Reload at full width. Expected: in the top right, an **Appearance** control reading System,
    Light, Dark, with **System** chosen, and the page in whatever your computer is set to.
37. Press **Dark**. Expected: the page crosses to dark over about a fifth of a second. The page
    behind the text is near black, the panels a shade lighter, the headings and body text light,
    the buttons and links a pale teal, the keyword chips warm on a dark brown. Nothing is grey on
    grey, and no text is hard to read.
38. Press **Light**, then **System**.
39. With **System** chosen, change the computer's appearance: **System Settings > Appearance >
    Dark** on macOS; **Settings > Personalisation > Colours** on Windows. Expected: the page
    follows within a moment, with no reload. Set it back and the page follows again.
40. Press **Dark**, then reload the page. Expected: it comes back dark, and **Dark** is still
    chosen. Watch the moment it loads: there is no white flash before it turns dark.
41. With **Dark** chosen, set the computer's appearance to light. Expected: the page stays dark.
    Your choice wins over the computer's.
42. Press **System** and reload. Expected: the page follows the computer again.
43. In dark, look at the row of six pictures. Expected: six night scenes, the horizon still
    carrying across them, the sun now a dim moon. Every picture draws, none is washed out or
    glowing against the dark page, and none shows a seal, emblem, logo or insignia.
44. In dark, click **Try with sample documents**. Expected: the report reads as cleanly as in
    light. The Army picture is marked, the keyword chips are legible, and the **Veterans Crisis
    Line** panel still stands out.
45. Add a text file the translator cannot read and translate again, as in step 7. Expected: the
    red row and the alert are readable against the dark page, not glaring.
46. Put the mouse aside. Tab to the **Appearance** control. Expected: focus lands on the chosen
    option with a visible ring. Left and right arrows move between System, Light and Dark, and
    the page changes as you move. Tab again leaves the group in one step.
47. Turn reduced motion on (step 27), reload in dark and press **Light**. Expected: the page
    changes theme at once, with no fade, and everything else behaves as in step 28. Turn reduced
    motion back off.
48. Open the page in a private window with cookies and site data blocked. Expected: the control
    still works for the session, the page still follows the computer, and nothing is remembered
    after a reload.

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

## How it works

49. Scroll to **How it works** at full width and go down it at a normal reading pace. Expected:
    three steps. In the first, the three documents turn out of a stack into a fan as the step
    arrives, and all three labels stay readable. In the second, the blocks of the form light one
    after another as the step travels up the window, three of them labelled. In the third, the
    keywords arrive one after another above the string they make. The page scrolls at its normal
    speed throughout: nothing holds the page still, nothing takes the wheel, and scrolling
    straight past the whole section costs nothing.
50. Scroll back up past the section and down again. Expected: nothing replays. Each step arrives
    once.
51. Set the width to 390 px and walk the section again. Expected: each step's picture sits under
    its words rather than beside them, the form still lights as you scroll, nothing is pinned,
    and nothing needs sideways scrolling.
52. Turn reduced motion on (step 27) and reload. Expected: all three steps are complete the
    moment they are on screen. The documents are already fanned, every block of the form is lit,
    and every keyword is there. Nothing turns, slides or lights up as you scroll.

## The summary that stays put

53. With reduced motion off, at full width, click **Try with sample documents** and scroll down
    through the report. Expected: the summary panel, with the branch, the pay grade, the net
    active service and the documents read, stays at the top of the window while the specialties
    and the keywords scroll under it. No text shows through it.
54. From the keyword string at the bottom, press Shift+Tab back up to **Download Markdown**.
    Expected: the page scrolls so the button is fully visible **above** the summary panel, not
    hidden under it, and the focus ring is not clipped.
55. Set the width to 390 px and scroll the report again. Expected: the summary scrolls away with
    everything else, because on a phone it would take a third of the screen.

## The scenes, with reduced motion on

56. Turn reduced motion on (step 27), reload, and press each of the six pictures in turn.
    Expected: the scene appears as a still picture of the moment after, fades up over about a
    fifth of a second, holds, and fades away. Nothing moves, turns, grows or travels. Every
    button still works, from the mouse and from the keyboard, and pressing again replays the
    fade. Turn reduced motion back off.
57. In dark, press each picture again. Expected: every scene is as legible as in light. The
    Navy smoke is clearly lighter than the night sky behind it, and nothing glows.

## Hosted mode

The hosted app is the same code with `V2C_MODE=hosted`, served under `/v2c`, bot-checked
and rate-limited. It runs from the container image, so this part needs Docker. The keys
below are Cloudflare's documented public test values, which always pass; they are not
credentials, and they are why this can be done with no Cloudflare account.

Most of it is already automatic. `deploy/smoke.sh` checks the boot refusal, the loopback
binding, the read-only filesystem, the copy, the robot check and the logs;
`deploy/verify-behind-caddy.sh` checks the page in a browser behind a Caddy configured
like the career site's. Build once, run both, and then do by hand only what neither can:

```bash
docker build -t v2c:local .                        # from the repository root; takes a few minutes
deploy/smoke.sh v2c:local
uv run --extra ocr python tests/make_scan.py --out /tmp/scan.pdf --pages 5
deploy/smoke.sh v2c:local --scan /tmp/scan.pdf     # also reports peak memory
deploy/verify-behind-caddy.sh v2c:local
```

Then run the image on its own and look at it:

```bash
docker run --rm -p 127.0.0.1:3009:3009 \
  --read-only --tmpfs /tmp/v2c:rw,noexec,nosuid,size=256m,mode=1777 \
  -e V2C_MODE=hosted \
  -e TURNSTILE_SITE_KEY=1x00000000000000000000AA \
  -e TURNSTILE_SECRET_KEY=1x0000000000000000000000000000000AA \
  v2c:local
# then open http://localhost:3009/v2c
```

58. Look at the page. Expected: the panel beside the drop zone is headed **What happens to
    your documents** and reads "Your documents are sent over HTTPS to this server, read in
    memory, and deleted as soon as your report is ready. Nothing is stored, logged or
    shared.", then "Don't upload a document you aren't comfortable sending." Nothing on
    the page says the documents stay on this computer. Under **How it works** the lede
    says all three steps happen on this server. Under **Resources for veterans** the lede
    says nothing about your documents goes with you. The hint under the drop zone says
    scans are read with OCR, not that OCR has to be installed.
59. Look between the drop zone and the buttons. Expected: a line reading "Before you
    translate, confirm you're not a robot." and, under it, Cloudflare's widget. With the
    test key it ticks itself within a second or two. **This is the check no script can
    do:** `deploy/verify-behind-caddy.sh` proves the script and its requests are allowed,
    but a test key draws no challenge box, so whether the box appears is a thing only a
    person can see. If it is missing with a real key, the policy's `frame-src` is wrong.
60. Click **Try with sample documents**. Expected: a report, as in step 2.
61. Translate again. Expected: it works a second time. The widget is asked for a fresh
    token after each translation, because a token is good for one.
62. Open the browser's console and translate once more. Expected: nothing about a
    Content-Security-Policy, and no blocked request.
63. Watch the container's output through all of the above. Expected: one line at boot
    reading `v2c hosted mode: 2 concurrent, queue 8, 10 per 10 min per visitor`, and
    nothing else at all. No file name, no document text, no address.
64. Add a text file the translator cannot read, as in step 7, and translate. Expected: the
    page names the file and says "Unrecognised document". The container prints one line
    of the form `translate failed id=… kind=…` and nothing more, and in particular not the
    name of your file.
65. Translate eleven times in ten minutes from the same browser. Expected: the eleventh
    says "You've translated several times just now. Try again in a few minutes."
66. Stop the container and start it again without `TURNSTILE_SECRET_KEY`. Expected: it
    exits straight away, printing `v2c cannot start:` and which variable is missing. It
    must not stay up: a page that promises a robot check with no check behind it is worse
    than a page that will not load.

## Taking the screenshots again

```bash
cd web
pnpm build && pnpm start        # one terminal
pnpm screenshots                # another
```

They land in `web/docs/screenshots/`, built from the fixture report, so no real document is
involved. Each page is shot twice, the second time with the system set to dark: the `-dark` files
are the dark theme. Three more sets go with the scrolling:

| Files | What they show |
| --- | --- |
| `strip-<where>-000.png` to `-100.png` | the whole page at five points on the way down, with a report on it, for desktop light, desktop dark, mobile light, and both themes with reduced motion |
| `scene-<branch>-light-N.png`, `-dark-N.png` | each branch's vignette, caught while it plays |
| `scene-<branch>-reduced-1.png` | the still frame a reader who asked for less motion gets instead |

## The palette

`web/docs/palette.md` lists every colour token with its light and dark value and the contrast
ratio it measures. `pnpm test` asserts those ratios against WCAG AA and fails if the document
falls out of step, so changing a colour means running the tests, not re-reading this page.

## The branch art

`web/public/branches/` holds twelve drawings, and they are the only ones edited by hand: one
scene per branch, and one act drawing per branch holding the actors its scene moves. Everything
under `web/public/branches/derived/` is written by `pnpm dark-art` and should never be edited:
the dark twin of each drawing, the three depth planes of each scene, and one file per actor.

- Every top-level shape in a scene carries `data-plane="sky"`, `"mid"` or `"fore"`; every one in
  an act drawing carries `data-actor="<name>"`. A shape with neither fails the generator.
- An actor is drawn **where it settles**, not where it comes in from. That is what lets a reader
  who asked for less motion see the scene as a still frame with no transform at all.
- After any change to a drawing, run `pnpm dark-art`, then `pnpm test`: `--check` and
  `src/content/branch-art.test.ts` both fail if the derived files are stale or orphaned.
- An actor added to a drawing needs a beat in `web/src/content/vignettes.ts`, and a beat needs an
  actor. The tests hold both halves of that.

Report pass or fail for each step in the chat.
