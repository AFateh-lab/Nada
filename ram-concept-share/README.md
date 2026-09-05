# RAM Concept Share

RAM Concept has no built-in way to password-protect a `.cpt` model or to give
someone limited access to it. Anyone who has the file and a licence can open,
edit and re-save it.

This tool takes a different route: the other party never receives the `.cpt`.
You export what they need to see (plans, reports, drawings) and pack it into a
single encrypted HTML file. They open that file in any browser, type the
password, and see a read-only viewer with only the files you chose to share.

## How to use it

1. In RAM Concept, print the plans and reports you want to share to PDF
   (File > Print, choose a PDF printer). Export DXF/DWG backgrounds if needed.
2. Open `make-package.html` in Chrome, Edge or Firefox (double-click it).
3. Give the package a title, an optional message, watermark text and expiry
   date.
4. Drop in the exported files. For each one, tick "Recipient may download"
   only if you are happy for them to keep a copy. Leave it unticked for
   view-only.
5. Type a long passphrase twice and click **Build encrypted package**.
   A file such as `Level_3_PT_slab.html` is saved to your Downloads folder.
6. Send the HTML file by email or file share. Send the password by a
   different channel, for example a phone call or text message.

The recipient double-clicks the HTML file, enters the password, and the
viewer opens. No software, account or internet connection is required. PDF
pages render inside the viewer when online; offline, the browser's own PDF
view is used.

## What it does and does not protect

- Everything in the package is encrypted with AES-256-GCM. The key is derived
  from the password with PBKDF2-SHA256 at 600,000 iterations, which makes
  password guessing slow. Nothing is uploaded; the builder runs entirely in
  your browser.
- Without the password, the package reveals only its title.
- "View only" files have no download button and, for PDFs, no toolbar. The
  recipient can still take screenshots or photograph the screen. No file
  format can prevent that.
- The expiry date is checked by the viewer's clock. It stops casual use after
  the date but is not a hard security control.
- If you include the `.cpt` itself and tick download, the recipient gets the
  full editable model. The builder warns when it sees a model file.

## Alternatives when the other party must open the model in RAM Concept

- Host RAM Concept on a virtual desktop (Azure Virtual Desktop, Windows 365
  or a Remote Desktop server) and give them a login with a read-only folder,
  clipboard and file transfer disabled. They can inspect the live model but
  cannot take it away. This is the only way to give real "limited access" to
  the native model.
- Send a reduced copy: Save As, delete what you do not want shared, then
  encrypt the copy (7-Zip with AES-256) and send the password separately.
