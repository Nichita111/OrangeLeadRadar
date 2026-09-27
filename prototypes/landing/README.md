# Landing scene prototype

A standalone prototype of the Landing page (WF-27), kept as input for the Landing task. It is not part of the app build and nothing imports it.

## Run it locally

From this folder, start any static server and open the address it prints:

```sh
cd prototypes/landing
python3 -m http.server 8000      # then open http://localhost:8000
# or: npx serve .
```

Opening `index.html` directly from disk also works. three.js r128 and Anime.js 3.2.2 are served from `vendor/`; only the Geist fonts come from Google Fonts, and the page falls back to system fonts offline.

Scroll to move through the steps, or use the dots on the right. Under `prefers-reduced-motion` each step shows its end frame.

`screens/` holds a screenshot of each step.

The page scrolls through eight steps of one 3D object: accounts, sources, read, sift (a wafer whose dies are the architecture and flow diagrams of `diagrams/src/`), quote, score, rank and the Prospects list.

It departs from the approved documents in ways the Landing task must take through a docs change first: eight steps instead of the three of WF-27, the step wording, and the demo shortcuts on Landing. DHL Group and Lufthansa Group values come from WF-12 and WF-24; every other account's position, documents and priority are sample values.

Published copy with its version history: https://claude.ai/artifact/JsVpYnFr7KbfJqT2CxHjeM
