# Page images

Place the project images directly in this folder:

- `logo.png`: the navigation logo. SVG is recommended for a sharp logo.
- `background.jpg`: the title background image. A landscape image is recommended.

Either filename can use `.svg`, `.png`, `.jpg`, `.jpeg`, `.webp`, `.avif`, or `.gif`.
For example, `logo.svg` and `background.webp` also work. Keep one file per role.

The page detects these files automatically, including changes to their contents.
It checks on load, when you return to the tab, and every ten seconds. You do not
need to edit code or restart the local development server. Missing files keep
the existing image placeholders. The page's logo picker remains available for temporary previews; reload to
return to the images saved in this folder. The title image loads as a full-panel
background; there is no separate image box on the right.

In a production deployment, include the images in the deployed build. Next.js
serves this folder publicly, so only place public image assets here.
