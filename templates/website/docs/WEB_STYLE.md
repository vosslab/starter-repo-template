# Web style

> This file is vendored. Local changes can and will be overwritten by propagation.

## Start with the browser

Consult Modern Web Guidance before changing browser-facing HTML, CSS, or JavaScript. Search for
the user-visible behavior, retrieve the matching guidance, and check it against the project's
browser support policy. Use Baseline Widely available when the project has no declared target.
Follow the guide's fallback for features outside that target. If the guide is unavailable,
check the platform specification and MDN compatibility data for the same target.
[Modern Web Guidance setup](https://developer.chrome.com/docs/modern-web-guidance/get-started)

Prefer native semantics and interactions. Use real buttons and links. For a modal, use a named
`<dialog>` with native opening and dismissal behavior. Choose the applicable guide for a popover
or another overlay. Keep DOM and keyboard order meaningful, and retain a visible focus indicator.
Use `:focus-visible` when styling it.

## Lay out and style

- Define the content hierarchy, intended viewport range, theme, and purpose of any motion.
- Use flexbox for one-dimensional flow and grid for rows and columns. Start with intrinsic sizing
  and logical properties. Use container queries when a component depends on its own space and
  media queries for page-wide conditions or user preferences.
- Keep selectors scoped. Where styles need explicit precedence, declare cascade layer order and
  keep easily overridden defaults low-specificity. Use custom properties for shared design values.
- Respect `prefers-reduced-motion`, preserve essential cues, and check text and controls in each
  supported theme. Follow `docs/FONT_STYLE.md` and `docs/COLOR_CONTRAST_ACCESSIBILITY.md`.

## Web typography

- Use `rem` for text sizes and let the root size follow the reader's browser preference.
  Raise the browser's default font size to check that text and controls still fit.
- When fallback sizing matters, block the web font and check for clipping and reflow.
  `font-size-adjust: from-font` uses the first available font's metric. Use a measured numeric
  ratio from the preferred face when the fallback needs to match that metric even if the face
  fails to load. [CSS Fonts specification](https://www.w3.org/TR/css-fonts-5/#font-size-adjust-prop)

## Verify the rendered result

Serve the built output over HTTP. Check the changed interaction with a keyboard and at the
relevant viewport sizes. Inspect overflow, zoom, focus, and the supported color and motion
preferences. Use the project's browser checks for repeatable behavior.
[PLAYWRIGHT_TEST_STYLE.md](PLAYWRIGHT_TEST_STYLE.md)
