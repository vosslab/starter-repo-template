# Font style

> This file is vendored. Local changes can and will be overwritten by propagation.

Use only the following font families when you choose typography for new or revised project text.
This applies to websites, apps, slides, figures, and styled or generated documents.

## Choose the family

| Family | Use |
| --- | --- |
| Atkinson Hyperlegible Next | Default for body text, headings, UI labels, and other proportional text. |
| Atkinson Hyperlegible Mono | Code and other text that needs fixed-width alignment. |
| IBM Plex Sans Condensed | Space-constrained text, such as long literal URLs or narrow labels, when wrapping is impractical. |

Keep renderer fallbacks available for missing glyphs or font-loading failures. Respect readers'
accessibility overrides.

## Load and verify fonts

For reproducible output, bundle or embed the faces your project uses. Include the corresponding
license with redistributed font files. Check the rendered output for the intended face and
readable text at its actual display or print size. For a PDF that should carry its fonts,
check the exported file's font list for the expected embedded faces.

Get the font files from the upstream projects.
[Atkinson Hyperlegible Next](https://github.com/googlefonts/atkinson-hyperlegible-next),
[Atkinson Hyperlegible Mono](https://github.com/googlefonts/atkinson-hyperlegible-next-mono),
[IBM Plex Sans Condensed releases](https://github.com/IBM/plex/releases).
